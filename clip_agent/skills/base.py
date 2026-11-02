"""Skill 基类：所有剪辑技能的统一抽象（SDD 模块 2 的 Skill 定义标准）。

每个 Skill 是独立原子任务，具备：
- 入参（meta.params 为默认参数，运行时可被执行计划覆盖）
- 前置依赖（meta.input 声明需要的输入键）
- 执行动作（run，只生成方案数据，不直接修改原素材）
- 输出（meta.output 声明的产出键，进入上下文供后续 Skill 消费）
- 失败判定（返回 ok=False + error 说明，调度器据此终止后续）

render 为可选能力：用户确认「应用」后才被调用，把方案物化为成片文件。
"""
from __future__ import annotations

from pathlib import Path

from ..core.models import ExecContext, SkillMeta, SkillResult


class Skill:
    """Skill 抽象基类，子类定义 meta 并实现 run。"""

    meta: SkillMeta

    def run(self, ctx: ExecContext, params: dict) -> SkillResult:
        raise NotImplementedError

    def render(self, ctx: ExecContext, params: dict, outputs: dict) -> list:
        """把执行结果物化为成片文件；默认无渲染能力（方案数据即交付物）。"""
        return []

    def success(self, outputs: dict) -> SkillResult:
        return SkillResult(skill_id=self.meta.skill_id, ok=True, outputs=outputs)

    def fail(self, error: str) -> SkillResult:
        return SkillResult(skill_id=self.meta.skill_id, ok=False, error=error)
