"""Skill 调度引擎（SDD 模块 2）。

调度规则：
- 按执行计划顺序执行，每步产出中间结果写入上下文，供后续 Skill 消费；
- 单 Skill 失败即终止后续流程，保留已完成结果并返回错误信息；
- 每步支持进度回调（长任务进度展示）。
"""
from __future__ import annotations

import time

from .models import ExecContext, ExecutionPlan, ScheduleReport, SkillResult
from .registry import REGISTRY, SkillRegistry


class Scheduler:
    """串行调度器。"""

    def __init__(self, registry: SkillRegistry = REGISTRY, tracker=None) -> None:
        self.registry = registry
        self.tracker = tracker  # 可选埋点器（metrics.MetricsTracker，鸭子类型避免循环依赖）

    def run(
        self,
        plan: ExecutionPlan,
        ctx: ExecContext,
        on_step_start=None,
        on_step_end=None,
    ) -> ScheduleReport:
        report = ScheduleReport(plan=plan)
        available = ctx.available_keys()

        for step in plan.steps:
            skill = self.registry.get(step.skill_id)
            if skill is None:
                report.aborted = True
                report.error = f"未注册的 Skill：{step.skill_id}"
                break
            if not skill.meta.is_enable:
                report.aborted = True
                report.error = f"Skill 已停用：{step.skill_id} {skill.meta.name}"
                break

            # 前置依赖检查
            missing = [k for k in skill.meta.input if k not in available]
            if missing:
                report.aborted = True
                report.error = (
                    f"{step.skill_id} {skill.meta.name} 缺少前置输入：{'、'.join(missing)}"
                    "（请通过 --media / --subtitle / --bgm 提供素材）"
                )
                break

            if on_step_start:
                on_step_start(step.skill_id, skill.meta.name)

            t0 = time.perf_counter()
            try:
                merged = {**skill.meta.params, **step.params}
                result = skill.run(ctx, merged)
            except Exception as exc:  # 失败原因要透传给用户，不允许静默吞掉
                result = SkillResult(
                    skill_id=step.skill_id, ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            result.duration = round(time.perf_counter() - t0, 3)

            report.results.append(result)
            if self.tracker:
                self.tracker.track_skill_run(result)
            if on_step_end:
                on_step_end(result)

            if not result.ok:
                report.aborted = True
                report.error = result.error or f"{step.skill_id} 执行失败"
                break

            # 成功后中间结果进入上下文，供后续 Skill 消费
            for key, value in result.outputs.items():
                if key in skill.meta.output:
                    ctx.put(key, value)
                    available.add(key)

        return report
