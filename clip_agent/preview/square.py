"""资产广场 HTML（P2 发现机制的本地可视化形态，零依赖自包含样式）。

输出：output/square.html —— 质量分排行、来源标识、复用/收藏/导入信号、标签。
所有资产文本一律 HTML 转义；样式复用 preview/html_report.py，保持报告视觉一致。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..assets.discovery import AssetInsight
from .html_report import _STYLE as STYLE
from .html_report import _esc as esc

_TYPE_LABELS = {
    "color_preset": "调色预设",
    "subtitle_template": "字幕模板",
    "skill_combo": "组合方案",
}

_SQUARE_EXTRA_STYLE = """
.score { font-variant-numeric: tabular-nums; font-weight: 600; }
.score-bar { width: 120px; background: #eef2f7; border-radius: 999px; height: 8px;
  overflow: hidden; margin-top: 4px; }
.score-fill { height: 100%; border-radius: 999px; background: #60a5fa; }
.score-fill.high { background: #22c55e; }
.score-fill.low { background: #94a3b8; }
.tag { display: inline-block; padding: 1px 8px; margin: 1px 2px; border-radius: 999px;
  background: #f1f4fa; color: #475569; font-size: 12px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
th.num { text-align: right; }
"""


def _score_kind(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return ""
    return "low"


def _badge_kind(badge: str) -> str:
    return {"官方精选": "ok", "社区热门": "info"}.get(badge, "muted")


def _row_html(rank_no: int, insight: AssetInsight) -> str:
    asset = insight.asset
    score = insight.score
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in asset.tags) or "—"
    type_label = _TYPE_LABELS.get(asset.asset_type, asset.asset_type)
    return (
        "<tr>"
        f'<td class="num">{rank_no}</td>'
        f'<td><div class="score">{score:.1f}</div>'
        f'<div class="score-bar"><div class="score-fill {_score_kind(score)}" '
        f'style="width:{min(score, 100):.1f}%"></div></div></td>'
        f"<td><div>{esc(asset.name)}</div>"
        f'<div class="caption">{esc(asset.asset_id)} · {esc(type_label)} · v{asset.version}</div></td>'
        f"<td><span class=\"badge {_badge_kind(insight.badge)}\">{esc(insight.badge)}</span></td>"
        f'<td class="num">{insight.reuse}</td>'
        f'<td class="num">{insight.weekly_reuse}</td>'
        f'<td class="num">{asset.favorites}</td>'
        f'<td class="num">{asset.installs}</td>'
        f"<td>{tags}</td>"
        "</tr>"
    )


def write_square_html(insights: list, out_path, weekly_reused: int,
                      now: datetime = None) -> Path:
    """生成资产广场页面并返回路径。"""
    out = Path(out_path)
    now = now or datetime.now()
    total_reuse = sum(i.materials for i in insights)
    featured = sum(1 for i in insights if i.badge == "官方精选")
    rows = "".join(
        _row_html(idx, insight) for idx, insight in enumerate(insights, start=1)
    ) or '<tr><td colspan="9">暂无资产</td></tr>'

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>创作资产广场</title>
<style>{STYLE}{_SQUARE_EXTRA_STYLE}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>创作资产广场</h1>
    <div class="meta">
      <div>生成时间：{esc(now.strftime('%Y-%m-%d %H:%M:%S'))}</div>
      <div>资产总数 {len(insights)} · 本周复用资产 {weekly_reused} · 官方精选 {featured} · 累计复用素材 {total_reuse}</div>
    </div>
  </header>
  <div class="card">
    <h2>质量分排行</h2>
    <div class="sub">质量分 = 50%×去重素材复用 + 30%×收藏 + 20%×导入（各维度封顶）；同一素材重复复用只计一次</div>
    <table>
      <thead>
        <tr>
          <th class="num">#</th><th>质量分</th><th>资产</th><th>来源</th>
          <th class="num">复用素材</th><th class="num">本周复用</th>
          <th class="num">收藏</th><th class="num">导入</th><th>标签</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <p class="note">数据来自本机资产库与埋点（data/assets.json、data/metrics.jsonl）；
  「复用素材」按不同素材去重，防止同一素材重复应用刷分。在线广场与跨设备榜单需要平台承载，此处为本地先行版。</p>
</div>
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    return out
