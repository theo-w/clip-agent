#!/usr/bin/env python3
"""生成语音演示素材（macOS 自带 say + ffmpeg）：

- output/demo/speech.mp4：约 10s 带中文口播的视频，用于演示 S006 语音转写

非 macOS 环境无法用 say 生成，可直接用任意口播视频演示 S006。
"""
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "output" / "demo"

TEXT = (
    "大家好，今天教大家做一道家常菜。先把鸡蛋打散，"
    "加入适量的盐和葱花，搅拌均匀之后放在一边备用。"
)


def run(cmd):
    print("+", " ".join(str(c) for c in cmd[:6]), "…")
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-1200:])
        sys.exit(1)


def pick_chinese_voice() -> str:
    """优先 Tingting，其次任意 zh_CN 语音。"""
    proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    lines = [l for l in proc.stdout.splitlines() if "zh_CN" in l]
    for line in lines:
        if line.split("zh_CN")[0].strip().startswith("Tingting"):
            return "Tingting"
    if lines:
        return lines[0].split("zh_CN")[0].strip()
    return ""


def main() -> int:
    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        print("需要 macOS 自带 say 与 ffmpeg；非 macOS 请直接用真实口播视频演示 S006。")
        return 1
    voice = pick_chinese_voice()
    if not voice:
        print("未找到中文语音（zh_CN），可在系统设置中安装后重试。")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    aiff = OUT / "speech.aiff"
    run(["say", "-v", voice, "-o", str(aiff), TEXT])
    run([
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=640x360:r=25",
        "-i", str(aiff), "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", str(OUT / "speech.mp4"),
    ])
    print(f"\n✓ 语音演示素材已生成：{OUT / 'speech.mp4'}（语音：{voice}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
