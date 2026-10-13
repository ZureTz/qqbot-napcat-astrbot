"""Isolated behavior tests; real AstrBot routing still needs integration testing."""

import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/astrbot_plugin_starter"


class FakeStar:
    def __init__(self, context):
        self.context = context


def decorator(*args, **kwargs):
    return lambda target: target


def load_plugin():
    api = types.ModuleType("astrbot.api")
    api.AstrBotConfig = dict
    api.logger = Mock()
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = object
    event.filter = types.SimpleNamespace(command=decorator)
    star = types.ModuleType("astrbot.api.star")
    star.Star, star.Context, star.register = FakeStar, object, decorator
    modules = {"astrbot": types.ModuleType("astrbot"), "astrbot.api": api,
               "astrbot.api.event": event, "astrbot.api.star": star}
    spec = importlib.util.spec_from_file_location("starter_under_test", PLUGIN / "main.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


starter = load_plugin()


class StarterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        schema = json.loads((PLUGIN / "_conf_schema.json").read_text())
        self.config = {key: value["default"] for key, value in schema.items()}
        self.config["llm_enabled"] = True
        self.context = types.SimpleNamespace(
            get_current_chat_provider_id=AsyncMock(return_value="session-model"),
            llm_generate=AsyncMock(return_value=types.SimpleNamespace(completion_text="回答")),
        )
        self.plugin = starter.StarterPlugin(self.context, self.config)

    def event(self, text="ask explain Python\nin Chinese", admin=True):
        return types.SimpleNamespace(
            get_message_str=lambda: text,
            is_admin=lambda: admin,
            unified_msg_origin="qq:GroupMessage:123",
            plain_result=lambda text: text,
            should_call_llm=Mock(),
        )

    async def ask(self, event=None):
        event = event or self.event()
        replies = [reply async for reply in self.plugin.ask(event)]
        event.should_call_llm.assert_called_once_with(False)
        self.assertEqual(self.plugin._active_requests, 0)
        return replies

    async def test_session_provider_and_complete_prompt(self):
        self.assertEqual(await self.ask(), ["回答"])
        self.context.get_current_chat_provider_id.assert_awaited_once_with("qq:GroupMessage:123")
        self.context.llm_generate.assert_awaited_once_with(
            chat_provider_id="session-model", prompt="explain Python\nin Chinese",
            system_prompt=self.config["system_prompt"],
        )

    async def test_explicit_provider(self):
        self.config["provider_id"] = "custom-model"
        await self.ask()
        self.context.get_current_chat_provider_id.assert_not_awaited()
        self.assertEqual(self.context.llm_generate.call_args.kwargs["chat_provider_id"], "custom-model")

    async def test_disabled_and_non_admin_do_not_call_model(self):
        self.config["llm_enabled"] = False
        self.assertIn("未启用", (await self.ask())[0])
        self.config["llm_enabled"] = True
        self.assertIn("管理员", (await self.ask(self.event(admin=False)))[0])
        self.context.llm_generate.assert_not_awaited()

    async def test_public_mode(self):
        self.config["admin_only"] = False
        self.assertEqual(await self.ask(self.event(admin=False)), ["回答"])

    async def test_empty_and_long_prompt(self):
        self.assertIn("用法", (await self.ask(self.event("ask")))[0])
        self.assertIn("过长", (await self.ask(self.event("ask " + "字" * 4001)))[0])
        self.context.llm_generate.assert_not_awaited()

    async def test_missing_provider(self):
        self.context.get_current_chat_provider_id.side_effect = RuntimeError("secret-key")
        self.assertIn("未找到", (await self.ask())[0])
        self.context.llm_generate.assert_not_awaited()

    async def test_error_does_not_leak_key(self):
        self.context.llm_generate.side_effect = RuntimeError("secret-key")
        starter.logger.reset_mock()
        reply = (await self.ask())[0]
        self.assertIn("调用失败", reply)
        self.assertNotIn("secret-key", reply + str(starter.logger.mock_calls))

    async def test_timeout_cancels_request_and_releases_capacity(self):
        self.config["timeout_seconds"] = 1
        cancelled = asyncio.Event()

        async def slow_model(**kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        self.context.llm_generate.side_effect = slow_model
        self.assertIn("超时", (await self.ask())[0])
        self.assertTrue(cancelled.is_set())

    async def test_empty_and_long_response(self):
        self.context.llm_generate.return_value.completion_text = " "
        self.assertIn("未返回文本", (await self.ask())[0])
        self.context.llm_generate.return_value.completion_text = "字" * 4000
        self.assertIn("已截断", (await self.ask())[0])

    async def test_concurrent_requests_reject_overflow_and_release_on_cancel(self):
        started = asyncio.Event()

        async def slow_model(**kwargs):
            if self.context.llm_generate.await_count == 2:
                started.set()
            await asyncio.Event().wait()

        async def consume():
            return [reply async for reply in self.plugin.ask(self.event())]

        self.context.llm_generate.side_effect = slow_model
        tasks = [asyncio.create_task(consume()) for _ in range(2)]
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            replies = await consume()
            self.assertIn("稍后再试", replies[0])
            self.assertEqual(self.context.llm_generate.await_count, 2)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(self.plugin._active_requests, 0)


if __name__ == "__main__":
    unittest.main()
