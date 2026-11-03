"""S001 静音片段自动裁切。"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media import analyzer
from .base import Skill


def invert_to_keep(total: float, silences, padding: float) -> list:
    """保留片段 = 全片时长减去（外扩 padding 后的）静音段（纯函数，便于单测）。"""
    keep = []
    cursor = 0.0
    for seg in silences:
        s = max(seg.start - padding, cursor)
        e = min(seg.end + padding, total)
        if s - cursor > 1e-3:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if total - cursor > 1e-3:
        keep.append((cursor, total))
    return keep


class SilenceCutSkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S001",
            name="静音片段裁切",
            desc="识别音频低于阈值的静音段，生成裁剪时间戳，可选渲染裁切后成片",
            params={
                "silence_threshold": -30,  # 静音判定阈值（dB）
                "min_duration": 0.5,      # 静音段最短时长（秒）
                "padding": 0.1,            # 裁切时静音段前后保留的余量（秒）
            },
            input=["audio_track"],
            output=["cut_time_list", "silence_segments"],
            triggers=["静音", "无声", "去静音"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        media = ctx.media_path
        if not media:
            return self.fail("缺少视频/音频素材（--media）")
        threshold = float(params.get("silence_threshold", -30))
        min_duration = float(params.get("min_duration", 0.5))
        padding = float(params.get("padding", 0.1))

        try:
            if not analyzer.has_audio(media):
                return self.fail("素材没有音频轨，无法检测静音")
            total = analyzer.probe_duration(media)
            silences = analyzer.detect_silence(media, threshold, min_duration)
        except analyzer.MediaToolError as exc:
            return self.fail(str(exc))

        keep = invert_to_keep(total, silences, padding)
        outputs = {
            "cut_time_list": [
                {"start": round(s, 3), "end": round(e, 3)} for s, e in keep
            ],
            "silence_segments": [
                {
                    "start": round(seg.start, 3),
                    "end": round(seg.end, 3),
                    "duration": round(seg.duration, 3),
                }
                for seg in silences
            ],
            "media_duration": round(total, 3),
            "keep_duration": round(sum(e - s for s, e in keep), 3),
        }
        # 时间戳方案落盘，供剪映手动导入参考
        if ctx.workdir:
            (Path(ctx.workdir) / "silence_cut.json").write_text(
                json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return self.success(outputs)

    def render(self, ctx: ExecContext, params: dict, outputs: dict,
               on_progress=None) -> list:
        media = ctx.media_path
        keep = [(seg["start"], seg["end"]) for seg in outputs.get("cut_time_list", [])]
        if not media or not keep:
            return []
        expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)
        total = sum(e - s for s, e in keep)
        # 容器/编码跟源流一致：音频素材输出 m4a，避免把 AAC 塞进 wav 导致
        # 不同 ffmpeg 版本对容器时长解析不一致（CI 上曾出现时长读成源素材长度）。
        video = analyzer.has_video(media)
        out = Path(ctx.workdir) / f"cut_{Path(media).stem}{'.mp4' if video else '.m4a'}"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-i", media]
        if video:
            cmd += [
                "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",
            ]
        cmd += [
            "-af", f"aselect='{expr}',asetpts=N/SR/TB",
            "-c:a", "aac", "-b:a", "160k",
            "-t", f"{total:.3f}",
            str(out),
        ]
        analyzer.run_cmd(cmd, progress_total=total, on_progress=on_progress)
        return [out]
