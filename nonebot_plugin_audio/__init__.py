from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Message, Event, Bot
from nonebot.params import RegexMatched
from nonebot import on_regex
from nonebot.plugin import PluginMetadata

import httpx
import re

__plugin_meta__ = PluginMetadata(
    name="语音合成",
    description="合成对应角色的语音",
    type="application",
    usage="语音列表:获取可合成角色列表\n[角色]说[文本]:合成语音",
    homepage="https://github.com/StillMisty/nonebot_plugin_audio",
)

url = "https://api.3000y.ac.cn"

available_roles = on_command("语音列表")
audio_tts = on_regex(r"^(.*?)说(.*)$")  # 使用正则表达式捕获角色和文本
audio_roles = None  # 将 audio_roles 初始化为 None


async def get_audio_roles(
    url: str = f"{url}/v1/gpt-audio-role", fresh: bool = False
) -> set[str] | None:
    """获取可合成角色列表。

    Args:
        url (str): 网址
        fresh (bool): 是否强制刷新
    Returns:
        set[str]: 角色列表
    """

    global audio_roles
    # 如果已经获取过角色列表且不强制刷新，则直接返回
    if audio_roles is not None and not fresh:
        return audio_roles
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
        res = response.json()
        if res["code"] != 200:
            logger.error(f"请求错误: {response.json()['msg']}")
            return None

        return set(res["data"])
    except Exception as e:
        logger.error(f"请求错误: {e}")


async def generate_audio(
    role: str, text: str, url: str = f"{url}/v1/gpt-audio"
) -> str | None:
    """生成语音。

    Args:
        url (str): 网址
        role (str): 角色
        text (str): 文本

    Returns:
        str: 语音链接
    """
    async with httpx.AsyncClient() as client:
        data = {"role": role, "input": text}
        response = await client.post(url, json=data, timeout=60)
        response.raise_for_status()
    res = response.json()
    if res["code"] != 200:
        logger.error(f"请求错误: {response.json()['msg']}")
        return None
    return res["data"]


@available_roles.handle()
async def handle_audio_roles(bot: Bot, event: Event):
    audio_roles = await get_audio_roles(fresh=True)
    if audio_roles is None:
        await available_roles.finish("获取角色列表失败")

    msg = "可合成角色列表：\n" + "\n".join(
        f"{i + 1}. {role}" for i, role in enumerate(audio_roles)
    )

    # 转发消息，防止刷屏
    await bot.send_forward_msg(
        user_id=event.user_id,  # 私聊时使用 user_id
        group_id=getattr(event, "group_id", None),  # 群聊时使用 group_id
        messages=[
            {
                "type": "node",
                "data": {
                    "name": "消息发送者A",
                    "uin": "10086",
                    "content": [{"type": "text", "data": {"text": msg}}],
                },
            }
        ],
    )


@audio_tts.handle()
async def handle_audio_tts(matched: re.Match[str] = RegexMatched()):
    role = matched.group(1).strip()
    text = matched.group(2).strip()

    audio_roles = await get_audio_roles()
    if audio_roles is None:
        await audio_tts.finish("获取角色列表失败")

    if role not in audio_roles:
        return

    try:
        audio_url = await generate_audio(role, text)
    except httpx.ReadTimeout:
        audio_tts.finish("语音合成超时")
        return
    
    if audio_url:
        await audio_tts.finish(Message(f"[CQ:record,file={audio_url}]"))
    else:
        await audio_tts.finish("语音合成错误")
