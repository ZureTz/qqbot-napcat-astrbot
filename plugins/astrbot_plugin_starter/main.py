"""Small command plugin for checking the QQ -> AstrBot -> QQ round trip."""

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Star, register


@register("astrbot_plugin_starter", "ZureTz", "QQ 机器人项目起步插件", "0.1.0")
class StarterPlugin(Star):
    @filter.command("ping")
    async def ping(self, event: AstrMessageEvent):
        """检查机器人消息链路，不调用大模型。"""
        yield event.plain_result("pong · NapCat + AstrBot 消息链路正常")

    @filter.command("bot_info")
    async def bot_info(self, event: AstrMessageEvent):
        """显示项目模板信息。"""
        yield event.plain_result("QQ Bot Starter v0.1.0\n可用指令：/ping、/bot_info")
