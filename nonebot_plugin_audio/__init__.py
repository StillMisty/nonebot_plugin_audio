from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Message, Event, Bot
from nonebot.params import RegexMatched
from nonebot import on_regex
from nonebot.plugin import PluginMetadata

import httpx
from bs4 import BeautifulSoup
import json
import re

__plugin_meta__ = PluginMetadata(
    name="语音合成",
    description="合成对应角色的语音",
    type="application",
    usage="语音列表:获取可合成角色列表\n[角色]说[文本]:合成语音",
    homepage="https://github.com/StillMisty/nonebot_plugin_audio",
)


url = "https://yy.lolimi.cn/"
available_roles = on_command("语音列表") # 获取可用角色列表，强制更新
audio_tts = on_regex(r"^(.*?)说(.*)$")  # 使用正则表达式捕获角色和文本
audio_roles = None  # 将 audio_roles 初始化为 None


async def get_audio_roles(url: str, force_update: bool = False):
    """
    从网页中提取音频角色列表。
    """
    # 使用缓存机制，避免重复请求网页
    global audio_roles
    if audio_roles is not None and not force_update:
        return audio_roles

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # 检查响应状态码

        soup = BeautifulSoup(response.content, "html.parser")
        select_element = soup.find("select", id="audioRole")
        if select_element:
            options = select_element.find_all("option")
            audio_roles = [option.text for option in options]
            return audio_roles
        else:
            logger.error("无法找到角色列表选择框")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误: {e}")
        return None
    except httpx.RequestError as e:
        logger.error(f"网络请求错误: {e}")
        return None
    except Exception as e:
        logger.error(f"其他错误: {e}")
        return None


@available_roles.handle()
async def available_roles_handle(bot: Bot, event: Event):
    roles = await get_audio_roles(url=url, force_update=True)
    if roles is None:
        await bot.send(event, Message("获取角色列表失败"))
        return

    role_info = "可用的角色：\n" + "\n".join(
        f"{i + 1}. {role}" for i, role in enumerate(roles)
    )
    await bot.send_forward_msg(
        user_id=event.user_id,  # 私聊时使用 user_id
        group_id=getattr(event, "group_id", None),  # 群聊时使用 group_id
        messages=[
            {
                "type": "node",
                "data": {
                    "name": "消息发送者A",
                    "uin": "10086",
                    "content": [{"type": "text", "data": {"text": role_info}}],
                },
            }
        ],
    )


@audio_tts.handle()
async def audio_tts_handle(
    bot: Bot, event: Event, matched: re.Match[str] = RegexMatched()
):
    selected_role = matched.group(1).strip()
    text_to_speak = re.sub(r"\[.*\]", "", matched.group(2).strip())
    
    if not 0 < len(text_to_speak.encode("utf-8")) < 100:
        await bot.send(event, Message("字符长度应在 1 到 100 之间"))
        return

    roles = await get_audio_roles(url)
    if roles is None:
        await bot.send(event, Message("获取角色列表失败"))
        return

    if selected_role not in roles:
        return

    audio_url = await generate_audio(url, selected_role, text_to_speak)
    if audio_url:
        await bot.send(event, Message(f"[CQ:record,file={audio_url}]"))
    else:
        await bot.send(event, Message("语音合成错误"))


async def generate_audio(url, role, text):
    """
    模拟生成音频的请求并返回音频链接。
    """
    try:
        data = {"role": role, "text": text}

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{url}/index/audio", data=data)
            response.raise_for_status()

        result = response.json()
        if result["code"] == 0:
            return result["data"]
        else:
            logger.error(f"音频生成失败: {result['message']}")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误: {e}")
        return None
    except httpx.RequestError as e:
        logger.error(f"网络请求错误: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"解析返回数据错误: {e}, 响应内容: {response.text}")
        return None
    except Exception as e:
        logger.error(f"其他错误: {e}")
        return None
