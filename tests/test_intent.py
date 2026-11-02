"""意图路由测试（规则路由，不依赖本地模型）。"""
from clip_agent import skills  # noqa: F401  注册内置 Skill
from clip_agent.core.intent import IntentRouter


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
