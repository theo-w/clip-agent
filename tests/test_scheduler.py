"""调度引擎测试：顺序执行、中间结果传递、失败终止保留、依赖检查、启停。"""
import pytest

from clip_agent.core.models import ExecContext, ExecutionPlan, PlanStep, SkillMeta
from clip_agent.core.registry import SkillRegistry
from clip_agent.core.scheduler import Scheduler
from clip_agent.skills.base import Skill


class FakeSkill(Skill):
    def __init__(self, skill_id, output_key=None, fail=False, consume=None):
        self.meta = SkillMeta(
            skill_id=skill_id, name=skill_id, desc="",
            params={}, input=consume or [],
            output=[output_key] if output_key else [],
        )
        self._output_key = output_key
        self._fail = fail

    def run(self, ctx, params):
        if self._fail:
            return self.fail("模拟失败")
        return self.success({self._output_key: "value"} if self._output_key else {})


def _registry(*skls) -> SkillRegistry:
    reg = SkillRegistry()
    for s in skls:
        reg.register(s)
    return reg


def _plan(*skill_ids):
    return ExecutionPlan(intent="t", steps=[PlanStep(sid) for sid in skill_ids])


def test_merge_overrides_reports_unknown_params():
    """修改参数重跑：未知参数不再被静默忽略，返回值用于提示可用参数名。"""
    import clip_agent.skills  # noqa: F401  导入即注册内置 Skill
    from clip_agent.__main__ import _merge_overrides

    plan = ExecutionPlan(intent="t", steps=[PlanStep("S001", params={})])
    unknown = _merge_overrides(plan, {"silence_threshold": -40, "no_such_param": 1})
    assert "no_such_param" in unknown
    assert "silence_threshold" not in unknown
    assert plan.steps[0].params["silence_threshold"] == -40


def test_sequential_run_with_intermediate():
    """A 的产出进入上下文，B 才能执行（中间结果接力）。"""
    reg = _registry(FakeSkill("A", output_key="x"), FakeSkill("B", consume=["x"]))
    report = Scheduler(registry=reg).run(_plan("A", "B"), ExecContext())
    assert report.ok
    assert [r.skill_id for r in report.results] == ["A", "B"]


def test_failure_aborts_and_keeps_completed():
    """失败策略：单 Skill 失败终止后续，保留已完成结果。"""
    reg = _registry(
        FakeSkill("A", output_key="x"),
        FakeSkill("B", fail=True),
        FakeSkill("C"),
    )
    report = Scheduler(registry=reg).run(_plan("A", "B", "C"), ExecContext())
    assert report.aborted
    assert [r.skill_id for r in report.results] == ["A", "B"]
    assert report.error == "模拟失败"
    assert report.results[0].ok  # 已完成结果保留


def test_missing_input_aborts():
    reg = _registry(FakeSkill("A", consume=["audio_track"]))
    report = Scheduler(registry=reg).run(_plan("A"), ExecContext())
    assert report.aborted
    assert "前置输入" in report.error


def test_disabled_skill_aborts():
    reg = _registry(FakeSkill("A"))
    reg.set_enable("A", False)
    report = Scheduler(registry=reg).run(_plan("A"), ExecContext())
    assert report.aborted
    assert "停用" in report.error


def test_unknown_skill_aborts():
    reg = _registry()
    report = Scheduler(registry=reg).run(_plan("X999"), ExecContext())
    assert report.aborted
    assert "未注册" in report.error


def test_skill_exception_wrapped():
    class Boom(FakeSkill):
        def run(self, ctx, params):
            raise RuntimeError("炸了")

    reg = _registry(Boom("A"))
    report = Scheduler(registry=reg).run(_plan("A"), ExecContext())
    assert report.aborted
    assert "RuntimeError" in report.error
