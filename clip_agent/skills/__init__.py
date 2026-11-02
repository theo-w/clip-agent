"""Skill 仓库：内置 5 个原子技能（SDD 模块 2 & 7），导入本包即完成注册。

启停状态持久化在 data/skill_state.json，新增 Skill 只需定义类并加入
BUILTIN_SKILLS，不需要改动调度核心。
"""
from __future__ import annotations

import json

from ..core.registry import REGISTRY
from ..paths import data_dir
from .s1_silence_cut import SilenceCutSkill
from .s2_subtitle_fix import SubtitleFixSkill
from .s3_highlight import HighlightSkill
from .s4_bgm_align import BgmAlignSkill
from .s5_color_apply import ColorApplySkill

BUILTIN_SKILLS = [
    SilenceCutSkill,
    SubtitleFixSkill,
    HighlightSkill,
    BgmAlignSkill,
    ColorApplySkill,
]


def _state_path():
    return data_dir() / "skill_state.json"


def _load_state() -> dict:
    path = _state_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_state(states: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(states, ensure_ascii=False, indent=2), encoding="utf-8")


def set_skill_enabled(skill_id: str, enabled: bool) -> None:
    """上下线某个 Skill（SDD 2.1 需求 2）。"""
    if REGISTRY.get(skill_id) is None:
        raise KeyError(skill_id)
    REGISTRY.set_enable(skill_id, enabled)
    states = _load_state()
    states[skill_id] = enabled
    _save_state(states)


for _cls in BUILTIN_SKILLS:
    REGISTRY.register(_cls())

for _sid, _enabled in _load_state().items():
    if REGISTRY.get(_sid) is not None:
        REGISTRY.set_enable(_sid, bool(_enabled))
