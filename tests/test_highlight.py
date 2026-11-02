"""S003 过短镜头合并逻辑测试。"""
from clip_agent.skills.s3_highlight import merge_short_shots


def test_merge_short_shot_into_previous():
    shots = [(0.0, 2.0), (2.0, 2.2), (2.2, 4.0)]
    assert merge_short_shots(shots, 0.5) == [(0.0, 2.2), (2.2, 4.0)]


def test_keep_long_shots():
    shots = [(0.0, 2.0), (2.0, 4.0)]
    assert merge_short_shots(shots, 0.5) == [(0.0, 2.0), (2.0, 4.0)]


def test_first_short_shot_stays():
    # 第一个镜头没有"前一个"可合并，保持原样
    shots = [(0.0, 0.2), (0.2, 3.0)]
    assert merge_short_shots(shots, 0.5) == [(0.0, 0.2), (0.2, 3.0)]


def test_short_shot_far_from_start_still_merges():
    # 回归：旧逻辑按"距已合并片段起点"判断，短镜头离起点超过阈值时会被漏合
    shots = [(0.0, 1.2), (1.2, 1.3), (1.3, 3.0)]
    assert merge_short_shots(shots, 1.0) == [(0.0, 1.3), (1.3, 3.0)]
