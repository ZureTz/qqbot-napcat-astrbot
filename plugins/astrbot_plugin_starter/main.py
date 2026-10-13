"""Message diagnostics and an opt-in, single-turn LLM entry point."""

import asyncio

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


@register("astrbot_plugin_starter", "ZureTz", "QQ 机器人项目起步插件", "0.2.0")
class StarterPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._active_requests = 0

    @filter.command("ping")
    async def ping(self, event: AstrMessageEvent):
        """检查机器人消息链路，不调用大模型。"""
        yield event.plain_result("pong · NapCat + AstrBot 消息链路正常")

    @filter.command("bot_info")
    async def bot_info(self, event: AstrMessageEvent):
        """显示项目模板信息。"""
        yield event.plain_result(
            "QQ Bot Starter v0.2.0\n可用指令：/ping、/bot_info、/ask 问题\n"
            "LLM 配置入口：AstrBot 面板 → 模型提供商；插件设置 → QQ Bot Starter"
        )

    @filter.command("ask")
    async def ask(self, event: AstrMessageEvent):
        """单轮调用已配置的模型，例如 /ask 用三句话解释 Python。"""
        # Avoid a second request through AstrBot's default chat pipeline.
        event.should_call_llm(False)
        if not self.config.get("llm_enabled", False):
            yield event.plain_result("LLM 入口未启用，请在 QQ Bot Starter 插件设置中开启。")
            return
        if self.config.get("admin_only", True) and not event.is_admin():
            yield event.plain_result("当前 /ask 仅允许 AstrBot 管理员使用。")
            return

        # Command matching is handled by AstrBot. Preserve spaces and newlines
        # in the remaining text instead of accepting only one parsed argument.
        parts = event.get_message_str().strip().split(maxsplit=1)
        prompt = parts[1].strip() if len(parts) == 2 else ""
        if not prompt:
            yield event.plain_result("用法：/ask 你的问题")
            return
        if len(prompt) > 4000:
            yield event.plain_result("问题过长，请控制在 4000 字符以内。")
            return
        if self._active_requests >= 2:
            yield event.plain_result("模型正在处理其他请求，请稍后再试。")
            return

        self._active_requests += 1
        try:
            provider_id = self.config.get("provider_id", "").strip()
            if not provider_id:
                try:
                    provider_id = await self.context.get_current_chat_provider_id(
                        event.unified_msg_origin
                    )
                except Exception as exc:
                    logger.warning(f"Starter provider lookup failed ({type(exc).__name__})")
                    yield event.plain_result(
                        "未找到当前会话的聊天模型。请在模型提供商中添加并启用模型，"
                        "然后选择默认对话模型，或在插件设置中指定模型。"
                    )
                    return

            timeout = max(1, min(300, int(self.config.get("timeout_seconds", 60))))
            response = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    system_prompt=self.config.get("system_prompt", ""),
                ),
                timeout=timeout,
            )
            answer = response.completion_text
            if not answer or not answer.strip():
                reply = "模型未返回文本，请检查所选模型是否支持文本对话。"
            else:
                reply = answer.strip()
                if len(reply) > 3500:
                    reply = reply[:3500] + "\n（回复过长已截断，请要求模型简短回答。）"
        except asyncio.TimeoutError:
            reply = "模型响应超时，请稍后再试，或检查服务地址和超时设置。"
        except Exception as exc:
            # Provider error bodies can contain credentials or user messages.
            logger.warning(f"Starter LLM request failed ({type(exc).__name__})")
            reply = "模型调用失败，请在面板检查模型、API Key、额度和服务地址。"
        finally:
            self._active_requests -= 1

        yield event.plain_result(reply)
