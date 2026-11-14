#!/usr/bin/env python3
"""办公室反转短片 v2：监控视角 -> 慢动作推镜 -> 定格锁定 -> 故障加速 -> 静音 -> 暖色反转。
用法: office_twist_v2.py 输入.mov 输出.mp4"""
import sys, subprocess, wave, tempfile, os
import numpy as np

IN, OUT = sys.argv[1], sys.argv[2]
F = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
SR = 44100
T = dict(s1=2.0, s2=4.0, s3=1.5, s4=1.5, s5=0.6, s6=1.8, s7=1.0, s8=1.3)
starts, acc = {}, 0.0
for k, v in T.items():
    starts[k] = acc; acc += v
TOTAL = acc

# ---------- 音效 ----------
def synth():
    t = np.arange(int(TOTAL * SR)) / SR
    a = np.zeros_like(t)
    rng = np.random.default_rng(1)
    def seg(k): return (t >= starts[k]) & (t < starts[k] + T[k])
    # 低频嗡鸣：开场到故障段
    dm = (t < starts['s5'])
    a += dm * 0.18 * (np.sin(2*np.pi*48*t) + 0.5*np.sin(2*np.pi*72*t + 1))
    # 心跳：S2 慢，S3 停顿，S4 加快
    def thump(t0, amp=0.9):
        nonlocal a
        m = (t >= t0) & (t < t0 + 0.25)
        tt = t - t0
        a += m * amp * np.sin(2*np.pi*(70 - 120*tt)*tt) * np.exp(-14*np.clip(tt, 0, None))
    x = starts['s2']
    while x < starts['s3']:
        thump(x); thump(x + 0.22, 0.6); x += 1.0
    x = starts['s4']
    while x < starts['s5']:
        thump(x); thump(x + 0.12, 0.6); x += 0.5
    # S3 定格：高频电流声 + 锁定“滴”
    m = seg('s3')
    a += m * 0.05 * rng.standard_normal(len(t)) * (np.sin(2*np.pi*3*t) > 0)
    for k in (0.1, 0.6):
        tt = t - (starts['s3'] + k); mm = (tt >= 0) & (tt < 0.15)
        a += mm * 0.35 * np.sin(2*np.pi*1800*tt)
    # S4 上升音
    m = seg('s4'); tt = np.clip(t - starts['s4'], 0, None)
    a += m * 0.25 * np.sin(2*np.pi*(200 + 900*tt/T['s4'])*tt) * (tt / T['s4'])
    a += m * 0.08 * rng.standard_normal(len(t)) * (tt / T['s4'])
    # S5 静音（已无声），S6 开头：爆破+清脆提示音
    tt = t - starts['s6']; mm = (tt >= 0) & (tt < 0.5)
    a += mm * 0.5 * rng.standard_normal(len(t)) * np.exp(-30*np.clip(tt, 0, None))
    for i, f in enumerate((784, 988, 1319)):
        tt = t - (starts['s6'] + 0.05 + i*0.09); mm = (tt >= 0) & (tt < 1.0)
        a += mm * 0.3 * np.sin(2*np.pi*f*tt) * np.exp(-5*np.clip(tt, 0, None))
    # S7 定格：喜剧“咚”
    tt = t - starts['s7']; mm = (tt >= 0) & (tt < 0.6)
    a += mm * 0.6 * np.sin(2*np.pi*(180 - 100*np.clip(tt, 0, .3)/.3)*np.clip(tt, 0, None)) * np.exp(-8*np.clip(tt, 0, None))
    # S8 片尾轻柔和弦
    tt = t - starts['s8']; mm = tt >= 0
    for f in (523, 659, 784):
        a += mm * 0.1 * np.sin(2*np.pi*f*np.clip(tt, 0, None)) * np.exp(-2*np.clip(tt, 0, None))
    a = np.tanh(a * 1.2) * 0.8
    a[-int(0.3*SR):] *= np.linspace(1, 0, int(0.3*SR))
    pcm = (a * 32767).astype('<i2')
    p = os.path.join(tempfile.mkdtemp(), "a.wav")
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    return p

wav = synth()

# ---------- 画面 ----------
def txt(text, size, color, y, en=None, x="(w-tw)/2", extra=""):
    e = f":enable='{en}'" if en else ""
    return (f"drawtext=fontfile={F}:text='{text}':fontsize={size}:fontcolor={color}"
            f":x={x}:y={y}{e}:borderw=3:bordercolor=black@0.7{extra}")

COMMON = "fps=30,setsar=1"
CCTV = ("eq=saturation=0.15:contrast=1.35:brightness=-0.1,noise=alls=22:allf=t,"
        "drawgrid=width=720:height=4:thickness=1:color=black@0.3,vignette=PI/2.6")
REC = (f"drawtext=fontfile={F}:text='● REC':fontsize=34:fontcolor=red:x=40:y=50:enable='lt(mod(t,1),0.6)',"
       f"drawtext=fontfile={F}:text='CAM-03':fontsize=30:fontcolor=white:x=w-tw-40:y=50,"
       f"drawtext=fontfile={F}:text='17\\:58\\:%{{eif\\:30+t\\:d\\:2}}':fontsize=30:fontcolor=white:x=40:y=h-80")

def push(dur, z0, z1):  # 推镜
    return (f"scale=w='720*({z0}+({z1}-{z0})*t/{dur})':h=-2:eval=frame,crop=720:1280")

g = []
# S1 开场字卡
g.append(f"color=c=black:s=720x1280:d={T['s1']}:r=30,"
         + txt("周一  17：58", 70, "white", 500) + ","
         + txt("某间普通的办公室", 40, "0xaaaaaa", 600) + ","
         + f"noise=alls=30:allf=t,fade=in:0:12,fade=out:st={T['s1']-0.4}:d=0.4,{COMMON}[v1]")
# S2 慢动作+推镜
g.append(f"[0:v]trim=0:2,setpts=2*(PTS-STARTPTS),{COMMON},{push(T['s2'],1.0,1.3)},{CCTV},{REC},"
         + txt("他已经盯着这东西三天了", 46, "white", "h-260", "between(t,0.3,2.0)") + ","
         + txt("没人知道，里面藏着什么", 46, "white", "h-260", "between(t,2.2,3.9)")
         + f",fade=out:st={T['s2']-0.15}:d=0.15,setsar=1[v2]")
# S3 定格+目标锁定
b = 6
g.append(f"[0:v]trim=start_frame=70:end_frame=71,setpts=PTS-STARTPTS,{COMMON},tpad=stop_mode=clone:stop_duration={T['s3']},"
         f"{push(T['s3'],1.3,1.6)},{CCTV},"
         f"drawbox=x=170:y=780:w=380:h=220:color=red:t=4:enable='gte(t,0.1)',"
         f"drawbox=x=150:y=760:w=420:h=260:color=red@0.6:t=2:enable='gte(t,0.1)',"
         + txt("目标物：不明", 44, "red", 690, "gte(t,0.2)") + ","
         + txt("危险等级：???", 40, "0xffcc00", "h-260", "gte(t,0.7)")
         + f",{REC},setsar=1[v3]")
# S4 加速+故障+抖动
g.append(f"[0:v]trim=2.0:5.0,setpts=(PTS-STARTPTS)/2,{COMMON},"
         f"scale=860:-2,crop=720:1280:x='70+14*sin(t*60)':y='(ih-1280)/2+10*cos(t*47)',"
         f"{CCTV},rgbashift=rh=-10:bh=10:gv=4:enable='lt(mod(t,0.3),0.1)',"
         f"colorbalance=rs=.35:rm=.2,"
         + txt("直到今天……", 70, "red", "h-300") + ",setsar=1[v4]")
# S5 静音黑场（0.6 秒空白，末尾白闪）
g.append(f"color=c=black:s=720x1280:d={T['s5']}:r=30,fade=out:st=0.45:d=0.15:color=white,{COMMON}[v5]")
# S6 反转：暖色+冲击放大
g.append(f"[0:v]trim=6.3:8.1,setpts=PTS-STARTPTS,{COMMON},eq=saturation=1.4:brightness=0.06,"
         f"{push(T['s6'],1.25,1.0)},"
         f"fade=in:0:4:color=white,"
         + txt("原来，只是在研究新到的小玩意", 44, "0xffe066", "h-290") + ",setsar=1[v6]")
# S7 定格笑脸+表情包大字
g.append(f"[0:v]trim=start_frame=240:end_frame=241,setpts=PTS-STARTPTS,{COMMON},tpad=stop_mode=clone:stop_duration={T['s7']},"
         f"eq=saturation=1.4:brightness=0.06,"
         f"{push(T['s7'],1.0,1.12)},"
         + txt("我 以 为 ？！", 96, "white", 150, extra=":box=1:boxcolor=red@0.85:boxborderw=18") + ",setsar=1[v7]")
# S8 片尾
g.append(f"color=c=0x101010:s=720x1280:d={T['s8']}:r=30,"
         + txt("—— 完 ——", 60, "white", 560) + ","
         + txt("虚构短片 · 剧情纯属娱乐", 30, "0x888888", 660) + f",fade=in:0:8,{COMMON}[v8]")

fc = ";".join(g) + ";[v1][v2][v3][v4][v5][v6][v7][v8]concat=n=8:v=1:a=0,format=yuv420p[v]"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", IN, "-i", wav, "-filter_complex", fc,
                "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-c:a", "aac",
                "-shortest", OUT], check=True)
print("done", TOTAL)
