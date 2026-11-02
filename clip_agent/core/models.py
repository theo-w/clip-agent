"""核心数据模型：Skill 元数据、执行计划、执行上下文、执行结果。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillMeta:
    """Skill 元数据，对应 SDD 第 5 节的数据结构。"""

    skill_id: str
    name: str
    desc: str
    params: dict = field(default_factory=dict)        # 默认参数
    input: list = field(default_factory=list)         # 前置依赖键
    output: list = field(default_factory=list)        # 产出键
    is_enable: bool = True
    version: str = "1.0"          # Skill 版本号（资产依赖校验用，形如 "1.2"）
    triggers: list = field(default_factory=list)     # 规则路由触发词


@dataclass
class PlanStep:
    """执行计划中的一个步骤：调用某个 Skill 并覆盖部分默认参数。"""

    skill_id: str
    params: dict = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """意图解析产出的执行计划（V1.0 为串行顺序）。"""

    intent: str
    steps: list = field(default_factory=list)
    explanation: str = ""      # 给用户看的解释 / 澄清话术
    source: str = "rule"        # rule | llm


@dataclass
class SkillResult:
    """单个 Skill 的执行结果。"""

    skill_id: str
    ok: bool
    outputs: dict = field(default_factory=dict)
    error: str = None           # type: (str, None)
    duration: float = 0.0


@dataclass
class ScheduleReport:
    """一次调度的完整报告（含失败终止语义）。"""

    plan: ExecutionPlan
    results: list = field(default_factory=list)
    aborted: bool = False
    error: str = None           # type: (str, None)
    started_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return not self.aborted and all(r.ok for r in self.results)


@dataclass
class ExecContext:
    """Skill 执行上下文：素材输入、中间结果、输出目录。"""

    media_path: str = None      # type: (str, None)
    subtitle_path: str = None   # type: (str, None)
    bgm_path: str = None        # type: (str, None)
    workdir: Path = field(default_factory=Path)
    intermediate: dict = field(default_factory=dict)

    def put(self, key: str, value: Any) -> None:
        self.intermediate[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.intermediate.get(key, default)

    def available_keys(self) -> set:
        """素材侧 + 中间结果侧可满足的输入依赖键。"""
        keys = set(self.intermediate)
        if self.media_path:
            keys.update({"audio_track", "video_timeline"})
        if self.subtitle_path:
            keys.add("subtitle_text")
        if self.bgm_path:
            keys.add("bgm_track")
        return keys
