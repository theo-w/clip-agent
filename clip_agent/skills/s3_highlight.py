"""S003 高光镜头识别筛选（V1 启发式：镜头切变节奏 + 瞬时响度评分）。"""
from __future__ import annotations

from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media import analyzer
from .base import Skill


def merge_short_shots(shots: list, min_segment: float) -> list:
    """把时长小于 min_segment 的镜头并入前一个镜头（纯函数，便于单测）。

    注意：判断依据是「当前镜头自身的时长」，而不是距已合并片段起点的距离——
    后者会让长片段把后续所有短镜头错误地吞掉。
    """
    merged = []
    for s, e in shots:
        if merged and (e - s) < min_segment:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


class HighlightSkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S003",
            name="高光镜头识别筛选",
            desc="基于镜头切变与瞬时响度的启发式评分筛选高能量片段（V1 启发式，V1.1 接入多模态模型精排）",
            params={
                "top_n": 5,
                "scene_threshold": 0.3,  # 切变判定阈值
                "min_segment": 1.0,      # 合并过短镜头的最小镜头时长（秒）
            },
            input=["video_timeline", "audio_track"],
            output=["highlight_segments", "highlight_total"],
            triggers=["高光", "精彩", "名场面", "镜头筛选"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        media = ctx.media_path
        if not media:
            return self.fail("缺少视频素材（--media）")
        top_n = int(params.get("top_n", 5))
        scene_threshold = float(params.get("scene_threshold", 0.3))
        min_segment = float(params.get("min_segment", 1.0))

        try:
            total = analyzer.probe_duration(media)
            cuts = analyzer.detect_scene_changes(media, scene_threshold)
            loud = analyzer.loudness_timeline(media)
        except analyzer.MediaToolError as exc:
            return self.fail(str(exc))

        if total <= 0:
            return self.fail("无法读取视频时长")

        # 切变点切分镜头
        boundaries = [0.0] + sorted(c for c in cuts if 0 < c < total) + [total]
        shots = [(s, e) for s, e in zip(boundaries, boundaries[1:]) if e > s]
        if not shots:
            shots = [(0.0, total)]
        merged = merge_short_shots(shots, min_segment)

        # 响度归一化基准
        values = [m for _, m in loud]
        loud_max = max(values) if values else -70.0
        loud_min = min(values) if values else -70.0
        span = max(loud_max - loud_min, 1e-6)

        def mean_loud(s: float, e: float) -> float:
            vals = [m for t, m in loud if s <= t < e]
            return sum(vals) / len(vals) if vals else loud_min

        # 评分：响度（0.7）+ 剪辑节奏（0.3，镜头越短节奏越快）
        scored = []
        for s, e in merged:
            loud_norm = (mean_loud(s, e) - loud_min) / span
            rate = min(1.0 / max(e - s, 1e-6) / 2.0, 1.0)
            scored.append({
                "start": round(s, 3), "end": round(e, 3),
                "score": round(0.7 * loud_norm + 0.3 * rate, 3),
            })

        top = sorted(scored, key=lambda x: -x["score"])[:top_n]
        top.sort(key=lambda x: x["start"])
        return self.success({
            "highlight_segments": top,
            "highlight_total": round(sum(x["end"] - x["start"] for x in top), 3),
            "shot_count": len(merged),
            "media_duration": round(total, 3),
        })
