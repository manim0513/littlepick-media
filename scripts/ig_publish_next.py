#!/usr/bin/env python3
"""ig/queue/ 에서 가장 앞선 릴스 하나를 인스타에 게시하고 ig/posts/ 로 옮김.
대기열 파일: ig/queue/<순번>-<slug>.json  {"caption","video_url"}
"""
import datetime, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(__file__))
import ig_post

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QD = f"{ROOT}/ig/queue"
q = sorted(f for f in os.listdir(QD) if f.endswith(".json"))
if not q:
    print(json.dumps({"status": "queue_empty"})); sys.exit(0)
f = q[0]; path = f"{QD}/{f}"
res = ig_post.run(json.load(open(path)))
kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
slug = f.split("-", 1)[1].rsplit(".", 1)[0]
d = f"{ROOT}/ig/posts/{kst:%Y-%m-%d}-{slug}"; os.makedirs(d, exist_ok=True)
shutil.move(path, f"{d}/post.json")
res["published_at_kst"] = f"{kst:%Y-%m-%d %H:%M}"
json.dump(res, open(f"{d}/result.json", "w"), ensure_ascii=False, indent=1)
res["remaining"] = len(q) - 1
print(json.dumps(res, ensure_ascii=False))
