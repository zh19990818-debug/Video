#!/usr/bin/env python3
"""语音转文字：python3 transcribe.py <音频/视频文件> [--model small] [--lang zh] [--out 输出.txt]
依赖：ffmpeg、faster-whisper（pip install faster-whisper）。首次运行会下载模型。"""
import argparse, sys, pathlib

p = argparse.ArgumentParser()
p.add_argument("audio")
p.add_argument("--model", default="small", help="tiny/base/small/medium/large-v3，越大越准越慢")
p.add_argument("--lang", default="zh", help="语言代码，zh/en/…；auto 自动识别")
p.add_argument("--out")
a = p.parse_args()

try:
    from faster_whisper import WhisperModel
except ImportError:
    sys.exit("缺少 faster-whisper：请先运行 pip install faster-whisper")

model = WhisperModel(a.model, compute_type="int8")
segs, info = model.transcribe(
    a.audio, language=None if a.lang == "auto" else a.lang,
    vad_filter=True, initial_prompt="以下是普通话的句子，使用简体中文和标点。" if a.lang == "zh" else None)

def ts(t): return f"{int(t//60):02d}:{int(t%60):02d}"
lines = [f"[{ts(s.start)}] {s.text.strip()}" for s in segs]
text = "\n".join(lines)
out = pathlib.Path(a.out or pathlib.Path(a.audio).with_suffix(".txt"))
out.write_text(text, encoding="utf-8")
print(f"语言={info.language} 时长={ts(info.duration)} 已保存：{out}")
