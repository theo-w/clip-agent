"""V1.2 剪映草稿导出测试：纯函数计划 + 可选依赖降级 + 结构校验。"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from clip_agent import __main__ as cli
from clip_agent.export import jianying


def _preview(results, media=None, bgm=None):
    return {
        "created_at": "2026-11-03T10:00:00",
        "media": media,
        "bgm": bgm,
        "plan": {
            "intent": "测试", "explanation": "",
            "source": "rule", "steps": [],
        },
        "aborted": False,
        "error": None,
        "results": results,
    }


def _result(skill_id, outputs):
    return {
        "skill_id": skill_id, "ok": True, "outputs": outputs,
        "error": None, "duration": 0.1,
    }


def _write_srt(path: Path, blocks: list) -> str:
    lines = []
    for index, (start, end, text) in enumerate(blocks, 1):
        lines.append(f"{index}\n{start} --> {end}\n{text}\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


@pytest.fixture()
def fake_media(tmp_path):
    """导出层的存在性校验只要求文件存在即可。"""
    path = tmp_path / "media.mp4"
    path.write_bytes(b"fake")
    return str(path)


def test_build_plan_maps_cut_clips(fake_media, tmp_path):
    preview = _preview([_result("S001", {
        "cut_time_list": [{"start": 0.0, "end": 1.92}, {"start": 3.304, "end": 6.0}],
        "media_duration": 6.0,
    })])
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media)

    assert [c.source_start for c in plan.clips] == [0.0, 3.304]
    assert [c.target_start for c in plan.clips] == [0.0, 1.92]
    assert plan.duration == 4.616
    assert plan.subtitles == []
    assert any("字幕" in w for w in plan.warnings)


def test_build_plan_maps_subtitles_through_cuts(fake_media, tmp_path):
    srt = _write_srt(tmp_path / "fixed.srt", [
        ("00:00:00,000", "00:00:01,000", "第一句"),
        ("00:00:02,000", "00:00:03,000", "这段在静音里，应被跳过"),
        ("00:00:03,300", "00:00:05,000", "裁剪后的第二句"),
    ])
    preview = _preview([_result("S001", {
        "cut_time_list": [{"start": 0.0, "end": 1.92}, {"start": 3.304, "end": 6.0}],
        "media_duration": 6.0,
    })], )
    preview["results"].append(_result("S002", {"fixed_subtitle": srt}))
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media)

    assert len(plan.subtitles) == 2
    assert plan.subtitles[0].text == "第一句"
    assert (plan.subtitles[0].start, plan.subtitles[0].end) == (0.0, 1.0)
    assert plan.subtitles[1].text == "裁剪后的第二句"
    assert (plan.subtitles[1].start, plan.subtitles[1].end) == (1.92, 3.616)


def test_build_plan_without_s1_uses_full_media(fake_media, tmp_path):
    preview = _preview([_result("S002", {
        "fixed_subtitle": _write_srt(tmp_path / "s.srt", [
            ("00:00:00,000", "00:00:02,000", "完整素材"),
        ]),
    })])
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media, duration=2.5)

    assert len(plan.clips) == 1
    assert (plan.clips[0].source_start, plan.clips[0].source_end) == (0.0, 2.5)
    assert plan.duration == 2.5
    assert plan.subtitles[0].text == "完整素材"


def test_build_plan_uses_highlight_segments_when_no_s1(fake_media, tmp_path):
    preview = _preview([_result("S003", {
        "highlight_segments": [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 4.0}],
        "media_duration": 6.0,
    })])
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media)

    assert [c.target_start for c in plan.clips] == [0.0, 2.0]
    assert plan.duration == 4.0


def test_build_plan_requires_media_and_existing_file(tmp_path):
    preview = _preview([])
    with pytest.raises(jianying.JianyingExportError, match="--media"):
        jianying.build_draft_plan(preview, tmp_path)
    with pytest.raises(jianying.JianyingExportError, match="不存在"):
        jianying.build_draft_plan(preview, tmp_path, media=str(tmp_path / "nope.mp4"))


def test_build_plan_prefers_rendered_bgm(fake_media, tmp_path):
    (tmp_path / "bgm_aligned.m4a").write_bytes(b"fake")
    preview = _preview([_result("S004", {"bgm_plan": {"target_duration": 4.6}})])
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media, duration=4.6)
    assert plan.bgm["path"].endswith("bgm_aligned.m4a")
    assert plan.bgm["note"] == "S004 对齐后的 BGM"


def test_write_draft_reports_missing_dependency(fake_media, tmp_path, monkeypatch):
    preview = _preview([])
    plan = jianying.build_draft_plan(preview, tmp_path, media=fake_media, duration=1.0)

    def _boom():
        raise ImportError("no module")

    monkeypatch.setattr(jianying, "_import_draft_module", _boom)
    with pytest.raises(jianying.JianyingExportError, match=r"pip install -e"):
        jianying.write_draft(plan, tmp_path / "drafts")


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not jianying._has_optional_dependency(),
    reason="需要 ffmpeg 与 pyJianYingDraft",
)
def test_write_draft_structure(tmp_path):
    media = tmp_path / "media.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-f", "lavfi",
         "-i", "testsrc=duration=3:size=320x180:rate=30", "-pix_fmt", "yuv420p",
         str(media)],
        check=True, capture_output=True,
    )
    srt = _write_srt(tmp_path / "fixed.srt", [
        ("00:00:00,000", "00:00:02,000", "测试字幕"),
    ])
    preview = _preview([_result("S002", {"fixed_subtitle": srt})])
    plan = jianying.build_draft_plan(preview, tmp_path, media=str(media), duration=3.0)
    draft_dir = jianying.write_draft(plan, tmp_path / "drafts")

    assert draft_dir.is_dir()
    content = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
    assert content["tracks"]
    assert any(track.get("name") == "字幕" for track in content["tracks"])
    assert "测试字幕" in (draft_dir / "draft_content.json").read_text(encoding="utf-8")
    plan_file = tmp_path / "drafts" / f"{plan.draft_name}.clip_agent.json"
    assert plan_file.exists()
    assert json.loads(plan_file.read_text(encoding="utf-8"))["duration"] == 3.0


def test_cli_export_jianying_dry_run(fake_media, tmp_path, capsys):
    run_dir = tmp_path / "run_x"
    run_dir.mkdir()
    preview = _preview([_result("S001", {
        "cut_time_list": [{"start": 0.0, "end": 1.0}],
        "media_duration": 1.0,
    })], media=fake_media)
    (run_dir / "preview.json").write_text(
        json.dumps(preview, ensure_ascii=False), encoding="utf-8"
    )

    code = cli.main(["export-jianying", str(run_dir), "--dry-run"])

    assert code == 0
    out = capsys.readouterr().out
    assert "剪映草稿计划" in out and "视频轨：1 段" in out
    assert "dry-run" in out


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or not jianying._has_optional_dependency(),
    reason="需要 ffmpeg 与 pyJianYingDraft",
)
def test_write_draft_audio_only_media(tmp_path):
    media = tmp_path / "voice.m4a"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=2", "-c:a", "aac", str(media)],
        check=True, capture_output=True,
    )
    preview = _preview([])
    plan = jianying.build_draft_plan(preview, tmp_path, media=str(media), duration=2.0)
    draft_dir = jianying.write_draft(plan, tmp_path / "drafts")
    content = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
    assert [(t["type"], t["name"]) for t in content["tracks"]] == [("audio", "原声轨")]
