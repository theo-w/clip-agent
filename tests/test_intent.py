"""意图路由测试（规则路由，不依赖本地模型）。"""
import pytest

from clip_agent import skills  # noqa: F401  注册内置 Skill
from clip_agent.core.intent import IntentRouter, plan_from_combo
from clip_agent.core.registry import REGISTRY


def _router() -> IntentRouter:
    return IntentRouter(use_llm=False)


def test_silence_instruction():
    plan = _router().route("识别视频静音片段并自动裁剪")
    assert [s.skill_id for s in plan.steps] == ["S001"]


def test_subtitle_instruction():
    plan = _router().route("批量校对所有字幕错别字，统一字体样式")
    assert [s.skill_id for s in plan.steps] == ["S002"]


def test_highlight_bgm_chain():
    """SDD 示例指令：高光 + 卡点 → S003 → S004 串行编排。"""
    plan = _router().route("筛选高光镜头，匹配BGM卡点")
    assert [s.skill_id for s in plan.steps] == ["S003", "S004"]


def test_color_instruction():
    plan = _router().route("给这段视频套用清冷调色预设")
    assert [s.skill_id for s in plan.steps] == ["S005"]


def test_bgm_only_instruction():
    plan = _router().route("把背景音乐对齐成片时长")
    assert [s.skill_id for s in plan.steps] == ["S004"]


def test_subjective_rejected():
    """边界判断：主观创意类指令拒绝全自动执行。"""
    plan = _router().route("帮我做一个有情绪张力的叙事剪辑")
    assert plan.steps == []
    assert "主观创意" in plan.explanation


def test_unknown_instruction_asks_clarification():
    plan = _router().route("今天天气怎么样")
    assert plan.steps == []
    assert "可用 Skill" in plan.explanation


def test_param_extraction():
    plan = _router().route("用-35dB阈值识别静音，超过1秒的裁掉，高光取前3个")
    params_s1 = plan.steps[0].params
    assert params_s1["silence_threshold"] == -35.0
    assert params_s1["min_duration"] == 1.0
    s3 = next(s for s in plan.steps if s.skill_id == "S003")
    assert s3.params["top_n"] == 3


# ---------------------------------------------------------------- 组合模板（V1.1）

def test_plan_from_combo_builds_ordered_steps():
    plan = plan_from_combo("口播净化", ["S001", "S002"],
                           {"S002": {"max_line_chars": 20, "bad_key": 1}})
    assert [s.skill_id for s in plan.steps] == ["S001", "S002"]
    assert plan.source == "combo"
    assert "S001 → S002" in plan.explanation
    # 每步参数按 Skill 认识的键过滤，未提供的回退默认值
    assert plan.steps[0].params == {}
    assert plan.steps[1].params == {"max_line_chars": 20}


def test_plan_from_combo_rejects_unknown_or_empty_steps():
    with pytest.raises(ValueError, match="S999"):
        plan_from_combo("坏模板", ["S001", "S999"])
    with pytest.raises(ValueError, match="steps"):
        plan_from_combo("空模板", [])


def test_plan_from_combo_rejects_disabled_skill():
    REGISTRY.set_enable("S005", False)
    try:
        with pytest.raises(ValueError, match="已停用"):
            plan_from_combo("含停用 Skill 的模板", ["S005"])
    finally:
        REGISTRY.set_enable("S005", True)
