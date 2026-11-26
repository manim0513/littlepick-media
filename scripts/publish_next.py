#!/usr/bin/env python3
"""queue/ 에서 가장 앞선 게시물 하나를 Threads에 게시하고 posts/ 로 옮김.
대기열 파일: queue/<순번>-<slug>.json  {"text","video_url"|"image_url","reply"}
게시 전 video_url 이 열리는지 확인. 결과는 posts/<날짜>-<slug>/ 에 기록.
"""
import datetime, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import threads_post as tp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
q = sorted(f for f in os.listdir(f"{ROOT}/queue") if f.endswith(".json"))
if not q:
    print(json.dumps({"status": "queue_empty"})); sys.exit(0)
f = q[0]; path = f"{ROOT}/queue/{f}"
p = json.load(open(path))
res = tp.run(p)
kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
slug = f.split("-", 1)[1].rsplit(".", 1)[0]
d = f"{ROOT}/posts/{kst:%Y-%m-%d}-{slug}"; os.makedirs(d, exist_ok=True)
shutil.move(path, f"{d}/post.json")
res["published_at_kst"] = f"{kst:%Y-%m-%d %H:%M}"
json.dump(res, open(f"{d}/result.json", "w"), ensure_ascii=False, indent=1)
res["remaining"] = len(q) - 1
print(json.dumps(res, ensure_ascii=False))
