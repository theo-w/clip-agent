"""S006 语音转写与 S006→S002 链式测试（后端调用用 monkeypatch，不依赖真实模型）。"""
from pathlib import Path

import pytest

from clip_agent.core.models import ExecContext, ExecutionPlan, PlanStep
from clip_agent.core.registry import SkillRegistry
from clip_agent.core.scheduler import Scheduler
from clip_agent.media import transcribe as asr
from clip_agent.media.transcribe import TranscriptSegment, segments_to_srt
from clip_agent.skills.s2_subtitle_fix import SubtitleFixSkill
from clip_agent.skills.s6_transcribe import TranscribeSkill


def test_segments_to_srt():
    text = segments_to_srt([
        TranscriptSegment(0.2, 1.8, "大家好。"),
        TranscriptSegment(1.9, 63.0, "今天做一道家常菜。"),
    ])
    assert text.startswith("1\n00:00:00,200 --> 00:00:01,800\n大家好。")
    assert "2\n00:00:01,900 --> 00:01:03,000" in text


def test_no_backend_error(monkeypatch):
    monkeypatch.setattr(asr, "available_backend", lambda: None)
    with pytest.raises(asr.AsrBackendError, match="未安装语音转写后端"):
        asr.transcribe("x.mp4", ".")


def test_s6_fails_with_install_hint(monkeypatch):
    monkeypatch.setattr(asr, "available_backend", lambda: None)
    skill = TranscribeSkill()
    result = skill.run(ExecContext(media_path="x.mp4"), skill.meta.params)
    assert not result.ok
    assert "pip install -e" in result.error


def test_s6_s2_chain(tmp_path, monkeypatch):
    """S006 转写输出作为 S002 的上游输入，串行编排自动接力。"""
    def fake_transcribe(media_path, workdir, backend="auto", model="", language="zh"):
        return (
            [TranscriptSegment(0.2, 1.8, "大家好,今天做一道家常菜.")],
            "mlx-whisper",
            "fake-model",
        )

    monkeypatch.setattr(asr, "transcribe", fake_transcribe)

    registry = SkillRegistry()
    registry.register(TranscribeSkill())
    registry.register(SubtitleFixSkill())
    scheduler = Scheduler(registry=registry)
    plan = ExecutionPlan(intent="语音转写并校对字幕", steps=[
        PlanStep(skill_id="S006"), PlanStep(skill_id="S002"),
    ])
    ctx = ExecContext(media_path="fake.mp4", workdir=tmp_path)
    report = scheduler.run(plan, ctx)

    assert report.ok, report.error
    assert [r.skill_id for r in report.results] == ["S006", "S002"]
    assert (tmp_path / "transcribed.srt").exists()
    fixed = Path(report.results[1].outputs["fixed_subtitle"])
    assert "大家好，今天做一道家常菜。" in fixed.read_text(encoding="utf-8")


def test_s2_prefers_explicit_subtitle(tmp_path):
    """同时存在 --subtitle 与上游转写时，显式字幕优先。"""
    explicit = tmp_path / "explicit.srt"
    explicit.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好.\n", encoding="utf-8")
    upstream = tmp_path / "upstream.srt"
    upstream.write_text("1\n00:00:00,000 --> 00:00:01,000\n世界.\n", encoding="utf-8")

    skill = SubtitleFixSkill()
    ctx = ExecContext(subtitle_path=str(explicit), workdir=tmp_path)
    ctx.put("subtitle_text", str(upstream))
    result = skill.run(ctx, skill.meta.params)
    assert result.ok
    fixed = Path(result.outputs["fixed_subtitle"]).read_text(encoding="utf-8")
    assert "你好" in fixed
    assert "世界" not in fixed
