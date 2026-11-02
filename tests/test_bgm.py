"""S004 BGM 对齐方案与 S005 调色纯函数测试。"""
from clip_agent.skills.s4_bgm_align import make_align_plan
from clip_agent.skills.s5_color_apply import build_filter_chain, jianying_mapping


def test_align_plan_trim():
    plan = make_align_plan(bgm_dur=5.0, target=3.0)
    assert plan["mode"] == "trim"
    assert plan["loops"] == 1
    assert plan["tail_trim"] == 2.0


def test_align_plan_loop_exact():
    plan = make_align_plan(bgm_dur=2.0, target=6.0)
    assert plan == {"mode": "loop", "loops": 3, "tail_trim": 0.0}


def test_align_plan_loop_partial():
    plan = make_align_plan(bgm_dur=2.5, target=6.0)
    assert plan["mode"] == "loop"
    assert plan["loops"] == 3
    assert plan["tail_trim"] == 1.5


def test_filter_chain():
    chain = build_filter_chain({"brightness": 0.1, "contrast": 1.2, "temperature": -0.5})
    assert chain.startswith("eq=brightness=0.100:contrast=1.200")
    assert "colorbalance=rs=-0.100:bs=0.100" in chain


def test_jianying_mapping():
    m = jianying_mapping({"brightness": -0.05, "contrast": 1.15, "saturation": 0.85})
    assert m["亮度"] == -5
    assert m["对比度"] == 15
    assert m["饱和度"] == -15
