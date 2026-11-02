"""CLI 端到端测试（需要 ffmpeg，缺失自动跳过）。

覆盖 SDD 第 4 节核心流程：指令 → 意图 → 调度 → 预览报告 → 采纳。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def demo_wav(tmp_path_factory):
    path = tmp_path_factory.mktemp("cli") / "demo.wav"
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


def _run_cli(args, data_dir):
    env = dict(os.environ)
    env["CLIP_AGENT_DATA_DIR"] = str(data_dir)
    env["CLIP_AGENT_LLM_URL"] = ""  # 测试固定走规则路由
    return subprocess.run(
        [sys.executable, "-m", "clip_agent"] + args,
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
    )


def test_cli_run_silence_golden_path(demo_wav, tmp_path):
    proc = _run_cli(
        ["run", "识别静音片段并裁剪", "--media", demo_wav,
         "--yes", "--no-render", "--workdir", str(tmp_path / "out")],
        data_dir=tmp_path / "data",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = tmp_path / "out" / "report.md"
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "S001" in content and "静音段" in content
    assert (tmp_path / "out" / "preview.json").exists()
    # 埋点落盘
    metrics = (tmp_path / "data" / "metrics.jsonl").read_text(encoding="utf-8")
    assert '"skill_run"' in metrics and '"adopted"' in metrics


def test_cli_rejects_without_media(demo_wav, tmp_path):
    """前置依赖缺失：给出明确失败原因而不是崩溃。"""
    proc = _run_cli(
        ["run", "识别静音片段并裁剪", "--yes", "--workdir", str(tmp_path / "out2")],
        data_dir=tmp_path / "data",
    )
    assert proc.returncode == 2
    assert "前置输入" in proc.stdout


def test_cli_subjective_rejected(demo_wav, tmp_path):
    proc = _run_cli(
        ["run", "帮我做一个有情绪张力的叙事剪辑", "--media", demo_wav,
         "--workdir", str(tmp_path / "out3")],
        data_dir=tmp_path / "data",
    )
    assert proc.returncode == 1
    assert "主观创意" in proc.stdout


def test_cli_assets_export_import(tmp_path):
    """V1.1 流通：导出 .clipasset → 导入到另一个数据目录的资产库。"""
    file = tmp_path / "color001.clipasset"
    proc = _run_cli(
        ["assets", "export", "color001", "--out", str(file)],
        data_dir=tmp_path / "lib_a",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert file.exists() and "分享码" in proc.stdout

    proc2 = _run_cli(["assets", "import", str(file)], data_dir=tmp_path / "lib_b")
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert "已导入资产" in proc2.stdout and "CA-" in proc2.stdout

    # 导入后原资产可被检索到
    proc3 = _run_cli(["assets", "list"], data_dir=tmp_path / "lib_b")
    assert proc3.returncode == 0 and "清冷胶片感" in proc3.stdout


def test_cli_assets_import_rejects_bad_dependency(tmp_path):
    bad = tmp_path / "bad.clipasset"
    bad.write_text(json.dumps({
        "format": "clipasset", "format_version": 1, "share_code": "CA-BAD001",
        "asset": {
            "asset_id": "ext12345", "asset_type": "color_preset",
            "name": "坏资产", "params": {},
            "dependencies": [{"skill_id": "S999", "min_version": "1.0"}],
        },
    }, ensure_ascii=False), encoding="utf-8")
    proc = _run_cli(["assets", "import", str(bad)], data_dir=tmp_path / "lib_c")
    assert proc.returncode == 1
    assert "S999" in proc.stdout and "未静默" not in proc.stdout
