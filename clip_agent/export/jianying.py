"""剪映草稿导出（V1.2 最小可用版）。

设计分两层：

1. **纯函数层**：从 run 目录的 ``preview.json`` + 产物文件构建 ``DraftPlan``，
   不依赖 pyJianYingDraft，可单测、可在无剪映环境的机器上 dry-run；
2. **写入层**：调用 pyJianYingDraft 生成草稿目录（可选依赖）。

边界（与官方工具能力一致）：
- macOS / Linux 只能生成草稿，**不能自动导出视频**；生成的草稿仍需在 Windows 版剪映中打开导出。
- 调色参数（S005）只写入草稿旁的说明文件，不会自动套用剪映参数。
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..media import analyzer
from ..media.analyzer import parse_srt


class JianyingExportError(Exception):
    """导出失败（缺依赖、缺素材、数据不完整等）。"""


DEPENDENCY_HINT = "需要可选依赖：pip install -e \".[jianying]\""


# ---------------------------------------------------------------- 计划结构

@dataclass
class TimelineClip:
    """时间轴上的一段视频：从源素材 [source_start, source_end] 拼到成片 target_start。"""

    source_start: float
    source_end: float
    target_start: float

    @property
    def duration(self) -> float:
        return round(self.source_end - self.source_start, 3)


@dataclass
class TimelineSubtitle:
    start: float
    end: float
    text: str


@dataclass
class DraftPlan:
    draft_name: str
    media_path: str
    width: int = 1920
    height: int = 1080
    clips: list = field(default_factory=list)
    subtitles: list = field(default_factory=list)
    bgm: dict | None = None
    color: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    @property
    def duration(self) -> float:
        if not self.clips:
            return 0.0
        last = self.clips[-1]
        return round(last.target_start + last.duration, 3)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["duration"] = self.duration
        return data


# ---------------------------------------------------------------- 纯函数层

def _find_outputs(preview: dict, skill_id: str) -> dict:
    for result in preview.get("results") or []:
        if result.get("skill_id") == skill_id and result.get("ok"):
            return result.get("outputs") or {}
    return {}


def _media_duration(preview: dict) -> float | None:
    for skill_id in ("S001", "S003"):
        value = _find_outputs(preview, skill_id).get("media_duration")
        if value:
            return float(value)
    return None


def _build_clips(preview: dict, media_duration: float | None) -> list:
    # 优先 S001 静音裁剪结果；没有时退用 S003 高光片段；再没有则整段素材
    spans = _find_outputs(preview, "S001").get("cut_time_list") or []
    if not spans:
        spans = _find_outputs(preview, "S003").get("highlight_segments") or []
    clips = []
    cursor = 0.0
    for seg in spans:
        start, end = float(seg["start"]), float(seg["end"])
        if end - start <= 0:
            continue
        clips.append(TimelineClip(round(start, 3), round(end, 3), round(cursor, 3)))
        cursor += end - start
    if clips:
        return clips
    duration = media_duration or 0.0
    if duration <= 0:
        raise JianyingExportError(
            "无法确定素材时长：该 run 没有 S001 裁剪结果，也没有 media_duration。"
            "请用 --media 指定素材并在导出时提供 --duration。"
        )
    return [TimelineClip(0.0, round(duration, 3), 0.0)]


def _map_subtitles(entries: list, clips: list) -> list:
    """把原始时间轴上的字幕映射到拼接后的成片时间轴（跨裁剪点自动裁切/跳过）。"""
    if not clips:
        return [TimelineSubtitle(round(e.start, 3), round(e.end, 3), e.text) for e in entries]
    mapped = []
    for entry in entries:
        for clip in clips:
            start = max(entry.start, clip.source_start)
            end = min(entry.end, clip.source_end)
            if end - start < 0.05:
                continue
            offset = start - clip.source_start
            mapped.append(TimelineSubtitle(
                round(clip.target_start + offset, 3),
                round(clip.target_start + offset + (end - start), 3),
                entry.text,
            ))
    mapped.sort(key=lambda s: s.start)
    return mapped


def _build_subtitles(preview: dict, workdir: Path, clips: list) -> tuple[list, list]:
    warnings = []
    outputs = _find_outputs(preview, "S002")
    srt_path = outputs.get("fixed_subtitle") or outputs.get("subtitle_path") or ""
    if not srt_path or not Path(srt_path).exists():
        warnings.append("未找到字幕产物（S002），草稿不含字幕轨")
        return [], warnings
    try:
        entries = parse_srt(srt_path)
    except Exception as exc:  # noqa: BLE001 - 预览产物可能来自任意运行，坏文件要降级
        warnings.append(f"字幕解析失败，草稿不含字幕轨：{exc}")
        return [], warnings
    return _map_subtitles(entries, clips), warnings


def _build_bgm(preview: dict, workdir: Path, bgm: str | None, duration: float) -> dict | None:
    aligned = workdir / "bgm_aligned.m4a"
    if aligned.exists():
        return {"path": str(aligned), "start": 0.0, "end": duration, "note": "S004 对齐后的 BGM"}
    if bgm:
        return {"path": str(Path(bgm)), "start": 0.0, "end": duration, "note": "原始 BGM（未对齐）"}
    return None


def _build_color(preview: dict) -> dict:
    outputs = _find_outputs(preview, "S005")
    if not outputs:
        return {}
    return {
        "color_params": outputs.get("color_params") or {},
        "jianying_mapping": outputs.get("jianying_mapping") or {},
        "source_note": outputs.get("source_note") or "",
        "note": "调色仅记录参数（等价剪映参数见 jianying_mapping），草稿不自动套用",
    }


def build_draft_plan(
    preview: dict,
    workdir,
    media: str | None = None,
    *,
    bgm: str | None = None,
    draft_name: str = "",
    width: int = 1920,
    height: int = 1080,
    duration: float | None = None,
) -> DraftPlan:
    """从预览数据构建草稿计划（不依赖 pyJianYingDraft）。"""
    workdir = Path(workdir)
    media_path = str(media or preview.get("media") or "")
    if not media_path:
        raise JianyingExportError("缺少原始素材路径：请用 --media 指定该次运行使用的素材")
    if not Path(media_path).exists():
        raise JianyingExportError(f"原始素材不存在：{media_path}")

    media_duration = duration or _media_duration(preview) or None
    clips = _build_clips(preview, media_duration)
    subtitles, warnings = _build_subtitles(preview, workdir, clips)
    plan_duration = round(clips[-1].target_start + clips[-1].duration, 3)
    return DraftPlan(
        draft_name=draft_name or f"clip_agent_{workdir.name}",
        media_path=media_path,
        width=width,
        height=height,
        clips=clips,
        subtitles=subtitles,
        bgm=_build_bgm(preview, workdir, bgm, plan_duration),
        color=_build_color(preview),
        warnings=warnings,
    )


# ---------------------------------------------------------------- 写入层

def _import_draft_module():
    import pyJianYingDraft  # noqa: PLC0415 - 可选依赖，按需导入
    return pyJianYingDraft


def _has_optional_dependency() -> bool:
    try:
        _import_draft_module()
    except ImportError:
        return False
    return True


def _load_draft_module():
    try:
        return _import_draft_module()
    except ImportError as exc:
        raise JianyingExportError(
            f"未安装 pyJianYingDraft（剪映草稿生成）。{DEPENDENCY_HINT}"
        ) from exc


def _has_video(path: str) -> bool:
    try:
        return analyzer.has_video(path)
    except analyzer.MediaToolError as exc:
        raise JianyingExportError(f"无法读取素材流信息：{exc}") from exc


def _has_video_quiet(path: str) -> bool:
    try:
        return analyzer.has_video(path)
    except analyzer.MediaToolError:
        return True


def _fmt_srt_time(seconds: float) -> str:
    ms = int(round(max(seconds, 0.0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(subtitles: list, path: Path) -> None:
    blocks = []
    for index, sub in enumerate(subtitles, 1):
        text = sub.text.strip()
        if not text:
            continue
        blocks.append(
            f"{len(blocks) + 1}\n"
            f"{_fmt_srt_time(sub.start)} --> {_fmt_srt_time(sub.end)}\n{text}"
        )
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def write_draft(plan: DraftPlan, out_dir, *, replace: bool = False) -> Path:
    """把草稿计划写入剪映草稿根目录，返回新草稿目录。"""
    draft = _load_draft_module()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not Path(plan.media_path).exists():
        raise JianyingExportError(f"原始素材不存在：{plan.media_path}")

    script = draft.DraftFolder(str(out)).create_draft(
        plan.draft_name, plan.width, plan.height, allow_replace=replace
    )
    # 同一素材只建一个材质实例，避免生成重复素材；音频素材单独走原声轨
    video_mode = _has_video(plan.media_path)
    track_type = draft.TrackType.video if video_mode else draft.TrackType.audio
    track_name = "剪辑轨" if video_mode else "原声轨"
    script.append_track(draft.TrackSpec(track_type, track_name))
    material_cls = draft.VideoMaterial if video_mode else draft.AudioMaterial
    try:
        material = material_cls(plan.media_path)
    except (ValueError, OSError) as exc:
        raise JianyingExportError(f"无法读取素材流信息：{exc}") from exc
    for clip in plan.clips:
        segment_cls = draft.VideoSegment if video_mode else draft.AudioSegment
        segment = segment_cls(
            material,
            draft.trange_seconds(clip.target_start, duration=clip.duration),
            source_timerange=draft.trange_seconds(clip.source_start, duration=clip.duration),
        )
        script.add_segment(segment, track_name)

    if plan.bgm:
        if not Path(plan.bgm["path"]).exists():
            raise JianyingExportError(f"BGM 素材不存在：{plan.bgm['path']}")
        script.append_track(draft.TrackSpec(draft.TrackType.audio, "BGM轨"))
        audio = draft.AudioSegment(
            plan.bgm["path"],
            draft.trange_seconds(plan.bgm["start"], duration=plan.bgm["end"] - plan.bgm["start"]),
        )
        script.add_segment(audio, "BGM轨")

    if plan.subtitles:
        with tempfile.TemporaryDirectory(prefix="clip_agent_srt_") as tmp:
            srt_path = Path(tmp) / "subtitles.srt"
            _write_srt(plan.subtitles, srt_path)
            script.import_srt(str(srt_path), track_name="字幕")

    script.save()
    # 调色参数等说明与计划留档，方便人工在剪映里复核
    (out / f"{plan.draft_name}.clip_agent.json").write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out / plan.draft_name


# ---------------------------------------------------------------- 自检/展示

def describe_plan(plan: DraftPlan) -> list:
    lines = [
        f"草稿：{plan.draft_name}（{plan.width}x{plan.height}，成片 {plan.duration:.3f}s）",
        f"素材：{plan.media_path}",
        f"{'视频轨' if _has_video_quiet(plan.media_path) else '原声轨'}：{len(plan.clips)} 段",
    ]
    for index, clip in enumerate(plan.clips, 1):
        lines.append(
            f"  {index}. 源 {clip.source_start:.3f}-{clip.source_end:.3f}s"
            f" → 时间轴 {clip.target_start:.3f}s"
        )
    lines.append(f"字幕轨：{len(plan.subtitles)} 条")
    lines.append(f"BGM 轨：{'有（' + plan.bgm['note'] + '）' if plan.bgm else '无'}")
    if plan.color:
        mapping = plan.color.get("jianying_mapping") or {}
        lines.append(
            f"调色（仅记录，不自动套用）：{json.dumps(mapping, ensure_ascii=False)}"
            if mapping else "调色：仅记录参数"
        )
    for warning in plan.warnings:
        lines.append(f"⚠ {warning}")
    return lines
