#!/usr/bin/env python3
"""상품 사진 + 자막으로 세로 슬라이드 영상(1080x1920) 생성.
사용: make_video.py spec.json out.mp4
spec.json: {"slides":[{"image":"path","caption":"텍스트"}, ...], "sec":2.4}
"""
import json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FONT = next(f for f in ["/usr/share/fonts/truetype/nanum/NanumSquareRoundEB.ttf",
                        "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"] if os.path.exists(f))

def frame(img_path, caption, out):
    im = Image.open(img_path).convert("RGB")
    bg = im.resize((H, H)).crop(((H - W) // 2, 0, (H - W) // 2 + W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (255, 250, 245)), 0.45)
    bg.paste(im.resize((1000, 1000)), (40, 520))
    d = ImageDraw.Draw(bg)
    size = 68
    f = ImageFont.truetype(FONT, size)
    while d.textlength(caption, font=f) > W - 160:
        size -= 4; f = ImageFont.truetype(FONT, size)
    tw = d.textlength(caption, font=f); x = (W - tw) / 2; y = 300
    d.rounded_rectangle((x - 40, y - 30, x + tw + 40, y + size + 32), radius=40, fill=(255, 255, 255))
    d.text((x, y), caption, font=f, fill=(60, 45, 40))
    bg.save(out)

def main(spec_path, out):
    spec = json.load(open(spec_path))
    slides, d, t = spec["slides"], spec.get("sec", 2.4), 0.4
    tmp = tempfile.mkdtemp()
    args, fc = [], ""
    for i, s in enumerate(slides):
        p = f"{tmp}/f{i}.png"; frame(s["image"], s["caption"], p)
        args += ["-framerate", "30", "-loop", "1", "-t", str(d), "-i", p]
        fc += (f"[{i}:v]scale=1188:2112,zoompan=z='min(zoom+0.0012,1.08)':d=1:"
               f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,setsar=1[v{i}];")
    prev = "v0"
    for i in range(1, len(slides)):
        fc += f"[{prev}][v{i}]xfade=transition=fade:duration={t}:offset={round(i*(d-t),2)}[x{i}];"
        prev = f"x{i}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args, "-filter_complex", fc.rstrip(";"),
                    "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-r", "30", "-movflags", "+faststart", out], check=True)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
