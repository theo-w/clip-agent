"""路径约定：数据目录（资产库 / 埋点 / Skill 开关状态）。"""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """数据目录；可用环境变量 CLIP_AGENT_DATA_DIR 覆盖（测试隔离用）。"""
    root = os.environ.get("CLIP_AGENT_DATA_DIR")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent / "data"
