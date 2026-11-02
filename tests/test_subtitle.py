"""S002 字幕修正纯函数测试。"""
from clip_agent.media.analyzer import SubtitleEntry
from clip_agent.skills.s2_subtitle_fix import (
    _fix_punctuation, _split_line, fix_entries, write_srt,
)


def test_fix_punctuation_chinese():
    assert _fix_punctuation("大家好,今天教大家做一道家常菜.") == "大家好，今天教大家做一道家常菜。"


def test_fix_punctuation_keeps_numbers_and_english():
    # 数字小数点不转全角；英文句子不动
    assert _fix_punctuation("版本是3.5吗?") == "版本是3.5吗？"
    assert _fix_punctuation("Hello, world.") == "Hello, world."


def test_split_line_wraps_long_text():
    line = "我们先把鸡蛋打散，然后加入适量的盐和葱花，搅拌均匀之后放在一边备用就行了"
    lines = _split_line(line, 18)
    assert len(lines) >= 2
    assert all(len(l) <= 18 for l in lines)
    assert "".join(lines) == line


def test_split_line_caps_two_lines_on_very_long_text():
    # 两行上限是硬约束：60+ 字无标点长句也绝不能折出第三行
    line = "这一句话完全没有标点符号并且远超两行字幕宽度的上限所以必须在保证只有两行的前提下进行硬切处理才可以"
    assert len(line) > 40
    lines = _split_line(line, 18)
    assert len(lines) == 2
    assert "".join(lines) == line


def test_split_line_caps_two_lines_on_long_punctuated_text():
    # 旧实现会把这句递归折成 3 行；两行上限下应恰好 2 行
    line = "这道菜的做法非常简单,我们先把鸡蛋打散,然后加入适量的盐和葱花,搅拌均匀之后放在一边备用就行了"
    lines = _split_line(line, 18)
    assert len(lines) == 2
    assert "".join(lines) == line


def test_split_line_prefers_valid_window_cut():
    # 30 字、标点都落在可行窗口外时，应在窗口内硬切，保证两行都 ≤ max_chars
    line = "前,面后" + "字" * 28  # 标点只在两端，中间无可行切点
    lines = _split_line(line, 18)
    assert len(lines) == 2
    assert all(len(l) <= 18 for l in lines)


def test_fix_entries_full_pipeline(tmp_path):
    entries = [
        SubtitleEntry(1, 0.2, 1.8, "大家好,今天教大家做一道家常菜."),
        # 超长 + 与上一条时间轴重叠
        SubtitleEntry(2, 1.7, 3.5,
                      "这道菜的做法非常简单,我们先把鸡蛋打散,然后加入适量的盐和葱花,搅拌均匀之后放在一边备用就行了"),
        SubtitleEntry(3, 3.6, 5.0, "下面我们开始热油."),
        # 与上一条重复
        SubtitleEntry(4, 5.1, 6.0, "下面我们开始热油."),
    ]
    fixed, issues = fix_entries(entries, {
        "max_line_chars": 18, "fix_overlap": True, "dedupe": True,
    })
    types = {it["type"] for it in issues}
    assert {"punctuation", "line_wrap", "overlap", "duplicate"} <= types
    # 重复条目被删除
    assert len(fixed) == 3
    # 重叠被修正：第二条起始对齐到第一条结束
    assert abs(fixed[1].start - 1.8) < 1e-6
    # 标点已全角化
    assert fixed[0].text.endswith("。")
    # 重新编号连续
    assert [e.index for e in fixed] == [1, 2, 3]

    write_srt(tmp_path / "out.srt", fixed)
    content = (tmp_path / "out.srt").read_text(encoding="utf-8")
    assert "-->" in content and "家常菜。" in content
