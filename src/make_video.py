#!/usr/bin/env python3
"""棕熊（藏马熊）科普短片：纯 Python 程序化渲染 -> ffmpeg 合成。"""
import math, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1280, 720, 30
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
def font(sz): return ImageFont.truetype(FONT, sz)
rnd = random.Random(7)

# ---------- 熊的剪影（超采样绘制一次，之后缩放复用） ----------
def bear_sprite(h=400, facing=1):
    S = 3; w = int(h*1.5)
    im = Image.new("L", (w*S, h*S), 0); d = ImageDraw.Draw(im)
    def E(cx, cy, rx, ry): d.ellipse([(cx-rx)*S, (cy-ry)*S, (cx+rx)*S, (cy+ry)*S], fill=255)
    u = h/100.0
    E(60*u*.8+10*u, 45*u, 36*u, 26*u)          # 躯干
    E(36*u, 30*u, 20*u, 22*u)                  # 肩峰
    E(104*u, 50*u, 22*u, 22*u)                 # 臀
    E(22*u, 52*u, 17*u, 15*u)                  # 头
    E(9*u, 58*u, 9*u, 7*u)                     # 口鼻
    E(26*u, 38*u, 5*u, 5*u)                    # 耳
    for lx in (30, 48, 92, 112):               # 四肢
        d.rounded_rectangle([(lx-6)*u*S, 55*u*S, (lx+7)*u*S, 92*u*S], 6*u*S, fill=255)
        E(lx+0.5, 92, 9, 4)
    im = im.resize((w, h), Image.LANCZOS)
    if facing == -1: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im
BEAR = bear_sprite(400)

def tint_sprite(im, rgb, alpha=255):
    out = Image.new("RGBA", im.size, rgb + (0,)); out.putalpha(im.point(lambda v: v*alpha//255)); return out

# ---------- 背景元素 ----------
def vgrad(top, bot):
    a = np.linspace(0, 1, H)[:, None, None]
    t = np.array(top)[None, None, :]; b = np.array(bot)[None, None, :]
    return Image.fromarray((t*(1-a)+b*a).repeat(W, 1).astype("uint8"))

def mountains(color, base, amp, seed, rough=0.5):
    r = random.Random(seed); pts = []; y = base
    n = 40; xs = np.linspace(0, W, n)
    for x in xs:
        y = base - amp*(0.5+0.5*math.sin(x/170.0+seed)) - r.random()*amp*rough
        pts.append((x, y))
    poly = [(0, H)] + pts + [(W, H)]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(im).polygon(poly, fill=color)
    return im

def pine(d, x, y, s, col):
    for i in range(4):
        w = s*(0.5+0.22*i); yy = y - s*1.1 + i*s*0.38
        d.polygon([(x, yy-s*0.6), (x-w, yy+s*0.2), (x+w, yy+s*0.2)], fill=col)
    d.rectangle([x-s*0.06, y-s*0.2, x+s*0.06, y+s*0.15], fill=col)

def forest(col, base, seed, count=26, size=(60, 110)):
    r = random.Random(seed); im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(count): pine(d, r.randint(-20, W+20), base+r.randint(-10, 25), r.randint(*size), col)
    d.rectangle([0, base+20, W, H], fill=col); return im

class Snow:
    def __init__(self, n=160, wind=1.5):
        self.p = [[rnd.random()*W, rnd.random()*H, rnd.uniform(0.6, 2.4), rnd.uniform(1, 3.2)] for _ in range(n)]
        self.wind = wind
    def draw(self, img, t):
        d = ImageDraw.Draw(img, "RGBA")
        for x, y, sp, r in self.p:
            xx = (x + t*30*self.wind*sp + math.sin(t*1.3+y)*8) % W; yy = (y + t*45*sp) % H
            d.ellipse([xx-r, yy-r, xx+r, yy+r], fill=(255, 255, 255, int(70+60*sp/2.4)))

def vignette():
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2)
    a = np.clip((d-0.55)*0.9, 0, 0.75)
    return Image.fromarray((a*255).astype("uint8"))
VIG = vignette(); BLACK = Image.new("RGB", (W, H), (0, 0, 0))

def ease(x): x = max(0, min(1, x)); return x*x*(3-2*x)
def fade(t, a, b, fi=0.6, fo=0.6):  # 在 [a,b] 内淡入淡出的透明度
    return ease((t-a)/fi) * ease((b-t)/fo)

def text(img, s, xy, sz, fill=(255, 255, 255), a=1.0, anchor="la", shadow=True, stroke=0):
    if a <= 0.01: return
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); f = font(sz)
    if shadow: d.text((xy[0]+2, xy[1]+3), s, font=f, fill=(0, 0, 0, int(160*a)), anchor=anchor)
    d.text(xy, s, font=f, fill=fill+(int(255*a),), anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, int(200*a)))
    img.alpha_composite(lay)

def panel(img, box, a=1.0, col=(8, 10, 16), alpha=150):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle(box, 14, fill=col+(int(alpha*a),)); img.alpha_composite(lay)

def paste_bear(img, x, y, scale, col, alpha=255, flip=False):
    sp = BEAR if not flip else BEAR.transpose(Image.FLIP_LEFT_RIGHT)
    s = sp.resize((int(sp.width*scale), int(sp.height*scale)), Image.LANCZOS)
    img.alpha_composite(tint_sprite(s, col, alpha), (int(x), int(y)))

# ---------- 预渲染各场景静态层 ----------
def scene_bg_dusk():
    im = vgrad((24, 34, 66), (232, 150, 104)).convert("RGBA")
    d = ImageDraw.Draw(im); d.ellipse([880, 360, 1040, 520], fill=(255, 226, 170, 255))
    im.alpha_composite(mountains((70, 84, 120, 255), 470, 150, 1))
    im.alpha_composite(mountains((38, 48, 78, 255), 560, 120, 3))
    im.alpha_composite(forest((16, 22, 36, 255), 640, 5))
    return im
def scene_bg_night(red=False):
    top, bot = ((8, 10, 22), (30, 38, 70)) if not red else ((16, 6, 10), (58, 26, 34))
    im = vgrad(top, bot).convert("RGBA"); d = ImageDraw.Draw(im)
    for _ in range(90):
        x, y = rnd.randint(0, W), rnd.randint(0, 330); d.point((x, y), fill=(255, 255, 255, rnd.randint(80, 230)))
    d.ellipse([1040, 70, 1100, 130], fill=(240, 240, 225, 255))
    c1, c2, c3 = ((36, 46, 78, 255), (20, 26, 48, 255), (8, 10, 18, 255)) if not red else ((70, 40, 52, 255), (40, 22, 30, 255), (14, 6, 8, 255))
    im.alpha_composite(mountains(c1, 470, 130, 2)); im.alpha_composite(mountains(c2, 540, 100, 6))
    im.alpha_composite(forest(c3, 640, 9, 34))
    return im
def scene_bg_cabin():
    im = scene_bg_night(red=True); d = ImageDraw.Draw(im)
    # 开拓村的简陋木屋，窗内有微光
    d.polygon([(380, 520), (560, 440), (740, 520)], fill=(10, 6, 8, 255)); d.rectangle([400, 520, 720, 650], fill=(12, 8, 10, 255))
    d.rectangle([590, 560, 640, 610], fill=(246, 190, 100, 255))
    return im
def scene_bg_dawn():
    im = vgrad((40, 56, 92), (250, 208, 150)).convert("RGBA")
    im.alpha_composite(mountains((120, 130, 160, 255), 460, 140, 4)); im.alpha_composite(mountains((60, 70, 100, 255), 540, 110, 8))
    im.alpha_composite(forest((18, 26, 38, 255), 640, 11, 30)); return im

BG = dict(dusk=scene_bg_dusk(), night=scene_bg_night(), cabin=scene_bg_cabin(), dawn=scene_bg_dawn())
BGPLAIN = vgrad((14, 20, 34), (28, 40, 60)).convert("RGBA")

# ---------- 时间线 ----------
# (start, end, name)
SC = [(0, 8, "title"), (8, 21, "species"), (21, 41, "sankebetsu"), (41, 51, "other"),
      (51, 65, "why"), (65, 83, "safety"), (83, 92, "end")]
TOTAL = SC[-1][1]
snow = Snow(180, 1.6); snow_n = Snow(90, 0.8)

def draw_icon(img, kind, cx, cy, col=(255, 214, 150)):
    d = ImageDraw.Draw(img)
    if kind == "food":      # 食物不足：空碗
        d.arc([cx-34, cy-30, cx+34, cy+30], 0, 180, fill=col, width=6); d.line([cx-34, cy, cx+34, cy], fill=col, width=6)
        d.line([cx-20, cy+38, cx+20, cy+38], fill=col, width=6)
    elif kind == "surprise":  # 突然遭遇：感叹号
        d.rounded_rectangle([cx-7, cy-38, cx+7, cy+10], 6, fill=col); d.ellipse([cx-8, cy+22, cx+8, cy+38], fill=col)
    elif kind == "cubs":     # 护幼：大小两个圈
        d.ellipse([cx-40, cy-26, cx+6, cy+20], outline=col, width=6); d.ellipse([cx+14, cy-2, cx+40, cy+24], outline=col, width=6)
    elif kind == "human":    # 人类食物：垃圾桶
        d.polygon([(cx-28, cy-18), (cx+28, cy-18), (cx+22, cy+36), (cx-22, cy+36)], outline=col, width=6)
        d.line([cx-34, cy-24, cx+34, cy-24], fill=col, width=6)

def draw_scene(name, t, img):  # t: 场景内相对时间
    if name == "title":
        img.alpha_composite(BG["dusk"]); snow_n.draw(img, t)
        paste_bear(img, 130+t*6, 292, 0.52, (8, 10, 18))
        a = ease((t-0.8)/1.5)
        text(img, "熊 出 没", (W//2, 190), 96, (255, 242, 222), a, "mm", stroke=2)
        text(img, "藏马熊与人类的距离 · 从北海道三毛别事件说起", (W//2, 262), 30, (255, 226, 190), ease((t-2)/1.5), "mm")
    elif name == "species":
        img.alpha_composite(BGPLAIN); snow_n.draw(img, t+3)
        paste_bear(img, 680, 300, 0.78, (6, 8, 14), 255, flip=True)
        text(img, "藏马熊", (80, 90), 62, (255, 236, 205), fade(t, 0.3, 99), "la")
        text(img, "Ursus arctos pruinosus · 棕熊的青藏高原亚种", (82, 168), 24, (170, 200, 230), fade(t, 0.8, 99))
        lines = ["体型：成年个体体重可达两百公斤以上", "分布：青藏高原及周边高山草甸、灌丛", "食性：杂食，以植物、鼠兔、旱獭、腐肉为主", "亲缘：与日本北海道的“蝦夷棕熊”同属棕熊"]
        for i, s in enumerate(lines):
            text(img, "▍"+s, (86, 240+i*62), 31, (240, 244, 250), fade(t, 1.6+i*1.5, 99))
    elif name == "sankebetsu":
        img.alpha_composite(BG["cabin"] if t < 12 else BG["night"]); snow.draw(img, t)
        if t < 12: paste_bear(img, 880, 330, 0.5, (4, 3, 5), 230, flip=False)
        else: pass
        tit = fade(t, 0.3, 99)
        panel(img, (60, 56, 760, 150), tit); text(img, "1915 · 三毛别棕熊事件", (86, 72), 48, (255, 214, 190), tit)
        items = [(2.0, "地点：北海道苫前郡三毛别（今苫前町）"), (4.5, "时间：1915年12月9日—14日，严冬，熊本应冬眠"),
                 (7.5, "一头棕熊闯入开拓村民宅，连续袭击数户"), (10.5, "结果：7人死亡、3人重伤，是日本史上最严重的兽害"),
                 (14.0, "熊体长约2.7米、体重约340公斤"), (16.5, "12月14日，猎人山本兵吉将其击毙")]
        for i, (st, s) in enumerate(items):
            a = fade(t, st, 99); panel(img, (60, 172+i*58, 800, 224+i*58), a, alpha=120)
            text(img, s, (80, 177+i*58), 27, (245, 240, 235), a)
    elif name == "other":
        img.alpha_composite(BGPLAIN); snow_n.draw(img, t)
        text(img, "它不是孤例", (W//2, 120), 56, (255, 220, 190), fade(t, 0.2, 99), "mm")
        cards = [("1970", "福冈大学登山队遇袭", "日高山脉，三名队员遇难", 1.2), ("近年", "日本熊出没持续增加", "山区食物歉收，熊进入人类生活圈", 3.6)]
        for i, (a1, b1, c1, st) in enumerate(cards):
            x0 = 90+i*560; al = fade(t, st, 99); panel(img, (x0, 220, x0+500, 520), al, alpha=170)
            text(img, a1, (x0+30, 245), 64, (255, 190, 120), al); text(img, b1, (x0+30, 345), 34, (255, 255, 255), al)
            text(img, c1, (x0+30, 405), 24, (190, 210, 235), al)
        text(img, "资料来源：公开报道与历史记载，数字取其通行说法", (W//2, 640), 20, (130, 150, 175), fade(t, 4, 99), "mm", shadow=False)
    elif name == "why":
        img.alpha_composite(BGPLAIN); snow_n.draw(img, t)
        text(img, "熊为什么会伤人？", (W//2, 90), 54, (255, 236, 205), fade(t, 0.2, 99), "mm")
        cs = [("food", "食物不足", "歉收年饥饿，冒险觅食"), ("surprise", "突然遭遇", "近距离惊吓，触发防御"),
              ("cubs", "母熊护幼", "最危险的情形之一"), ("human", "人类食物", "垃圾、饲喂让熊失去戒心")]
        for i, (k, a1, b1) in enumerate(cs):
            x0 = 60+i*300; al = fade(t, 1.0+i*2.4, 99); panel(img, (x0, 190, x0+270, 500), al, alpha=165)
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); draw_icon(lay, k, x0+135, 270)
            lay.putalpha(lay.getchannel("A").point(lambda v: int(v*al))); img.alpha_composite(lay)
            text(img, a1, (x0+135, 350), 36, (255, 255, 255), al, "mm"); text(img, b1, (x0+135, 420), 20, (180, 205, 235), al, "mm")
        text(img, "绝大多数熊并不主动“猎杀”人，冲突多源于误遇与食物", (W//2, 600), 26, (255, 214, 160), fade(t, 10.5, 99), "mm")
    elif name == "safety":
        img.alpha_composite(BG["dawn"]); snow_n.draw(img, t)
        panel(img, (60, 50, 700, 640), fade(t, 0.1, 99), alpha=165)
        text(img, "遇到熊，请记住", (96, 70), 48, (255, 224, 170), fade(t, 0.3, 99))
        st = [("1", "出行结伴，发出声响，避免突然撞见"), ("2", "发现熊：保持冷静，不要尖叫奔跑"),
              ("3", "面向它，缓慢后退，拉开距离"), ("4", "携带熊用喷雾，学会提前使用"),
              ("5", "若被扑倒：护住后颈、俯卧装死（防御性攻击）"), ("6", "食物与垃圾密封收好，绝不投喂")]
        for i, (n, s) in enumerate(st):
            a = fade(t, 1.2+i*2.5, 99); y = 150+i*76
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).ellipse([96, y, 144, y+48], fill=(255, 196, 120, int(255*a)))
            img.alpha_composite(lay); text(img, n, (120, y+24), 30, (30, 20, 10), a, "mm", shadow=False)
            text(img, s, (162, y+6), 25, (255, 255, 255), a)
        paste_bear(img, 760, 330, 0.55, (10, 14, 24), 255, flip=True)
    elif name == "end":
        img.alpha_composite(BG["dusk"]); snow_n.draw(img, t+5)
        paste_bear(img, 760, 305, 0.5, (8, 10, 18), 255, flip=True)
        text(img, "它们不是怪物，只是野兽", (W//2, 200), 56, (255, 240, 220), fade(t, 0.5, 99), "mm", stroke=2)
        text(img, "保持距离，就是对彼此最好的尊重", (W//2, 280), 34, (255, 218, 175), fade(t, 2.2, 99), "mm")

def render_frame(i):
    t = i/FPS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for a, b, n in SC:
        if a <= t < b:
            draw_scene(n, t-a, img)
            # 切场淡入淡出
            f = min(ease((t-a)/0.6), ease((b-t)/0.6)); break
    rgb = img.convert("RGB"); rgb = Image.composite(BLACK, rgb, VIG.point(lambda v: int(v*0.7)))
    if f < 1: rgb = Image.blend(BLACK, rgb, f)
    return rgb

# ---------- 音频：风声 + 低沉氛围垫音 ----------
def make_audio(path, dur):
    sr = 44100; n = int(sr*dur); r = np.random.default_rng(3); t = np.arange(n)/sr
    noise = r.standard_normal(n); k = 600
    wind = np.convolve(noise, np.ones(k)/k, "same"); wind /= np.abs(wind).max()
    wind *= 0.5+0.5*np.sin(2*np.pi*t/9.0+1)**2
    pad = sum(np.sin(2*np.pi*f*t+p)*a for f, p, a in [(55, 0, .5), (82.4, 1, .35), (110, 2, .25), (164.8, .5, .12)])
    pad *= 0.6+0.4*np.sin(2*np.pi*t/13)
    # 三毛别段（21–41s）更低沉不安
    tension = ((t > 21) & (t < 41)).astype(float); tension = np.convolve(tension, np.ones(sr)/sr, "same")
    pad += tension*np.sin(2*np.pi*46*t)*0.5*(0.5+0.5*np.sin(2*np.pi*t*0.4))
    sig = 0.22*wind + 0.22*pad
    fade_ = np.minimum(1, np.minimum(t/2, (dur-t)/3)); sig *= fade_
    sig = (sig/np.abs(sig).max()*0.6*32767).astype("<i2")
    with wave.open(path, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(sig.tobytes())

if __name__ == "__main__":
    out = sys.argv[1]; wav = out.replace(".mp4", ".wav"); make_audio(wav, TOTAL)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                          "-c:a", "aac", "-b:a", "160k", "-shortest", out], stdin=subprocess.PIPE)
    for i in range(TOTAL*FPS): p.stdin.write(render_frame(i).tobytes())
    p.stdin.close(); p.wait(); print("done", out)
