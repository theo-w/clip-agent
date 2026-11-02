#!/usr/bin/env python3
"""生成演示素材（需要 ffmpeg）：

- output/demo/demo.mp4：6s 视频，3 个镜头（2s/2s/2s），中间 1.2s 静音
- output/demo/demo.srt：含半角标点、超长行、时间轴重叠、连续重复等问题的字幕
- output/demo/bgm.m4a：2.5s 的 BGM（演示循环对齐）
"""
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "output" / "demo"

SRT_CONTENT = """1
00:00:00,200 --> 00:00:01,800
大家好,今天教大家做一道家常菜.

2
00:00:01,700 --> 00:00:03,500
这道菜的做法非常简单,我们先把鸡蛋打散,然后加入适量的盐和葱花,搅拌均匀之后放在一边备用就行了

3
00:00:03,600 --> 00:00:05,000
下面我们开始热油.

4
00:00:05,100 --> 00:00:06,000
下面我们开始热油.
"""


def run(cmd):
    print("+", " ".join(cmd[:6]), "…")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-1500:])
        sys.exit(1)


def main() -> int:
    if not OUT.exists():
        OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    video = OUT / "demo.mp4"
    run([
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "testsrc2=duration=2:size=640x360:rate=25",
        "-f", "lavfi", "-i", "smptebars=duration=2:size=640x360:rate=25",
        "-f", "lavfi", "-i", "rgbtestsrc=duration=2:size=640x360:rate=25",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];"
        "[3:a]volume=0:enable='between(t,2,3.2)'[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(video),
    ])

    (OUT / "demo.srt").write_text(SRT_CONTENT, encoding="utf-8")

    run([
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=2.5",
        "-c:a", "aac", "-b:a", "128k", str(OUT / "bgm.m4a"),
    ])

    print(f"\n✓ 演示素材已生成：{OUT}")
    print("  - demo.mp4  6s，3 个镜头，2.0~3.2s 静音")
    print("  - demo.srt  含标点/折行/重叠/重复问题")
    print("  - bgm.m4a   2.5s BGM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
