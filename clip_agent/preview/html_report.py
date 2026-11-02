"""HTML 预览报告（零依赖、自包含样式，SDD 模块 5 的可视化形态）。

- 每次运行：output/run_*/report.html —— 意图、步骤、各 Skill 结果、调色对比图、产物链接；
- 评测仪表盘：output/report.html —— 效率/质量/生态指标 + 最近运行列表。

所有外部数据一律 HTML 转义，避免指令/字幕文本注入。
"""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from ..core.models import ExecutionPlan, ScheduleReport

# 输出目录中的产物 → 展示名
_ARTIFACT_LABELS = {
    "cut_demo.mp4": "静音裁剪成片",
    "fixed.srt": "校对后字幕",
    "transcribed.srt": "转写字幕",
    "bgm_aligned.m4a": "BGM 对齐音频",
    "graded_demo.mp4": "调色成片",
    "compare.jpg": "调色对比图",
    "silence_cut.json": "静音时间戳方案",
}
_SKIP_FILES = {"report.md", "report.html", "preview.json", "asr_input.wav"}

_DECISION_LABELS = {
    "adopted": ("已采纳", "ok"),
    "previewed": ("仅预览", "info"),
    "discarded": ("已放弃", "muted"),
    "failed": ("执行中断", "bad"),
    "": ("预览中", "info"),
}

_STYLE = """
:root {
  --bg: #f5f7fb; --card: #ffffff; --text: #17223b; --muted: #5b6784;
  --border: #e6eaf2; --accent: #335cff;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 40px 20px 64px; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
    "Microsoft YaHei", sans-serif; line-height: 1.65;
}
.wrap { max-width: 960px; margin: 0 auto; }
header { margin-bottom: 24px; }
h1 { font-size: 26px; margin: 0 0 6px; letter-spacing: .2px; }
.meta { color: var(--muted); font-size: 14px; }
.meta div { margin-top: 2px; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  padding: 22px 24px; margin-top: 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04);
  overflow-x: auto;
}
.card h2 { font-size: 18px; margin: 0 0 4px; }
.card .sub { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.badge {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600; vertical-align: middle; margin-left: 8px;
}
.badge.ok { color: #15803d; background: #e8f7ee; }
.badge.info { color: #1d4ed8; background: #e8f0ff; }
.badge.muted { color: #475569; background: #eef2f6; }
.badge.bad { color: #b91c1c; background: #feeceb; }
table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 8px 0 4px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 600; background: #f8fafd; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
code, pre {
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 13px;
  background: #f6f8fc; border: 1px solid var(--border); border-radius: 8px;
}
code { padding: 1px 6px; }
pre { padding: 12px 14px; overflow-x: auto; }
.compare { width: 100%; border-radius: 10px; border: 1px solid var(--border); margin-top: 6px; }
.caption { color: var(--muted); font-size: 13px; margin-top: 4px; }
.files { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
.files a {
  display: inline-block; padding: 8px 14px; border: 1px solid var(--border);
  border-radius: 10px; background: #fbfcff; color: var(--accent); text-decoration: none;
  font-size: 14px;
}
.files a:hover { background: #eef2ff; }
.files a span { color: var(--muted); font-weight: 400; margin-left: 6px; font-size: 12px; }
.note { color: var(--muted); font-size: 13px; margin-top: 24px; }
.error { color: #b91c1c; }
.bar-row { display: flex; align-items: center; gap: 12px; margin: 8px 0; font-size: 14px; }
.bar-label { width: 96px; color: var(--muted); flex: none; }
.bar-track { flex: 1; background: #eef2f7; border-radius: 999px; height: 10px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; }
.bar-fill.ok { background: #22c55e; }
.bar-fill.info { background: #60a5fa; }
.bar-fill.muted { background: #94a3b8; }
.bar-val { width: 110px; flex: none; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.runs { list-style: none; padding: 0; margin: 8px 0 0; }
.runs li { padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
.runs li:last-child { border-bottom: 0; }
.runs a { color: var(--accent); text-decoration: none; }
.runs .when { color: var(--muted); font-size: 12px; margin-left: 8px; }
.runs .intent { color: var(--text); }
@media (max-width: 640px) {
  body { padding: 24px 14px 48px; }
  h1 { font-size: 22px; }
  .card { padding: 18px 16px; border-radius: 12px; }
  th, td { padding: 6px 8px; font-size: 13px; }
  .bar-label { width: 76px; }
  .bar-val { width: 96px; font-size: 13px; }
}
"""


def _esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _badge(decision: str) -> str:
    label, kind = _DECISION_LABELS.get(decision, _DECISION_LABELS[""])
    return f'<span class="badge {kind}">{_esc(label)}</span>'


def _ts(t: float) -> str:
    m, s = divmod(float(t), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:04.1f}" if h else f"{int(m):02d}:{s:04.1f}"


def _table(headers: list, rows: list, numeric=()) -> str:
    ths = "".join(
        f'<th class="{"num" if i in numeric else ""}">{_esc(h)}</th>'
        for i, h in enumerate(headers)
    )
    body = ""
    for row in rows:
        tds = "".join(
            f'<td class="{"num" if i in numeric else ""}">{_esc(c)}</td>'
            for i, c in enumerate(row)
        )
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"


def _card(title: str, sub: str, body: list, badge: str = "") -> str:
    sub_html = f'<div class="sub">{_esc(sub)}</div>' if sub else ""
    return (
        f'<section class="card"><h2>{_esc(title)}{badge}</h2>{sub_html}'
        + "".join(body)
        + "</section>"
    )


def _r_s1(out: dict) -> list:
    sil = out.get("silence_segments", [])
    keep = out.get("cut_time_list", [])
    rows = [
        (s.get("start", 0), s.get("end", 0), f"{s.get('duration', 0)}s") for s in sil
    ]
    parts = [
        f"<p>识别静音段 <b>{len(sil)}</b> 处（合计 "
        f"{sum(s.get('duration', 0) for s in sil):.1f}s），裁切后成片约 "
        f"<b>{out.get('keep_duration', 0)}s</b>（原片 {out.get('media_duration', 0)}s）。</p>"
    ]
    if rows:
        parts.append("<p>需要删除的静音段（可手动在剪映定位裁剪）：</p>")
        parts.append(_table(
            ["#", "开始", "结束", "时长"],
            [(i, _ts(r[0]), _ts(r[1]), r[2]) for i, r in enumerate(rows, 1)],
        ))
    if keep:
        parts.append("<p>保留片段：</p>")
        parts.append(_table(
            ["#", "开始", "结束"],
            [(i, _ts(k.get("start", 0)), _ts(k.get("end", 0))) for i, k in enumerate(keep, 1)],
        ))
    return parts


def _r_s2(out: dict) -> list:
    issues = out.get("subtitle_issues", [])
    type_label = {
        "punctuation": "标点", "line_wrap": "折行", "overlap": "时间轴重叠",
        "overlap_dropped": "零时长丢弃", "duplicate": "重复字幕",
        "llm_polish": "错别字(模型)", "llm_skipped": "模型降级",
    }
    parts = [
        f"<p>共 {out.get('entry_count', 0)} 条字幕，自动修正 "
        f"<b>{out.get('issue_count', len(issues))}</b> 处问题。</p>"
    ]
    if issues:
        parts.append(_table(
            ["#", "问题类型", "修正内容"],
            [
                (it.get("index"), type_label.get(it.get("type"), it.get("type")),
                 (it.get("after") or "")[:60].replace("\n", " "))
                for it in issues
            ],
        ))
    style = json.dumps(out.get("style", {}), ensure_ascii=False, indent=2)
    parts.append("<p>统一样式参数：</p>")
    parts.append(f"<pre>{_esc(style)}</pre>")
    return parts


def _r_s3(out: dict) -> list:
    segs = out.get("highlight_segments", [])
    parts = [
        f"<p>共切分 {out.get('shot_count', 0)} 个镜头，筛出高光片段 "
        f"<b>{len(segs)}</b> 段（合计 {out.get('highlight_total', 0)}s，V1 启发式评分）。</p>"
    ]
    if segs:
        parts.append(_table(
            ["#", "开始", "结束", "评分"],
            [(i, _ts(s.get("start", 0)), _ts(s.get("end", 0)), s.get("score"))
             for i, s in enumerate(segs, 1)],
        ))
    return parts


def _r_s4(out: dict) -> list:
    plan = out.get("bgm_plan", {})
    mode = {"trim": "裁剪 BGM 尾部", "loop": "循环 BGM 补足时长"}.get(plan.get("mode"), "-")
    return [
        f"<p>BGM 原长 {plan.get('bgm_duration')}s，目标时长 {plan.get('target_duration')}s。</p>",
        f"<p>对齐方式：<b>{_esc(mode)}</b>（循环 {plan.get('loops')} 次，"
        f"尾部裁掉 {plan.get('tail_trim')}s），尾部淡出 {plan.get('fade_out')}s。</p>",
    ]


def _image_src(workdir: Path, name: str) -> str:
    """图片内嵌为 data URI，报告单文件可分享；读取失败退回相对路径。"""
    try:
        data = base64.b64encode((Path(workdir) / name).read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"
    except OSError:
        return name


def _r_s5(out: dict, workdir: Path) -> list:
    mapping = out.get("jianying_mapping", {})
    parts = [f"<p>调色参数来源：{_esc(out.get('source_note') or '内联参数')}</p>"]
    img = out.get("compare_image")
    if img and (Path(workdir) / img).exists():
        parts.append(
            f'<img class="compare" src="{_esc(_image_src(workdir, img))}" alt="调色前后对比">'
        )
        parts.append('<div class="caption">左：原片帧 ｜ 右：调色后</div>')
    parts.append("<p>ffmpeg 滤镜链：</p>")
    parts.append(f"<pre>{_esc(out.get('filter_chain', ''))}</pre>")
    if mapping:
        parts.append("<p>剪映「调节」面板参数映射：</p>")
        parts.append(_table(["参数", "数值"], list(mapping.items()), numeric=(1,)))
    return parts


def _r_s6(out: dict) -> list:
    parts = [
        f"<p>转写后端：{_esc(out.get('backend', '-'))}"
        f"（模型 <code>{_esc(out.get('asr_model', '-'))}</code>），识别出 "
        f"<b>{out.get('segment_count', 0)}</b> 条字幕。</p>"
    ]
    preview = out.get("segments_preview", [])
    if preview:
        parts.append(_table(
            ["#", "开始", "结束", "文本"],
            [(i, _ts(s.get("start", 0)), _ts(s.get("end", 0)),
              (s.get("text") or "")[:40]) for i, s in enumerate(preview, 1)],
        ))
    return parts


def _render_result(result, workdir: Path) -> str:
    title = f"{result.skill_id}"
    sub = f"耗时 {result.duration:.2f}s"
    if not result.ok:
        return _card(
            title, sub,
            [f'<p class="error">失败原因：{_esc(result.error)}</p>'],
            badge='<span class="badge bad">失败</span>',
        )
    out = result.outputs or {}
    renderer = {
        "S001": lambda o: _r_s1(o),
        "S002": lambda o: _r_s2(o),
        "S003": lambda o: _r_s3(o),
        "S004": lambda o: _r_s4(o),
        "S005": lambda o: _r_s5(o, workdir),
        "S006": lambda o: _r_s6(o),
    }.get(result.skill_id)
    if renderer:
        body = renderer(out)
    else:
        body = [f"<pre>{_esc(json.dumps(out, ensure_ascii=False, indent=2))}</pre>"]
    return _card(title, sub, body, badge='<span class="badge ok">完成</span>')


def _artifacts_html(workdir: Path) -> str:
    workdir = Path(workdir)
    links = []
    if workdir.exists():
        for f in sorted(workdir.iterdir()):
            if not f.is_file() or f.name in _SKIP_FILES or f.name.startswith("."):
                continue
            label = _ARTIFACT_LABELS.get(f.name, f.name)
            links.append(
                f'<a href="{_esc(f.name)}">{_esc(label)}<span>{_esc(f.name)}</span></a>'
            )
    if not links:
        return ""
    return _card("产物文件", "点击打开（相对当前目录）", [f'<div class="files">{"".join(links)}</div>'])


def write_run_html(
    workdir,
    plan: ExecutionPlan,
    report: ScheduleReport,
    decision: str = "",
) -> Path:
    """生成单次运行的 report.html，返回路径。"""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    steps = " → ".join(f"{s.skill_id}" for s in plan.steps) or "无"
    body = [
        "<header>",
        f"<h1>剪辑辅助 Agent · 执行预览报告 {_badge(decision)}</h1>",
        f'<div class="meta"><div>意图：{_esc(plan.intent or "未识别")}</div>',
        f"<div>执行步骤：{_esc(steps)}</div>",
    ]
    if plan.explanation:
        body.append(f"<div>路由说明：{_esc(plan.explanation)}</div>")
    body.append("</header>")

    for result in report.results:
        body.append(_render_result(result, workdir))
    if report.aborted:
        body.append(_card(
            "执行中断",
            "",
            [f'<p class="error">{_esc(report.error)}</p>'
             "<p>已保留前面完成的结果；可调整参数后重试。</p>"],
        ))
    body.append(_artifacts_html(workdir))
    body.append('<div class="note">本报告为预览产物，未修改任何原始素材；确认应用前不渲染成片。</div>')

    page = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>剪辑辅助 Agent · 执行预览报告</title>"
        f"<style>{_STYLE}</style></head><body><div class=\"wrap\">"
        + "".join(body)
        + "</div></body></html>"
    )
    path = workdir / "report.html"
    path.write_text(page, encoding="utf-8")
    return path


# ---------------------------------------------------------------- 评测仪表盘

def collect_recent_runs(output_dir, limit: int = 10) -> list:
    """扫描 output/run_*，返回最近运行（含 intent、链接）。"""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []
    dirs = sorted(
        (d for d in output_dir.glob("run_*") if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )[:limit]
    runs = []
    for d in dirs:
        intent, created = "", ""
        preview = d / "preview.json"
        if preview.exists():
            try:
                payload = json.loads(preview.read_text(encoding="utf-8"))
                intent = (payload.get("plan") or {}).get("intent") or ""
                created = payload.get("created_at") or ""
            except json.JSONDecodeError:
                pass
        target = "report.html" if (d / "report.html").exists() else "report.md"
        runs.append({
            "name": d.name,
            "intent": intent or "（未识别意图）",
            "created_at": created,
            "href": f"{d.name}/{target}",
        })
    return runs


def _fraction_bar(label: str, value: int, total: int, kind: str) -> str:
    pct = value / total if total else 0
    return (
        f'<div class="bar-row"><div class="bar-label">{_esc(label)}</div>'
        f'<div class="bar-track"><div class="bar-fill {kind}" style="width:{pct:.1%}"></div></div>'
        f'<div class="bar-val">{value}/{total}（{pct:.0%}）</div></div>'
    )


def render_metrics_html(data: dict, runs: list) -> str:
    """评测仪表盘 HTML（data 来自 MetricsTracker.report()）。"""
    skills = data.get("skills", {})
    dec = data.get("decisions", {"adopted": 0, "modified": 0, "discarded": 0})
    assets = data.get("assets", {})
    total_dec = dec.get("adopted", 0) + dec.get("modified", 0) + dec.get("discarded", 0)

    body = ["<header>",
            "<h1>剪辑辅助 Agent · 评测仪表盘</h1>",
            '<div class="meta"><div>效率 / 质量 / 生态指标（数据来自本地埋点）</div></div>',
            "</header>"]

    eff_rows = [
        (sid, v.get("调用次数", 0), f"{v.get('成功率', 0):.0%}", v.get("平均耗时(s)", 0))
        for sid, v in skills.items()
    ]
    body.append(_card(
        "一、效率指标", "Skill 调用次数与平均耗时",
        [_table(["Skill", "调用次数", "成功率", "平均耗时(s)"], eff_rows, numeric=(1, 2, 3))]
        if eff_rows else ["<p>暂无数据，先跑几次 <code>clip-agent run</code>。</p>"],
    ))

    bars = []
    if total_dec:
        bars += [
            _fraction_bar("采纳", dec.get("adopted", 0), total_dec, "ok"),
            _fraction_bar("二次修改", dec.get("modified", 0), total_dec, "info"),
            _fraction_bar("放弃", dec.get("discarded", 0), total_dec, "muted"),
        ]
    else:
        bars = ["<p>暂无用户决策数据。</p>"]
    body.append(_card("二、质量指标", "用户决策分布（采纳 / 修改 / 放弃）", bars))

    eco_rows = [
        (label, assets.get(key, 0))
        for label, key in (("资产保存", "save"), ("资产复用", "use"), ("资产收藏", "favorite"))
    ]
    body.append(_card(
        "三、生态指标", "创作资产库动作",
        [_table(["动作", "次数"], eco_rows, numeric=(1,))],
    ))

    if runs:
        items = "".join(
            f'<li><a href="{_esc(r["href"])}">{_esc(r["name"])}</a>'
            f'<span class="when">{_esc(r["created_at"])}</span>'
            f'<div class="intent">{_esc(r["intent"])}</div></li>'
            for r in runs
        )
        body.append(_card("最近运行", "点击查看各次运行的 HTML 报告", [f'<ul class="runs">{items}</ul>']))
    body.append('<div class="note">报表口径：采纳率 = 采纳 ÷ 全部用户决策；'
                '修改参数重跑计入“二次修改”，非交互预览不计入决策。</div>')

    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>剪辑辅助 Agent · 评测仪表盘</title>"
        f"<style>{_STYLE}</style></head><body><div class=\"wrap\">"
        + "".join(body)
        + "</div></body></html>"
    )


def write_metrics_html(out_path, data: dict, runs: list) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_metrics_html(data, runs), encoding="utf-8")
    return out_path
