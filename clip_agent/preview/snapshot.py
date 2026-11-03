"""结果预览 & 人工干预模块（SDD 模块 5）。

设计原则：所有 AI 输出不直接覆盖原工程，先物化为输出目录中的预览快照
（preview.json + report.md），用户确认应用后才渲染，放弃则原素材不变。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..core.models import ExecutionPlan, ScheduleReport


def _ts(t: float) -> str:
    m, s = divmod(float(t), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:04.1f}" if h else f"{int(m):02d}:{s:04.1f}"


class PreviewSnapshot:
    def __init__(self, workdir) -> None:
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

    def write(self, plan: ExecutionPlan, report: ScheduleReport,
              media: str = None, bgm: str = None) -> Path:
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "media": media,
            "bgm": bgm,
            "plan": {
                "intent": plan.intent,
                "explanation": plan.explanation,
                "source": plan.source,
                "steps": [
                    {"skill_id": s.skill_id, "params": s.params} for s in plan.steps
                ],
            },
            "aborted": report.aborted,
            "error": report.error,
            "results": [
                {
                    "skill_id": r.skill_id,
                    "ok": r.ok,
                    "outputs": r.outputs,
                    "error": r.error,
                    "duration": r.duration,
                }
                for r in report.results
            ],
        }
        (self.workdir / "preview.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report_path = self.workdir / "report.md"
        report_path.write_text(self._render(payload), encoding="utf-8")
        return report_path

    # ---------------------------------------------------------------- 渲染

    def _render(self, payload: dict) -> str:
        p = payload["plan"]
        lines = ["# 剪辑辅助 Agent · 执行预览报告", ""]
        lines.append(f"- 生成时间：{payload['created_at']}")
        lines.append(f"- 意图：{p['intent'] or '未识别'}")
        if p["explanation"]:
            lines.append(f"- 路由说明：{p['explanation']}")
        steps = " → ".join(s["skill_id"] for s in p["steps"]) or "无"
        lines.append(f"- 执行步骤：{steps}")
        lines.append("")
        for r in payload["results"]:
            lines.extend(self._render_result(r))
        if payload["aborted"]:
            lines.append(f"> ⚠ 执行中断：{payload['error']}")
            lines.append("")
        lines.append("---")
        lines.append("*本报告仅为预览，未修改任何原始素材；确认应用前不渲染成片。*")
        return "\n".join(lines)

    def _render_result(self, r: dict) -> list:
        if not r["ok"]:
            return [f"## {r['skill_id']} 执行失败", "", f"失败原因：{r['error']}", ""]
        out = r["outputs"]
        header = f"## {r['skill_id']} 完成（{r['duration']:.2f}s）"
        renderer = {
            "S001": self._r_s1, "S002": self._r_s2, "S003": self._r_s3,
            "S004": self._r_s4, "S005": self._r_s5, "S006": self._r_s6,
        }.get(r["skill_id"])
        body = renderer(out) if renderer else [
            "```json", json.dumps(out, ensure_ascii=False, indent=2), "```"
        ]
        return [header, ""] + body + [""]

    def _r_s1(self, out: dict) -> list:
        sil = out.get("silence_segments", [])
        keep = out.get("cut_time_list", [])
        lines = [
            f"识别静音段 **{len(sil)}** 处（合计 "
            f"{sum(s['duration'] for s in sil):.1f}s），裁切后成片约 "
            f"**{out.get('keep_duration', 0)}s**（原片 {out.get('media_duration', 0)}s）。",
            "",
            "### 需要删除的静音段（可手动在剪映中定位裁剪）",
            "",
            "| # | 开始 | 结束 | 时长 |",
            "|---|---|---|---|",
        ]
        for i, s in enumerate(sil, 1):
            lines.append(
                f"| {i} | {_ts(s['start'])} | {_ts(s['end'])} | {s['duration']}s |"
            )
        lines += ["", "### 保留片段（cut_time_list）", "", "| # | 开始 | 结束 |", "|---|---|---|"]
        for i, s in enumerate(keep, 1):
            lines.append(f"| {i} | {_ts(s['start'])} | {_ts(s['end'])} |")
        lines += ["", "完整时间戳方案：`silence_cut.json`"]
        return lines

    def _r_s2(self, out: dict) -> list:
        issues = out.get("subtitle_issues", [])
        lines = [
            f"共 {out.get('entry_count', 0)} 条字幕，自动修正 **{out.get('issue_count', len(issues))}** 处问题；"
            f"修正后字幕：`fixed.srt`。",
            "",
        ]
        if issues:
            type_label = {
                "punctuation": "标点", "line_wrap": "折行", "overlap": "时间轴重叠",
                "overlap_dropped": "零时长丢弃", "duplicate": "重复字幕",
                "llm_polish": "错别字(模型)", "llm_skipped": "模型降级",
            }
            lines += ["| # | 问题类型 | 修正内容 |", "|---|---|---|"]
            for it in issues:
                label = type_label.get(it["type"], it["type"])
                brief = (it.get("after") or "")[:30].replace("\n", " ")
                lines.append(f"| {it['index']} | {label} | {brief} |")
        lines += [
            "", "统一样式参数：", "```json",
            json.dumps(out.get("style", {}), ensure_ascii=False, indent=2), "```",
        ]
        return lines

    def _r_s3(self, out: dict) -> list:
        segs = out.get("highlight_segments", [])
        lines = [
            f"共切分 {out.get('shot_count', 0)} 个镜头，筛出高光片段 **{len(segs)}** 段"
            f"（合计 {out.get('highlight_total', 0)}s，V1 为启发式评分）。",
            "",
            "| # | 开始 | 结束 | 评分 |",
            "|---|---|---|---|",
        ]
        for i, s in enumerate(segs, 1):
            lines.append(
                f"| {i} | {_ts(s['start'])} | {_ts(s['end'])} | {s['score']} |"
            )
        return lines

    def _r_s4(self, out: dict) -> list:
        plan = out.get("bgm_plan", {})
        mode = {"trim": "裁剪 BGM 尾部", "loop": "循环 BGM 补足时长"}.get(
            plan.get("mode"), "-"
        )
        return [
            f"BGM 原长 {plan.get('bgm_duration')}s，目标时长 {plan.get('target_duration')}s。",
            "",
            f"- 对齐方式：**{mode}**（循环 {plan.get('loops')} 次，尾部裁掉 {plan.get('tail_trim')}s）",
            f"- 尾部淡出：{plan.get('fade_out')}s",
        ]

    def _r_s6(self, out: dict) -> list:
        lines = [
            f"转写后端：{out.get('backend', '-')}（模型 `{out.get('asr_model', '-')}`），"
            f"识别出 **{out.get('segment_count', 0)}** 条字幕；转写字幕：`transcribed.srt`。",
            "",
        ]
        preview = out.get("segments_preview", [])
        if preview:
            lines += ["| # | 开始 | 结束 | 文本 |", "|---|---|---|---|"]
            for i, s in enumerate(preview, 1):
                text = (s.get("text") or "")[:24].replace("\n", " ")
                lines.append(f"| {i} | {_ts(s['start'])} | {_ts(s['end'])} | {text} |")
        return lines

    def _r_s5(self, out: dict) -> list:
        mapping = out.get("jianying_mapping", {})
        lines = [
            f"调色参数来源：{out.get('source_note') or '内联参数'}",
            "",
        ]
        if out.get("compare_image"):
            lines.append(f"调色效果对比图：`{out['compare_image']}`（左：原片帧 ｜ 右：调色后）")
            lines.append("")
        lines += [
            "ffmpeg 滤镜链：",
            "```",
            out.get("filter_chain", ""),
            "```",
            "剪映「调节」面板参数映射：",
            "",
            "| 参数 | 数值 |",
            "|---|---|",
        ]
        for k, v in mapping.items():
            lines.append(f"| {k} | {v} |")
        return lines
