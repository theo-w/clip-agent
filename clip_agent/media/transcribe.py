"""语音转写模块（V1.1 可选能力）：本地 Whisper 后端适配。

支持两个可选后端（均为可选依赖，未安装时核心链路零影响）：
- mlx-whisper：Apple Silicon 本地推理，默认后端；
- faster-whisper：跨平台 CPU 推理。

首次运行会自动下载模型；国内网络可设置 HF_ENDPOINT=https://hf-mirror.com。
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from . import analyzer


class AsrBackendError(RuntimeError):
    """无可用 ASR 后端或后端执行失败。"""


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


# 各后端默认模型：mlx 使用 HF 仓库名，faster-whisper 使用模型档名
DEFAULT_MODELS = {
    "mlx-whisper": "mlx-community/whisper-small-mlx",
    "faster-whisper": "small",
}

_BACKEND_MODULES = {
    "mlx-whisper": "mlx_whisper",
    "faster-whisper": "faster_whisper",
}


def available_backend() -> str | None:
    """探测已安装的 ASR 后端，返回后端名；都没有则返回 None。"""
    for name, module in _BACKEND_MODULES.items():
        if importlib.util.find_spec(module) is not None:
            return name
    return None


def extract_audio(media_path: str, wav_path: Path) -> Path:
    """抽取 16kHz 单声道 wav，作为转写后端的统一输入。"""
    analyzer.run_cmd([
        "ffmpeg", "-y", "-hide_banner", "-i", str(media_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path),
    ])
    return wav_path


def transcribe(
    media_path: str,
    workdir: Path,
    backend: str = "auto",
    model: str = "",
    language: str = "zh",
) -> tuple:
    """转写音视频为字幕片段，返回 (segments, 实际后端, 实际模型)。"""
    name = available_backend() if backend in ("", "auto") else backend
    if name is None:
        raise AsrBackendError(
            "未安装语音转写后端。安装方式：pip install -e \".[asr]\""
            "（Apple Silicon 装 mlx-whisper，其他平台装 faster-whisper）；"
            "国内网络建议先设置 HF_ENDPOINT=https://hf-mirror.com"
        )
    if name not in _BACKEND_MODULES:
        raise AsrBackendError(
            f"不支持的转写后端：{name}（可选 mlx-whisper / faster-whisper）"
        )
    if importlib.util.find_spec(_BACKEND_MODULES[name]) is None:
        raise AsrBackendError(
            f"指定的后端 {name} 未安装，请执行 pip install -e \".[asr]\""
        )

    used_model = model or DEFAULT_MODELS[name]
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    wav = extract_audio(media_path, workdir / "asr_input.wav")

    if name == "mlx-whisper":
        segments = _run_mlx(wav, used_model, language)
    else:
        segments = _run_faster(wav, used_model, language)
    return segments, name, used_model


def _run_mlx(wav: Path, model: str, language: str) -> list:
    try:
        import mlx_whisper
        result = mlx_whisper.transcribe(
            str(wav), path_or_hf_repo=model, language=language,
        )
    except Exception as exc:
        msg = str(exc)
        if "xethub" in msg:
            msg += "（镜像下载模型失败：请设置 HF_HUB_DISABLE_XET=1 后重试）"
        raise AsrBackendError(f"mlx-whisper 转写失败：{msg}") from exc
    return [
        TranscriptSegment(float(s["start"]), float(s["end"]), s["text"].strip())
        for s in result.get("segments", [])
        if s.get("text", "").strip()
    ]


def _run_faster(wav: Path, model: str, language: str) -> list:
    try:
        from faster_whisper import WhisperModel
        engine = WhisperModel(model, device="cpu", compute_type="int8")
        segments, _info = engine.transcribe(
            str(wav), language=language, vad_filter=True,
        )
        return [
            TranscriptSegment(float(s.start), float(s.end), s.text.strip())
            for s in segments
            if s.text.strip()
        ]
    except Exception as exc:
        raise AsrBackendError(f"faster-whisper 转写失败：{exc}") from exc


def _fmt_time(t: float) -> str:
    ms = max(int(round(t * 1000)), 0)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list) -> str:
    """转写片段 → 标准 SRT 文本（纯函数，便于单测）。"""
    blocks = [
        f"{i}\n{_fmt_time(seg.start)} --> {_fmt_time(seg.end)}\n{seg.text}\n"
        for i, seg in enumerate(segments, 1)
    ]
    return "\n".join(blocks)
