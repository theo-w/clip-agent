"""S006 语音转写生成字幕（可选 ASR 后端，V1.1）。"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media import analyzer, transcribe as asr
from .base import Skill


class TranscribeSkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S006",
            name="语音转写生成字幕",
            desc=(
                "调用本地 Whisper 后端（mlx-whisper / faster-whisper，可选安装）"
                "把音视频转写为 SRT，作为字幕校对（S002）的上游输入"
            ),
            params={
                "asr_backend": "auto",   # auto | mlx-whisper | faster-whisper
                "asr_model": "",         # 空 = 后端默认模型
                "language": "zh",
            },
            input=["audio_track"],
            output=["transcribed_srt", "subtitle_text"],
            triggers=["语音转写", "语音识别", "识别语音", "转写", "自动字幕", "生成字幕", "ASR", "asr"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        if not ctx.media_path:
            return self.fail("缺少音视频素材（--media）")
        try:
            segments, backend, model = asr.transcribe(
                str(ctx.media_path),
                Path(ctx.workdir),
                backend=str(params.get("asr_backend") or "auto"),
                model=str(params.get("asr_model") or ""),
                language=str(params.get("language") or "zh"),
            )
        except asr.AsrBackendError as exc:
            return self.fail(str(exc))
        except analyzer.MediaToolError as exc:
            return self.fail(str(exc))

        if not segments:
            return self.fail("未识别到语音内容（音频可能为纯音乐或无对白）")

        srt_path = Path(ctx.workdir) / "transcribed.srt"
        srt_path.write_text(asr.segments_to_srt(segments), encoding="utf-8")
        return self.success({
            "transcribed_srt": str(srt_path),
            # 供下游 S002 消费的中间结果键
            "subtitle_text": str(srt_path),
            "segment_count": len(segments),
            "backend": backend,
            "asr_model": model,
            "segments_preview": [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in segments[:5]
            ],
        })

    def render(self, ctx: ExecContext, params: dict, outputs: dict,
               on_progress=None) -> list:
        # 纯复制产物，无渲染耗时；保留 on_progress 参数以对齐 Skill.render 协议
        path = outputs.get("transcribed_srt")
        return [Path(path)] if path and Path(path).exists() else []
