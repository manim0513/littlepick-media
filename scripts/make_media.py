#!/usr/bin/env python3
"""리틀픽 v2 템플릿: 같은 spec 으로 세로 영상(1080x1920) 또는 캐러셀 이미지(1080x1350)를 만든다.

사용:
  make_media.py video    spec.json out.mp4
  make_media.py carousel spec.json out_dir/      -> out_dir/1.jpg, 2.jpg ...

spec.json:
{
  "hook": "첫 화면 큰 문구\n두 줄까지",      # 첫 장(커버)
  "hook_image": "path",                       # 생략하면 첫 슬라이드 이미지
  "slides": [{"image": "path", "caption": "한 줄 설명", "hl": "강조할 부분"}],
  "hl": "hook 에서 강조할 부분",
  "cta": "링크는 댓글에"                       # 마지막 장 (생략 가능)
}
스타일: 밝은 배경 + 굵은 검정 글씨 + 형광펜 강조, 상단 진행바(영상), 장수 표시(캐러셀),
하단 @littlepicks.life. 영상은 컷마다 글자가 톡 올라오고 사진이 천천히 확대됨.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

FONT = next(f for f in ["/usr/share/fonts/truetype/nanum/NanumSquareRoundEB.ttf",
                        "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"] if os.path.exists(f))
FONT_R = "/usr/share/fonts/truetype/nanum/NanumSquareRoundR.ttf"
BG, INK, MARK, SUB = (255, 255, 255), (25, 25, 25), (255, 226, 77), (150, 145, 140)
HANDLE = "@littlepicks.life"
FPS = 30


def font(size, regular=False):
    return ImageFont.truetype(FONT_R if regular else FONT, size)


def trim(im, thr=242):
    """사진 가장자리의 흰 여백을 잘라냄."""
    g = im.convert("L").point(lambda v: 255 if v < thr else 0)
    b = g.getbbox()
    return im.crop(b) if b else im


def fit(im, w, h, zoom=1.0):
    """여백 제거 후, 비율이 비슷하면 꽉 채우고 아니면 흰 배경에 여유 있게 담음."""
    im = trim(im); r = (im.width / im.height) / (w / h)
    if 0.6 <= r <= 1.8:
        return cover(im, w, h, zoom)
    s = min((w - 80) / im.width, (h - 80) / im.height) * zoom
    r = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    out = Image.new("RGB", (w, h), (255, 255, 255)); out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return out


def cover(im, w, h, zoom=1.0):
    """im 을 w x h 에 꽉 채우도록 가운데 크롭(+확대)."""
    s = max(w / im.width, h / im.height) * zoom
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def draw_lines(d, lines, hl, y, size, W, maxw):
    f = font(size)
    while max(d.textlength(l, font=f) for l in lines) > maxw and size > 40:
        size -= 4; f = font(size)
    lh = int(size * 1.32)
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=f); x = (W - tw) / 2; ly = y + i * lh
        if hl and hl in line:
            a = x + d.textlength(line[:line.index(hl)], font=f); b = a + d.textlength(hl, font=f)
            d.rectangle((a - 6, ly + size * 0.52, b + 6, ly + size * 1.08), fill=MARK)
        d.text((x, ly), line, font=f, fill=INK)
    return y + lh * len(lines)


class Card:
    """한 장: 사진 영역 + 글자 레이어. kind = video | carousel"""

    def __init__(self, kind, image, text, hl, big, idx, n):
        self.kind, self.idx, self.n = kind, idx, n
        self.W, self.H = (1080, 1920) if kind == "video" else (1080, 1350)
        self.box = (0, 700, 1080, 1780) if kind == "video" else (0, 430, 1080, 1350)
        self.src = Image.open(image).convert("RGB")
        self.text, self.hl, self.big = text, hl, big

    def text_layer(self):
        W, H = self.W, self.H
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        lines = self.text.split("\n")
        top, bottom = (200, 680) if self.kind == "video" else (70, 410)
        size = (104 if self.big else 80) if self.kind == "video" else (92 if self.big else 72)
        f = font(size); lh = int(size * 1.32)
        y = top + (bottom - top - lh * len(lines)) // 2
        draw_lines(d, lines, self.hl, y, size, W, W - 120)
        return layer

    def chrome_layer(self):
        W, H = self.W, self.H
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        if self.kind == "video":
            gap, x0, y0 = 10, 40, 70; seg = (W - 2 * x0 - gap * (self.n - 1)) / self.n
            for i in range(self.n):
                a = x0 + i * (seg + gap)
                d.rounded_rectangle((a, y0, a + seg, y0 + 8), radius=4,
                                    fill=INK if i <= self.idx else (215, 210, 205))
            f = font(34, True); tw = d.textlength(HANDLE, font=f)
            d.text(((W - tw) / 2, 1825), HANDLE, font=f, fill=SUB)
        else:
            f = font(34); s = f"{self.idx + 1}/{self.n}"; tw = d.textlength(s, font=f)
            d.rounded_rectangle((W - tw - 74, 1270, W - 30, 1326), radius=28, fill=(25, 25, 25, 170))
            d.text((W - tw - 52, 1279), s, font=f, fill=(255, 255, 255))
            if self.idx == 0:
                f = font(30, True); d.text((36, 1282), HANDLE, font=f, fill=(255, 255, 255),
                                           stroke_width=2, stroke_fill=(0, 0, 0))
        return layer

    def render(self, t=None, dur=1.0):
        """t=None 이면 정지 이미지(캐러셀), 아니면 영상의 t초 시점 프레임."""
        x0, y0, x1, y1 = self.box
        base = Image.new("RGB", (self.W, self.H), BG)
        zoom = 1.0 if t is None else 1.0 + 0.06 * (t / dur)
        base.paste(fit(self.src, x1 - x0, y1 - y0, zoom), (x0, y0))
        if not hasattr(self, "_txt"):
            self._txt, self._chrome = self.text_layer(), self.chrome_layer()
        base.paste(self._chrome, (0, 0), self._chrome)
        if t is None:
            base.paste(self._txt, (0, 0), self._txt)
        else:  # 글자 팝업: 0.22초 동안 아래에서 40px 올라오며 나타남
            p = min(1.0, t / 0.22); p = 1 - (1 - p) ** 3
            txt = self._txt.copy(); txt.putalpha(txt.getchannel("A").point(lambda a: int(a * p)))
            base.paste(txt, (0, int(40 * (1 - p))), txt)
        return base


def cards(spec, kind):
    s = spec["slides"]; items = [(spec.get("hook_image", s[0]["image"]), spec["hook"], spec.get("hl"), True)]
    items += [(x["image"], x["caption"], x.get("hl"), False) for x in s]
    if spec.get("cta"):
        items.append((spec.get("cta_image", s[0]["image"]), spec["cta"], spec.get("cta_hl"), True))
    return [Card(kind, im, tx, hl, big, i, len(items)) for i, (im, tx, hl, big) in enumerate(items)]


def video(spec, out):
    cs = cards(spec, "video")
    durs = [1.9] + [1.45] * (len(cs) - 2) + [1.6]
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", "1080x1920", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt",
                          "yuv420p", "-profile:v", "high", "-crf", "21", "-movflags", "+faststart", out],
                         stdin=subprocess.PIPE)
    for c, dur in zip(cs, durs):
        for k in range(round(dur * FPS)):
            p.stdin.write(c.render(k / FPS, dur).tobytes())
    p.stdin.close(); assert p.wait() == 0


def carousel(spec, out_dir):
    os.makedirs(out_dir, exist_ok=True); paths = []
    for i, c in enumerate(cards(spec, "carousel"), 1):
        path = os.path.join(out_dir, f"{i}.jpg"); c.render().save(path, quality=90); paths.append(path)
    print(json.dumps(paths))


if __name__ == "__main__":
    kind, spec_path, out = sys.argv[1:4]
    spec = json.load(open(spec_path))
    (video if kind == "video" else carousel)(spec, out)
