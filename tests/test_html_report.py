"""HTML 报告测试：转义安全、产物链接、失败态、仪表盘与最近运行扫描。"""
import json

from clip_agent.core.models import ExecutionPlan, PlanStep, ScheduleReport, SkillResult
from clip_agent.preview.html_report import (
    collect_recent_runs,
    render_metrics_html,
    write_run_html,
)


def _plan(intent="静音片段裁切", steps=("S001",)) -> ExecutionPlan:
    return ExecutionPlan(
        intent=intent,
        steps=[PlanStep(skill_id=s) for s in steps],
        explanation="规则路由命中",
        source="rule",
    )


def test_run_html_escapes_untrusted_text(tmp_path):
    plan = _plan(intent='<script>alert("x")</script>')
    report = ScheduleReport(plan=plan, results=[
        SkillResult(
            skill_id="S002", ok=True, duration=0.01,
            outputs={"entry_count": 1, "issue_count": 0, "style": {}},
        ),
    ])
    path = write_run_html(tmp_path, plan, report, decision="adopted")
    html = path.read_text(encoding="utf-8")

    assert "&lt;script&gt;" in html
    assert '<script>alert("x")</script>' not in html
    assert "已采纳" in html
    assert "S002" in html


def test_run_html_s005_compare_image_and_artifacts(tmp_path):
    (tmp_path / "compare.jpg").write_bytes(b"fake-jpg")
    (tmp_path / "graded_demo.mp4").write_bytes(b"fake-mp4")
    plan = _plan(steps=("S005",))
    report = ScheduleReport(plan=plan, results=[
        SkillResult(
            skill_id="S005", ok=True, duration=0.1,
            outputs={
                "source_note": "资产库预设「清冷胶片感」v1",
                "filter_chain": "eq=brightness=-0.05",
                "jianying_mapping": {"亮度": -5},
                "compare_image": "compare.jpg",
            },
        ),
    ])
    html = write_run_html(tmp_path, plan, report, decision="previewed").read_text(
        encoding="utf-8"
    )

    assert 'src="data:image/jpeg;base64,' in html
    assert "左：原片帧" in html
    assert 'href="compare.jpg"' in html
    assert "调色对比图" in html
    assert 'href="graded_demo.mp4"' in html
    assert "仅预览" in html


def test_run_html_failed_state(tmp_path):
    plan = _plan()
    report = ScheduleReport(
        plan=plan, results=[], aborted=True,
        error="未安装语音转写后端。<b>安装</b>",
    )
    html = write_run_html(tmp_path, plan, report, decision="failed").read_text(
        encoding="utf-8"
    )

    assert "执行中断" in html
    assert "&lt;b&gt;安装&lt;/b&gt;" in html
    assert "<b>安装</b>" not in html


def test_metrics_html_contains_rates_and_run_links():
    data = {
        "skills": {
            "S001": {"调用次数": 4, "成功率": 1.0, "平均耗时(s)": 0.08},
        },
        "decisions": {"adopted": 4, "modified": 1, "discarded": 1},
        "assets": {"save": 1, "use": 2, "favorite": 0},
    }
    runs = [{
        "name": "run_20261102_185807",
        "intent": "<script>x</script>",
        "created_at": "2026-11-02T18:58:07",
        "href": "run_20261102_185807/report.html",
    }]
    html = render_metrics_html(data, runs)

    assert "4/6（67%）" in html          # 采纳率
    assert "1/6（17%）" in html          # 二次修改率
    assert "run_20261102_185807/report.html" in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "资产复用" in html


def test_collect_recent_runs(tmp_path):
    newer = tmp_path / "run_20261102_190000"
    newer.mkdir()
    (newer / "preview.json").write_text(json.dumps({
        "created_at": "2026-11-02T19:00:00",
        "plan": {"intent": "套用调色预设"},
    }, ensure_ascii=False), encoding="utf-8")
    (newer / "report.html").write_text("<html></html>", encoding="utf-8")

    older = tmp_path / "run_20261102_180000"
    older.mkdir()
    (older / "preview.json").write_text(json.dumps({
        "created_at": "2026-11-02T18:00:00",
        "plan": {"intent": "识别静音片段并裁剪"},
    }, ensure_ascii=False), encoding="utf-8")

    runs = collect_recent_runs(tmp_path, limit=10)
    assert [r["name"] for r in runs] == ["run_20261102_190000", "run_20261102_180000"]
    assert runs[0]["href"] == "run_20261102_190000/report.html"
    assert runs[1]["href"] == "run_20261102_180000/report.md"  # 无 html 时回退 md
    assert runs[0]["intent"] == "套用调色预设"
