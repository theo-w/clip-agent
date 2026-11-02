"""S005 调色一帧预览对比图的端到端测试（需要 ffmpeg，缺失自动跳过）。"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="需要 ffmpeg"
)

from clip_agent.core.models import ExecContext
from clip_agent.skills.s5_color_apply import ColorApplySkill


@pytest.fixture(scope="module")
def demo_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "demo.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner",
         "-f", "lavfi", "-i", "testsrc2=duration=1:size=320x180:rate=10",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         str(path)],
        check=True, capture_output=True,
    )
    return str(path)


def test_compare_image_in_preview(demo_video, tmp_path):
    """预览阶段应生成左右对比图，宽度为原片两倍。"""
    skill = ColorApplySkill()
    ctx = ExecContext(media_path=demo_video, workdir=tmp_path)
    result = skill.run(ctx, {"contrast": 1.2, "brightness": 0.05})
    assert result.ok
    assert result.outputs.get("compare_image") == "compare.jpg"
    compare = tmp_path / "compare.jpg"
    assert compare.exists()
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width",
         "-of", "csv=p=0", str(compare)],
        check=True, capture_output=True, text=True,
    )
    assert int(proc.stdout.strip()) == 640  # 320x180 原片，hstack 后 640


def test_render_after_confirm(demo_video, tmp_path):
    """确认应用后渲染整片成片。"""
    skill = ColorApplySkill()
    ctx = ExecContext(media_path=demo_video, workdir=tmp_path)
    result = skill.run(ctx, {"contrast": 1.2, "brightness": 0.05})
    produced = skill.render(ctx, {"contrast": 1.2, "brightness": 0.05},
                            result.outputs)
    assert len(produced) == 1
    assert produced[0].name.startswith("graded_")
