"""Skill 仓库：注册、检索、启停控制（SDD 模块 7）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..skills.base import Skill


class SkillRegistry:
    """全局 Skill 注册表。"""

    def __init__(self) -> None:
        self._skills = {}

    def register(self, skill: "Skill") -> "Skill":
        if skill.meta.skill_id in self._skills:
            raise ValueError(f"Skill 重复注册：{skill.meta.skill_id}")
        self._skills[skill.meta.skill_id] = skill
        return skill

    def get(self, skill_id: str):
        return self._skills.get(skill_id)

    def all(self) -> list:
        return list(self._skills.values())

    def enabled(self) -> list:
        return [s for s in self._skills.values() if s.meta.is_enable]

    def set_enable(self, skill_id: str, enabled: bool) -> None:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"未注册的 Skill：{skill_id}")
        skill.meta.is_enable = enabled

    def manifest(self) -> list:
        """Skill 清单（供意图路由与 CLI 展示）。"""
        return [
            {
                "skill_id": s.meta.skill_id,
                "name": s.meta.name,
                "desc": s.meta.desc,
                "params": s.meta.params,
                "input": s.meta.input,
                "output": s.meta.output,
                "is_enable": s.meta.is_enable,
                "version": s.meta.version,
            }
            for s in self._skills.values()
        ]


REGISTRY = SkillRegistry()
