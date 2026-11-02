"""S005 批量调色参数套用。"""
from __future__ import annotations

from pathlib import Path

from ..assets.library import AssetLibrary, AssetNotFoundError
from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media import analyzer
from .base import Skill

# ffmpeg 参数安全范围（越界自动裁剪）
_PARAM_RANGES = {
    "brightness": (-1.0, 1.0),
    "contrast": (0.5, 2.0),
    "saturation": (0.0, 3.0),
    "gamma": (0.1, 10.0),
    "temperature": (-1.0, 1.0),
}


def build_filter_chain(color: dict) -> str:
    """调色参数 → ffmpeg 滤镜链（纯函数，便于单测）。"""
    eq = [
        f"{k}={float(color[k]):.3f}"
        for k in ("brightness", "contrast", "saturation", "gamma")
        if k in color
    ]
    parts = [f"eq={':'.join(eq)}"] if eq else []
    if "temperature" in color:
        t = float(color["temperature"])
        parts.append(f"colorbalance=rs={t * 0.2:.3f}:bs={-t * 0.2:.3f}")
    return ",".join(parts)


def jianying_mapping(color: dict) -> dict:
    """ffmpeg 参数 → 剪映「调节」面板数值映射（纯函数）。"""
    m = {}
    if "brightness" in color:
        m["亮度"] = round(float(color["brightness"]) * 100)
    if "contrast" in color:
        m["对比度"] = round((float(color["contrast"]) - 1) * 100)
    if "saturation" in color:
        m["饱和度"] = round((float(color["saturation"]) - 1) * 100)
    if "temperature" in color:
        m["色温"] = round(float(color["temperature"]) * 100)
    if "gamma" in color:
        m["伽马"] = round((float(color["gamma"]) - 1) * 100)
    return m


class ColorApplySkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S005",
            name="批量调色参数套用",
            desc="从创作资产库读取调色预设（或内联参数），生成 ffmpeg 滤镜链，输出剪映调节面板参数映射",
            params={
                "asset_id": "",
                "brightness": 0.0,
                "contrast": 1.0,
                "saturation": 1.0,
                "gamma": 1.0,
                "temperature": 0.0,
            },
            input=["video_timeline"],
            output=["color_params", "filter_chain"],
            triggers=["调色", "色彩", "滤镜", "预设", "LUT", "lut"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        media = ctx.media_path
        if not media:
            return self.fail("缺少视频素材（--media）")

        # 参数来源：资产库预设 > 内联参数
        color = {}
        source_note = ""
        asset_id = str(params.get("asset_id") or "")
        if asset_id:
            try:
                asset = AssetLibrary().get(asset_id)
            except AssetNotFoundError:
                return self.fail(f"资产库中不存在调色预设：{asset_id}")
            color = {k: v for k, v in asset.params.items() if k in _PARAM_RANGES}
            source_note = f"资产库预设「{asset.name}」v{asset.version}"
        for key in _PARAM_RANGES:
            if key in params and params[key] != self.meta.params.get(key):
                color[key] = params[key]
        if not color:
            return self.fail("未指定调色参数（--asset 资产 ID，或 --set brightness=0.1 等）")

        # 参数校验与范围裁剪
        for key, (lo, hi) in _PARAM_RANGES.items():
            if key in color:
                try:
                    color[key] = max(lo, min(hi, float(color[key])))
                except (TypeError, ValueError):
                    return self.fail(f"参数 {key} 不是数值：{color[key]}")

        chain = build_filter_chain(color)
        if not chain:
            return self.fail("有效调色参数为空")
        return self.success({
            "color_params": {k: round(float(v), 3) for k, v in color.items()},
            "filter_chain": chain,
            "jianying_mapping": jianying_mapping(color),
            "source_note": source_note,
        })

    def render(self, ctx: ExecContext, params: dict, outputs: dict) -> list:
        media = ctx.media_path
        chain = outputs.get("filter_chain")
        if not media or not chain:
            return []
        out = Path(ctx.workdir) / f"graded_{Path(media).name}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-i", media,
            "-vf", chain,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
        ]
        cmd += ["-c:a", "copy"] if analyzer.has_audio(media) else []
        cmd.append(str(out))
        analyzer.run_cmd(cmd)
        return [out]
