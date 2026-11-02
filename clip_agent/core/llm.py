"""本地大模型客户端（Ollama / MLX 等 OpenAI 兼容接口，可选能力）。

未配置或不可达时所有能力自动降级（规则路由 / 纯规则字幕修正），
不阻塞主流程。
"""
from __future__ import annotations

import json
import os
import socket
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b"


def _base_url() -> str:
    return os.environ.get("CLIP_AGENT_LLM_URL", DEFAULT_BASE_URL) or ""


def is_available() -> bool:
    """探测本地模型服务是否可达（0.5s 超时，失败自动走规则兜底）。"""
    url = _base_url()
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def chat(system: str, user: str, model: str = None, temperature: float = 0.0,
         timeout: float = 60.0) -> str:
    """调用 OpenAI 兼容的 /chat/completions 接口，返回模型文本。"""
    url = _base_url()
    payload = {
        "model": model or os.environ.get("CLIP_AGENT_LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "stream": False,
    }
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]
