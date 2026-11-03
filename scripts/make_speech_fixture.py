#!/usr/bin/env python3
"""生成语音演示素材（macOS 自带 say + ffmpeg）：

- 默认：output/demo/speech.mp4，约 10s 中文口播，用于演示 S006 语音转写
- --long：output/demo/speech_long.mp4，30–60s 中文口播（句间插入停顿），
  用于 D1/D2 真实素材证据与效率基线

非 macOS 环境无法用 say 生成，可直接用任意口播视频演示 S006。
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "output" / "demo"

TEXT_SHORT = (
    "大家好，今天教大家做一道家常菜。先把鸡蛋打散，"
    "加入适量的盐和葱花，搅拌均匀之后放在一边备用。"
)

# --long：含 [[slnc]] 停顿，给 S001 留出真实静音段
TEXT_LONG = (
    "大家好，今天演示剪辑辅助 Agent 的完整流程。[[slnc 1200]] "
    "先识别口播里的静音片段，把停顿自动裁掉，让节奏更紧凑。[[slnc 1000]] "
    "然后校对字幕，按语义重新断句，最长每行十六个字。[[slnc 900]] "
    "接着给画面加一层清冷胶片感，并生成前后对比图，方便确认效果。[[slnc 800]] "
    "最后把这些步骤保存成组合资产，下次一键复用。"
    "整条链路都在本地完成，不上传素材，也不依赖额外服务。"
    "效果不满意时，可以只预览，不落盘。这就是今天要展示的核心能力。"
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--long", action="store_true",
                        help="生成 30–60s 长口播（speech_long.mp4，含停顿）")
    args = parser.parse_args()

    if shutil.which("say") is None or shutil.which("ffmpeg") is None:
        print("需要 macOS 自带 say 与 ffmpeg；非 macOS 请直接用真实口播视频演示 S006。")
        return 1
    voice = pick_chinese_voice()
    if not voice:
        print("未找到中文语音（zh_CN），可在系统设置中安装后重试。")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    text = TEXT_LONG if args.long else TEXT_SHORT
    stem = "speech_long" if args.long else "speech"
    aiff = OUT / f"{stem}.aiff"
    run(["say", "-v", voice, "-o", str(aiff), text])
    run([
        "ffmpeg", "-y", "-hide_banner",
        "-f", "lavfi", "-i", "color=c=0x1a1a2e:s=1280x720:r=25" if args.long
        else "color=c=0x1a1a2e:s=640x360:r=25",
        "-i", str(aiff), "-shortest",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", str(OUT / f"{stem}.mp4"),
    ])
    print(f"\n✓ 语音演示素材已生成：{OUT / (stem + '.mp4')}（语音：{voice}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
