"""S004 音频 BGM 时长对齐。"""
from __future__ import annotations

from pathlib import Path

from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media import analyzer
from .base import Skill


def make_align_plan(bgm_dur: float, target: float) -> dict:
    """对齐方案计算（纯函数，便于单测）。"""
    if bgm_dur >= target:
        return {"mode": "trim", "loops": 1, "tail_trim": round(bgm_dur - target, 3)}
    loops = int(target // bgm_dur) + (1 if target % bgm_dur else 0)
    return {"mode": "loop", "loops": loops, "tail_trim": round(loops * bgm_dur - target, 3)}


class BgmAlignSkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S004",
            name="音频 BGM 时长对齐",
            desc="将 BGM 时长与目标时长（高光片段总长或成片时长）对齐：裁剪或循环，尾部长淡出",
            params={
                "fade_out": 2.0,     # 尾部淡出（秒）
                "trim_start": 0.0,   # BGM 起始裁剪点（秒）
            },
            input=["bgm_track"],
            output=["bgm_plan"],
            triggers=["BGM", "bgm", "背景音乐", "卡点", "对齐"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        if not ctx.bgm_path:
            return self.fail("缺少 BGM 素材（--bgm）")
        try:
            bgm_dur = analyzer.probe_duration(ctx.bgm_path)
        except analyzer.MediaToolError as exc:
            return self.fail(str(exc))

        # 目标时长优先级：上游高光片段总长 > 成片时长
        target = ctx.get("highlight_total")
        if not target:
            if ctx.media_path:
                try:
                    target = analyzer.probe_duration(ctx.media_path)
                except analyzer.MediaToolError as exc:
                    return self.fail(str(exc))
            else:
                return self.fail("无法确定目标时长：既无高光片段也无成片素材")

        plan = make_align_plan(bgm_dur, float(target))
        plan["fade_out"] = float(params.get("fade_out", 2.0))
        plan["trim_start"] = float(params.get("trim_start", 0.0))
        plan["bgm_duration"] = round(bgm_dur, 3)
        plan["target_duration"] = round(float(target), 3)
        return self.success({"bgm_plan": plan})

    def render(self, ctx: ExecContext, params: dict, outputs: dict) -> list:
        plan = outputs.get("bgm_plan")
        if not ctx.bgm_path or not plan:
            return []
        fade = float(plan.get("fade_out", 2.0))
        target = float(plan["target_duration"])
        out = Path(ctx.workdir) / "bgm_aligned.m4a"
        cmd = ["ffmpeg", "-y", "-hide_banner"]
        if plan["mode"] == "loop" and plan["loops"] > 1:
            cmd += ["-stream_loop", str(plan["loops"] - 1)]
        cmd += ["-i", ctx.bgm_path]
        if plan.get("trim_start"):
            cmd += ["-ss", str(plan["trim_start"])]
        cmd += ["-t", str(target)]
        fade_start = max(target - fade, 0)
        if fade_start > 0:
            cmd += ["-af", f"afade=t=out:st={fade_start:.3f}:d={fade:.3f}"]
        cmd += ["-c:a", "aac", "-b:a", "192k", str(out)]
        analyzer.run_cmd(cmd)
        return [out]
