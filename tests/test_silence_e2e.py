"""S001 静音检测与裁切的端到端测试（需要 ffmpeg，缺失自动跳过）。"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="需要 ffmpeg"
)

from clip_agent.core.models import ExecContext
from clip_agent.media import analyzer
from clip_agent.skills.s1_silence_cut import SilenceCutSkill, invert_to_keep
from clip_agent.media.analyzer import SilenceSegment


@pytest.fixture(scope="module")
def demo_audio(tmp_path_factory):
    """1s 声音 + 1.2s 静音 + 1s 声音。"""
    path = tmp_path_factory.mktemp("media") / "demo.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2.2",
            "-af", "volume=0:enable='between(t,1,2.2)'",
            "-ar", "44100", str(path),
        ],
        check=True, capture_output=True,
    )
    return str(path)


def test_detect_silence(demo_audio):
    segs = analyzer.detect_silence(demo_audio, threshold_db=-35, min_duration=0.5)
    assert len(segs) == 1
    assert abs(segs[0].start - 1.0) < 0.15
    assert abs(segs[0].end - 2.2) < 0.15


def test_invert_to_keep():
    keep = invert_to_keep(10.0, [SilenceSegment(4.0, 6.0)], padding=0.1)
    assert keep == [(0.0, 3.9), (6.1, 10.0)]


def test_silence_skill_run(demo_audio, tmp_path):
    skill = SilenceCutSkill()
    ctx = ExecContext(media_path=demo_audio, workdir=tmp_path)
    result = skill.run(ctx, skill.meta.params)
    assert result.ok
    keep = result.outputs["cut_time_list"]
    # 音频为 1s 声音 + 1.2s 尾部静音：裁掉后只剩 1 个保留段（前 0.9s）
    assert len(keep) == 1
    assert abs(keep[0]["end"] - 0.9) < 0.15   # 静音前留 0.1s 余量
    assert (tmp_path / "silence_cut.json").exists()


def test_silence_skill_render(demo_audio, tmp_path):
    skill = SilenceCutSkill()
    ctx = ExecContext(media_path=demo_audio, workdir=tmp_path)
    result = skill.run(ctx, skill.meta.params)
    produced = skill.render(ctx, skill.meta.params, result.outputs)
    assert len(produced) == 1
    # 渲染后时长 ≈ 0.9s（尾部静音已去除）
    assert abs(analyzer.probe_duration(str(produced[0])) - 0.9) < 0.3


def test_silence_render_streams_progress(demo_audio, tmp_path):
    """渲染进度流式回报（Backlog 修复）：回调单调不减，且以 100% 收尾。"""
    skill = SilenceCutSkill()
    ctx = ExecContext(media_path=demo_audio, workdir=tmp_path)
    result = skill.run(ctx, skill.meta.params)
    ratios = []
    produced = skill.render(ctx, skill.meta.params, result.outputs,
                            on_progress=ratios.append)
    assert produced
    assert ratios and ratios[-1] == 1.0
    assert all(0.0 <= r <= 1.0 for r in ratios)
    assert ratios == sorted(ratios)
