#!/usr/bin/env python3
"""상품 하나를 대기열 글로 만든다: 갤러리 이미지 다운로드 → 영상/캐러셀 생성 → queue/NN-<slug>.json.

사용: build_post.py product.json
product.json:
{
  "slug": "baby-sleep-vest", "format": "video" | "carousel",
  "link": "https://link.coupang.com/a/...",
  "gallery": ["image/retail/images/....jpg", ...],      # 쿠팡 썸네일 경로 (48x48ex 뒤쪽)
  "hook": "큰 문구\n두 줄", "hl": "강조", "hook_img": 1,
  "slides": [[2, "설명\n두 줄", "강조"], [5, "사이즈표", "저장", true], ...],   # [이미지번호, 문구, 강조, contain?]
  "cta": "링크는 댓글에", "cta_hl": "댓글", "cta_img": 3,
  "text": "본문 (반말, 기준 날짜 표기 금지)"
}
이미지 번호는 gallery 순서(1부터). 결과 미디어는 videos/<slug>.mp4 또는 images/<slug>/N.jpg.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://manim0513.github.io/littlepick-media/"
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로,\n이에 따른 일정액의 수수료를 제공받습니다.\n"


def main(path):
    p = json.load(open(path)); slug = p["slug"]
    assert "기준)" not in p["text"], "본문에 기준 날짜 표기 금지"
    src = os.path.join(ROOT, ".cache", slug); os.makedirs(src, exist_ok=True)
    for i, g in enumerate(p["gallery"], 1):
        out = f"{src}/{i}.img"
        if not os.path.exists(out):
            subprocess.run(["curl", "-sf", "-A", "Mozilla/5.0", "-o", out,
                            f"https://thumbnail.coupangcdn.com/thumbnails/remote/720x720ex/{g}"], check=True)
    img = lambda n: f"{src}/{n}.img"
    spec = {"hook": p["hook"], "hl": p.get("hl"), "hook_image": img(p.get("hook_img", 1)),
            "slides": [{"image": img(s[0]), "caption": s[1], "hl": s[2] if len(s) > 2 else None,
                        "contain": bool(s[3]) if len(s) > 3 else False} for s in p["slides"]],
            "cta": p.get("cta", "링크는 댓글에"), "cta_hl": p.get("cta_hl", "댓글"),
            "cta_image": img(p.get("cta_img", 1))}
    os.makedirs(f"{ROOT}/specs", exist_ok=True)
    json.dump(spec, open(f"{ROOT}/specs/{slug}.json", "w"), ensure_ascii=False, indent=1)
    mm = os.path.join(ROOT, "scripts", "make_media.py")
    post = {"text": p["text"], "reply": DISCLOSURE + p["link"]}
    if p["format"] == "video":
        subprocess.run([sys.executable, mm, "video", f"{ROOT}/specs/{slug}.json", f"{ROOT}/videos/{slug}.mp4"], check=True)
        post["video_url"] = f"{BASE}videos/{slug}.mp4"
    else:
        subprocess.run([sys.executable, mm, "carousel", f"{ROOT}/specs/{slug}.json", f"{ROOT}/images/{slug}"],
                       check=True, capture_output=True)
        n = len(spec["slides"]) + 2
        post["carousel"] = [f"{BASE}images/{slug}/{i}.jpg" for i in range(1, n + 1)]
    q = f"{ROOT}/queue"; os.makedirs(q, exist_ok=True)
    nums = [int(f.split("-")[0]) for f in os.listdir(q) if f[:2].isdigit()]
    # 번호는 기존 대기열·게시 기록과 겹치지 않게 증가
    hist = os.path.join(ROOT, "queue", ".last_number")
    last = max(nums + [int(open(hist).read()) if os.path.exists(hist) else 0])
    num = last + 1; open(hist, "w").write(str(num))
    out = f"{q}/{num:02d}-{slug}.json"
    json.dump(post, open(out, "w"), ensure_ascii=False, indent=1)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
