#!/usr/bin/env python3
"""인스타 릴스용 세로 영상(1080x1920, 30fps) + 자체 합성 배경음 생성. 무료 도구만(PIL, numpy, ffmpeg).

사용: make_reel.py spec.json out.mp4

spec.json:
{
  "bpm": 112,
  "shots": [
    {"image": "path", "beats": 2,              # 컷 길이(박자 수)
     "layout": "full" | "card",                # full=화면 꽉, card=흐린 배경 위 사진
     "focus": 0.5,                             # full 일 때 가로 기준점(0~1)
     "move": "in" | "out" | "left" | "right" | "punch",
     "text": "자막\n두 줄", "hl": "강조",     # 형광 강조
     "pos": "top" | "mid" | "low",
     "tag": "1",                               # 리스트 번호 배지(선택)
     "big": true, "dark": true,                # 큰 글씨 / 사진 어둡게
     "shake": true, "flash": true}             # 흔들림 / 흰 번쩍(컷 시작)
  ]
}
"""
import json, math, os, subprocess, sys, tempfile, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
for f in ["/usr/share/fonts/truetype/nanum/NanumSquareRoundEB.ttf", "/usr/share/fonts/truetype/nanum/NanumSquareEB.ttf",
          "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"]:
    if os.path.exists(f):
        FONT = f; break
INK, MARK, PAPER = (20, 20, 20), (255, 222, 60), (255, 255, 255)
SR = 44100


# ---------- 그림 ----------
def cover(im, w, h, focus=0.5):
    s = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x = int((r.width - w) * focus); y = (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def base_plate(shot):
    """움직임 전에 한 번 만드는 큰 배경(1.25배 여유)."""
    im = Image.open(shot["image"]).convert("RGB")
    BW, BH = int(W * 1.25), int(H * 1.25)
    if shot.get("layout", "full") == "full":
        plate = cover(im, BW, BH, shot.get("focus", 0.5))
    else:
        bg = cover(im, BW // 4, BH // 4).filter(ImageFilter.GaussianBlur(10)).resize((BW, BH), Image.BILINEAR)
        bg = ImageEnhance.Brightness(bg).enhance(0.55)
        fw = int(W * 0.92); fh = int(im.height * fw / im.width)
        fg = im.resize((fw, fh), Image.LANCZOS)
        m = Image.new("L", fg.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, fw, fh), radius=48, fill=255)
        bg.paste(fg, ((BW - fw) // 2, int(BH / 2 + H * 0.07 - fh / 2)), m)
        plate = bg
    if shot.get("dark"):
        plate = ImageEnhance.Brightness(plate).enhance(0.6)
    return plate


def camera(plate, shot, p, t):
    """p: 0~1 진행도. 확대/이동/펀치/흔들림 적용 후 1080x1920 으로 잘라냄."""
    BW, BH = plate.size
    mv = shot.get("move", "in")
    z = 1.0; ox = 0.0
    if mv == "in": z = 1.0 + 0.10 * p
    elif mv == "out": z = 1.10 - 0.10 * p
    elif mv == "left": z = 1.06; ox = 0.05 * (0.5 - p)
    elif mv == "right": z = 1.06; ox = -0.05 * (0.5 - p)
    elif mv == "punch":  # 처음 0.15초 크게 들어왔다가 안착
        k = min(1, t / 0.18); z = 1.18 - 0.12 * (1 - (1 - k) ** 3) + 0.03 * p
    cw = W * (BW / (W * 1.25)) / z; ch = H * (BH / (H * 1.25)) / z
    cx = BW / 2 + ox * BW; cy = BH / 2
    if shot.get("shake") and t < 0.35:
        a = (0.35 - t) / 0.35 * 18
        cx += a * math.sin(t * 90); cy += a * math.cos(t * 70)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return plate.resize((W, H), Image.BILINEAR, box=box)


def font(size):
    return ImageFont.truetype(FONT, size)


def text_layer(shot):
    """틱톡식 흰 박스 자막(줄마다) + 형광 강조 + 번호 배지."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    txt = shot.get("text")
    if txt:
        lines = txt.split("\n"); size = 100 if shot.get("big") else 84
        f = font(size)
        while max(d.textlength(l, font=f) for l in lines) > W - 200:
            size -= 4; f = font(size)
        lh = int(size * 1.45)
        total = lh * len(lines)
        y0 = {"top": 330, "mid": (H - total) // 2 - 60, "low": 1180}[shot.get("pos", "top")]
        hl = shot.get("hl")
        for i, line in enumerate(lines):
            tw = d.textlength(line, font=f); x = (W - tw) / 2; y = y0 + i * lh
            d.rounded_rectangle((x - 30, y - 18, x + tw + 30, y + size + 20), radius=22, fill=PAPER + (255,))
        for i, line in enumerate(lines):
            tw = d.textlength(line, font=f); x = (W - tw) / 2; y = y0 + i * lh
            if hl and hl in line:
                a = x + d.textlength(line[:line.index(hl)], font=f); b = a + d.textlength(hl, font=f)
                d.rectangle((a - 4, y + size * 0.45, b + 4, y + size * 1.05), fill=MARK + (255,))
            d.text((x, y), line, font=f, fill=INK + (255,))
    if shot.get("tag"):
        f = font(120); s = shot["tag"]; tw = d.textlength(s, font=f)
        cx, cy, r = 150, 230, 95
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MARK + (255,))
        d.text((cx - tw / 2, cy - 68), s, font=f, fill=INK + (255,))
    return layer


def pop(layer, t):
    """0.2초 동안 0.6→1.06→1.0 크기로 튀어나옴."""
    if t >= 0.22:
        return layer, (0, 0)
    k = max(0.0, t / 0.22)
    s = 0.6 + 0.46 * math.sin(k * math.pi / 2) ** 0.8 if k < 0.75 else 1.06 - 0.06 * (k - 0.75) / 0.25
    bbox = layer.getbbox()
    if not bbox:
        return layer, (0, 0)
    part = layer.crop(bbox); cw, ch = part.size
    part = part.resize((max(1, int(cw * s)), max(1, int(ch * s))), Image.BILINEAR)
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    a = min(1.0, t / 0.08)
    if a < 1:
        part.putalpha(part.getchannel("A").point(lambda v: int(v * a)))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(part, (int(cx - part.width / 2), int(cy - part.height / 2)), part)
    return out, (0, 0)


# ---------- 소리(직접 합성, 저작권 없음) ----------
def env(n, a=0.005, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def synth(total, bpm, cuts, pops):
    n = int(total * SR) + SR; out = np.zeros(n)
    beat = 60 / bpm
    def add(sig, at, g=1.0):
        i = int(at * SR); j = min(n, i + len(sig)); out[i:j] += g * sig[:j - i]
    t = np.arange(int(0.35 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 9)
    hat = np.random.default_rng(1).standard_normal(int(0.05 * SR)) * env(int(0.05 * SR), 0.001, 0.012)
    hat = np.diff(hat, prepend=0)
    clap_n = int(0.18 * SR)
    clap = np.random.default_rng(2).standard_normal(clap_n) * env(clap_n, 0.001, 0.05)
    clap = np.convolve(clap, np.ones(6) / 6, "same")
    # 코드 진행 (밝은 팝): F - G - Em - Am
    chords = [[65, 69, 72], [67, 71, 74], [64, 67, 71], [69, 72, 76]]
    bass = [41, 43, 40, 45]
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    def pluck(fr, dur, d=0.25):
        tt = np.arange(int(dur * SR)) / SR
        s = np.sin(2 * np.pi * fr * tt) + 0.35 * np.sin(4 * np.pi * fr * tt) + 0.12 * np.sin(6 * np.pi * fr * tt)
        return s * env(len(tt), 0.004, d)
    nb = int(total / beat) + 2
    for b in range(nb):
        at = b * beat; bar = (b // 4) % 4
        add(kick, at, 0.9 if b % 2 == 0 else 0.5)
        if b % 4 in (1, 3): add(clap, at, 0.35)
        add(hat, at + beat / 2, 0.22); add(hat, at, 0.12)
        if b % 2 == 0:
            for m in chords[bar]: add(pluck(midi(m), beat * 1.6, 0.3), at, 0.11)
        add(pluck(midi(bass[bar]), beat * 0.9, 0.2), at, 0.32)
        # 위쪽 아르페지오
        for k in range(2):
            m = chords[bar][(b * 2 + k) % 3] + 12
            add(pluck(midi(m), beat * 0.5, 0.08), at + k * beat / 2, 0.06)
    # 컷 전환 '휙' 소리, 자막 '톡' 소리
    for c in cuts:
        m = int(0.22 * SR); nz = np.random.default_rng(int(c * 100)).standard_normal(m)
        sw = np.convolve(nz, np.ones(12) / 12, "same") * np.sin(np.linspace(0, np.pi, m)) ** 2
        add(sw, max(0, c - 0.16), 0.5)
    for p in pops:
        tt = np.arange(int(0.08 * SR)) / SR
        add(np.sin(2 * np.pi * (900 + 600 * tt / 0.08) * tt) * env(len(tt), 0.002, 0.025), p, 0.35)
    out = out[:int(total * SR)]
    fade = int(0.5 * SR); out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.abs(out).max() + 1e-9) * 0.8
    return (out * 32767).astype(np.int16)


def main(spec_path, out):
    spec = json.load(open(spec_path)); bpm = spec.get("bpm", 112); beat = 60 / bpm
    shots = spec["shots"]
    durs = [s.get("beats", 2) * beat for s in shots]
    total = sum(durs)
    tmp = tempfile.mkdtemp(); vtmp = f"{tmp}/v.mp4"; atmp = f"{tmp}/a.wav"
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "20", "-preset", "medium", vtmp], stdin=subprocess.PIPE)
    frame_no = 0; start = 0.0; cuts, pops = [], []
    for s, dur in zip(shots, durs):
        plate = base_plate(s); txt = text_layer(s)
        if start > 0: cuts.append(start)
        if s.get("text") or s.get("tag"): pops.append(start + 0.02)
        end_frame = round((start + dur) * FPS)
        while frame_no < end_frame:
            t = max(0.0, frame_no / FPS - start); pr = t / dur
            fr = camera(plate, s, pr, t).convert("RGBA")
            lay, _ = pop(txt, t); fr.alpha_composite(lay)
            fr = fr.convert("RGB")
            if s.get("flash") and t < 0.12:
                fr = Image.blend(fr, Image.new("RGB", (W, H), (255, 255, 255)), 0.7 * (1 - t / 0.12))
            p.stdin.write(fr.tobytes()); frame_no += 1
        start += dur
    p.stdin.close(); p.wait()
    with wave.open(atmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(synth(total, bpm, cuts, pops).tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", vtmp, "-i", atmp, "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], check=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
