"""数据采集 & 评测模块（SDD 模块 6）：调用链路埋点 + 效果报表。

埋点事件（JSONL 追加写入 data/metrics.jsonl）：
- skill_run：Skill 调用、耗时、成败、错误信息
- decision：用户决策（adopted 采纳 / modified 修改重跑 / discarded 放弃）
- asset：资产动作（save 保存 / use 复用 / favorite 收藏 / export 导出 / import 导入）
  其中 use 事件可带 material（素材名），供资产广场按独立素材去重计分

报表输出 SDD 6.1 定义的三大类指标：效率 / 质量 / 生态。
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from ..core.models import SkillResult
from ..paths import data_dir


def default_metrics_path() -> Path:
    return data_dir() / "metrics.jsonl"


class MetricsTracker:
    def __init__(self, path: Path = None) -> None:
        self.path = Path(path) if path else default_metrics_path()

    # ---------------------------------------------------------------- 埋点

    def _append(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def track_skill_run(self, result: SkillResult) -> None:
        self._append({
            "type": "skill_run",
            "skill_id": result.skill_id,
            "ok": result.ok,
            "duration": result.duration,
            "error": result.error,
        })

    def track_decision(self, skill_ids: list, outcome: str, note: str = "") -> None:
        self._append({
            "type": "decision",
            "skill_ids": skill_ids,
            "outcome": outcome,  # adopted | modified | discarded
            "note": note,
        })

    def track_asset(self, action: str, asset_id: str, material: str = "") -> None:
        event = {
            "type": "asset",
            "action": action,  # save | use | favorite | rollback | export | import
            "asset_id": asset_id,
        }
        # 复用事件记录素材名，供资产广场按「独立素材」去重计分（防同一素材刷复用）
        if material:
            event["material"] = material
        self._append(event)

    # ---------------------------------------------------------------- 报表

    def load_events(self) -> list:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def report(self) -> dict:
        runs = defaultdict(lambda: {"count": 0, "ok": 0, "total_duration": 0.0})
        decisions = {"adopted": 0, "modified": 0, "discarded": 0}
        assets = defaultdict(int)
        for ev in self.load_events():
            etype = ev.get("type")
            if etype == "skill_run":
                v = runs[ev["skill_id"]]
                v["count"] += 1
                v["total_duration"] += ev.get("duration", 0) or 0
                if ev.get("ok"):
                    v["ok"] += 1
            elif etype == "decision":
                outcome = ev.get("outcome")
                if outcome in decisions:
                    decisions[outcome] += 1
            elif etype == "asset":
                assets[ev.get("action", "")] += 1
        return {
            "skills": {
                sid: {
                    "调用次数": v["count"],
                    "成功率": round(v["ok"] / v["count"], 3) if v["count"] else 0,
                    "平均耗时(s)": round(v["total_duration"] / v["count"], 3)
                    if v["count"] else 0,
                }
                for sid, v in runs.items()
            },
            "decisions": decisions,
            "assets": dict(assets),
        }

    def render_report_md(self) -> str:
        data = self.report()
        lines = ["# 剪辑辅助 Agent · 评测报表", ""]

        lines += ["## 一、效率指标", "", "| Skill | 调用次数 | 平均耗时(s) |", "|---|---|---|"]
        for sid, v in data["skills"].items():
            lines.append(f"| {sid} | {v['调用次数']} | {v['平均耗时(s)']} |")
        if not data["skills"]:
            lines.append("| - | 暂无数据 | - |")

        dec = data["decisions"]
        total_dec = dec["adopted"] + dec["modified"] + dec["discarded"]
        lines += ["", "## 二、质量指标", ""]
        for sid, v in data["skills"].items():
            lines.append(f"- {sid} 成功率：{v['成功率']:.0%}")
        if total_dec:
            lines.append(f"- 结果采纳率：{dec['adopted']}/{total_dec}（{dec['adopted'] / total_dec:.0%}）")
            lines.append(f"- 二次修改率：{dec['modified']}/{total_dec}（{dec['modified'] / total_dec:.0%}）")
            lines.append(f"- 放弃率：{dec['discarded']}/{total_dec}（{dec['discarded'] / total_dec:.0%}）")
        else:
            lines.append("- 用户决策：暂无数据")

        asset = data["assets"]
        lines += ["", "## 三、生态指标", ""]
        lines.append(f"- 资产保存：{asset.get('save', 0)} 次")
        lines.append(f"- 资产复用：{asset.get('use', 0)} 次")
        lines.append(f"- 资产收藏：{asset.get('favorite', 0)} 次")
        lines.append(f"- 资产导出/导入：{asset.get('export', 0)} / {asset.get('import', 0)} 次（V1.1 流通）")

        if not data["skills"] and not total_dec and not any(asset.values()):
            lines += ["", "（暂无埋点数据，先跑几次 `clip-agent run` 再来看报表）"]
        return "\n".join(lines)
