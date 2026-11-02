"""S002 字幕批量校对、样式统一。"""
from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from ..core.llm import chat, is_available
from ..core.models import ExecContext, SkillMeta, SkillResult
from ..media.analyzer import SubtitleEntry, parse_srt
from .base import Skill

DEFAULT_STYLE = {
    "font": "思源黑体 CN Medium",
    "font_size": 5,           # 剪映字幕字号档位
    "color": "#FFFFFF",
    "stroke": 0.5,            # 描边粗细
    "position": "底部居中",
}

_CJK = r"一-鿿"


def _is_mostly_ascii(text: str) -> bool:
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars > len(text) * 0.7


def _fix_punctuation(text: str) -> str:
    """中文语境的半角标点全角化；英文/数字为主的行不做处理。"""
    if _is_mostly_ascii(text):
        return text
    # 仅转换紧邻中文字符的半角标点，避免破坏数字、英文与网址
    text = re.sub(rf"(?<=[{_CJK}])\.(?!\d)", "。", text)
    text = re.sub(rf"(?<=[{_CJK}]),", "，", text)
    text = re.sub(rf"(?<=[{_CJK}])\?", "？", text)
    text = re.sub(rf"(?<=[{_CJK}])!", "！", text)
    text = re.sub(rf"(?<=[{_CJK}]);", "；", text)
    # 去掉全角标点两侧的多余空格
    text = re.sub(r"\s*([，。？！；])\s*", r"\1", text)
    return text


def _split_line(line: str, max_chars: int) -> list:
    """超长行折行：优先在中点附近的标点处切，找不到就硬切；最多两行。

    两行上限是字幕渲染的硬约束——极长句宁可单行略超宽，也不能折出第三行。
    """
    if len(line) <= max_chars:
        return [line]
    mid = len(line) // 2
    candidates = [m.start() + 1 for m in re.finditer(r"[，。？！；,.!?]", line)]
    # 保证两行都 ≤ max_chars 的可行切点窗口
    lo = max(1, len(line) - max_chars)
    hi = min(max_chars, len(line) - 1)
    valid = [p for p in candidates if lo <= p <= hi]
    if valid:
        cut = min(valid, key=lambda p: abs(p - mid))
    elif lo <= hi:
        cut = min(max(mid, lo), hi)  # 窗口内无标点：在窗口内硬切，两行仍不超宽
    else:
        cut = mid  # 总长 > 2×max_chars：保两行上限，单行可能略超宽
    left, right = line[:cut].strip(), line[cut:].strip()
    if not left or not right:
        return [line]
    return [left, right]


def fix_entries(entries: list, params: dict):
    """规则修正主流程（纯函数，便于单测）：标点、折行、重叠、重复。"""
    max_chars = int(params.get("max_line_chars", 18))
    fix_overlap = bool(params.get("fix_overlap", True))
    dedupe = bool(params.get("dedupe", True))
    issues = []
    result = []

    for entry in entries:
        original = entry.text
        text = _fix_punctuation(entry.text)
        punct_changed = text != entry.text

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        wrapped = []
        for line in lines:
            wrapped.extend(_split_line(line, max_chars))
        new_text = "\n".join(wrapped)
        wrap_changed = new_text != "\n".join(lines)

        new_entry = replace(entry, text=new_text)

        # 连续重复（口播结巴 / 重复导入）
        if dedupe and result and new_text == result[-1].text \
                and new_entry.start - result[-1].end < 1.5:
            issues.append({
                "index": entry.index, "type": "duplicate",
                "before": original, "after": "（已删除）",
            })
            continue

        # 时间轴重叠
        if result and new_entry.start < result[-1].end:
            after = (f"对齐到 {result[-1].end:.2f}s" if fix_overlap else "仅报告")
            issues.append({
                "index": entry.index, "type": "overlap",
                "before": f"起始 {new_entry.start:.2f}s 与上一条结束重叠",
                "after": after,
            })
            if fix_overlap:
                new_entry = replace(new_entry, start=result[-1].end)
                if new_entry.end <= new_entry.start:
                    issues.append({
                        "index": entry.index, "type": "overlap_dropped",
                        "before": original, "after": "（时长为零，已删除）",
                    })
                    continue

        if punct_changed:
            issues.append({
                "index": entry.index, "type": "punctuation",
                "before": original, "after": new_text,
            })
        if wrap_changed:
            issues.append({
                "index": entry.index, "type": "line_wrap",
                "before": original, "after": new_text,
            })

        result.append(new_entry)

    result = [replace(e, index=i + 1) for i, e in enumerate(result)]
    return result, issues


def _llm_polish(texts: list):
    """可选的本地模型错别字润色；失败返回 None（降级为纯规则结果）。"""
    try:
        numbered = "\n".join(
            f"{i}. {t.replace(chr(10), ' / ')}" for i, t in enumerate(texts, 1)
        )
        system = (
            "你是短视频字幕校对员。修正每条字幕中的错别字与明显语病，"
            "保持口语风格、语义与长度基本不变，不要增删内容。"
            "只输出一个 JSON 字符串数组（顺序与输入一致），不要输出其他文字。"
        )
        resp = chat(system, numbered, temperature=0.1)
        start, end = resp.find("["), resp.rfind("]")
        if start < 0 or end <= start:
            return None
        data = json.loads(resp[start : end + 1])
        if isinstance(data, list) and len(data) == len(texts):
            return [str(x) for x in data]
    except Exception:
        return None
    return None


def _fmt_time(t: float) -> str:
    ms = max(int(round(t * 1000)), 0)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(path, entries: list) -> None:
    blocks = [
        f"{e.index}\n{_fmt_time(e.start)} --> {_fmt_time(e.end)}\n{e.text}\n"
        for e in entries
    ]
    Path(path).write_text("\n".join(blocks), encoding="utf-8")


class SubtitleFixSkill(Skill):
    def __init__(self) -> None:
        self.meta = SkillMeta(
            skill_id="S002",
            name="字幕批量校对与样式统一",
            desc="解析 SRT，规则修正标点/折行/时间轴重叠/连续重复，统一样式参数，可选本地模型错别字润色",
            params={
                "style": DEFAULT_STYLE,
                "max_line_chars": 18,
                "fix_overlap": True,
                "dedupe": True,
                "llm_polish": False,
            },
            input=["subtitle_text"],
            output=["fixed_subtitle", "subtitle_issues"],
            triggers=["字幕", "错别字", "校对", "样式统一"],
        )

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        if not ctx.subtitle_path:
            return self.fail("缺少字幕素材（--subtitle 指定 SRT 文件）")
        try:
            entries = parse_srt(ctx.subtitle_path)
        except Exception as exc:
            return self.fail(f"字幕解析失败：{exc}")
        if not entries:
            return self.fail("字幕内容为空或格式不正确")

        fixed, issues = fix_entries(entries, params)

        if params.get("llm_polish") and is_available():
            polished = _llm_polish([e.text for e in fixed])
            if polished is None:
                issues.append({
                    "index": 0, "type": "llm_skipped",
                    "before": "本地模型润色", "after": "失败或格式异常，已降级为纯规则结果",
                })
            else:
                new_fixed = []
                for e, p in zip(fixed, polished):
                    if p and p != e.text:
                        issues.append({
                            "index": e.index, "type": "llm_polish",
                            "before": e.text, "after": p,
                        })
                        e = replace(e, text=p)
                    new_fixed.append(e)
                fixed = new_fixed

        out_path = Path(ctx.workdir) / "fixed.srt"
        write_srt(out_path, fixed)
        return self.success({
            "fixed_subtitle": str(out_path),
            "subtitle_issues": issues,
            "issue_count": len(issues),
            "entry_count": len(entries),
            "style": params.get("style") or DEFAULT_STYLE,
        })

    def render(self, ctx: ExecContext, params: dict, outputs: dict) -> list:
        path = outputs.get("fixed_subtitle")
        return [Path(path)] if path and Path(path).exists() else []
