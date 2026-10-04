import asyncio
import json
import urllib.error
import urllib.request

from config.settings import settings


class DeepSeekError(RuntimeError):
    pass


def _post_chat(messages: list[dict], temperature: float) -> str:
    if not settings.deepseek_api_key:
        raise DeepSeekError("服务端尚未配置 DEEPSEEK_API_KEY")

    body = json.dumps(
        {
            "model": settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "NewsPilot/2.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DeepSeekError(f"DeepSeek 请求失败（{exc.code}）：{detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DeepSeekError(f"无法连接 DeepSeek：{exc}") from exc

    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek 返回了无法识别的数据") from exc


async def chat(messages: list[dict], temperature: float = 0.25) -> str:
    return await asyncio.to_thread(_post_chat, messages, temperature)
