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
available_roles = on_command("语音列表")
audio_tts = on_regex(r"^(.*?)说(.*)$")  # 使用正则表达式捕获角色和文本
audio_roles = None


async def get_audio_roles(url):
    """
    从网页中提取音频角色列表。
    """
    # 如果已经获取过角色列表，直接返回
    global audio_roles
    if audio_roles is not None:
        return audio_roles

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        response.raise_for_status()  # 检查响应状态码
        soup = BeautifulSoup(response.content, "html.parser")
        select_element = soup.find("select", id="audioRole")
        if select_element:
            options = select_element.find_all("option")
            return [option.text for option in options]
        else:
            return None  # 或抛出异常，取决于你的需求
    except httpx.exceptions.RequestException as e:
        logger.error(f"网络请求错误: {e}")
        return None
    except Exception as e:
        logger.error(f"其他错误: {e}")
        return None


@available_roles.handle()
async def available_roles_handle(bot: Bot, event: Event):
    global audio_roles
    audio_roles = await get_audio_roles(url=url)
    if audio_roles is None:
        logger.error("检索角色失败！")
        return

    role_info = "可用的角色：\n" + "\n".join(
        f"{i + 1}. {role}" for i, role in enumerate(audio_roles)
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
    # 使用正则表达式捕获的角色和文本
    selected_role = matched.group(1).strip()
    text_to_speak = re.sub(r"\[.*\]", "", matched.group(2).strip())
    logger.info(f"角色: {selected_role}, 文本: {text_to_speak}")

    global audio_roles
    audio_roles = await get_audio_roles(url)
    if audio_roles is None:
        logger.error("模型列表为空")
        return

    if selected_role not in audio_roles:
        await bot.send(event, Message("角色不存在"))
    else:
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
        # 获取角色和文本
        data = {"role": role, "text": text}

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{url}/index/audio", data=data)
        response.raise_for_status()  # 检查状态码

        # 解析返回数据，提取音频链接
        try:
            result = response.json()
            if result["code"] == 0:
                audio_url = result["data"]
                return audio_url
            else:
                logger.error(f"音频生成失败: {result['message']}")
                return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"解析返回数据错误: {e}, 响应内容: {response.text}")
            return None

    except httpx.exceptions.RequestException as e:
        logger.error(f"网络请求错误: {e}")
        return None
    except Exception as e:
        logger.error(f"其他错误: {e}")
        return None
