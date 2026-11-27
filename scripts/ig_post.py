#!/usr/bin/env python3
"""인스타그램 릴스 게시 (Instagram API, 통합 로그인 토큰 EAA… → graph.facebook.com).
토큰은 클라우드 환경의 네트워크 시크릿이 graph.facebook.com 요청에 자동으로 붙임(코드에 토큰 없음).
사용: ig_post.py post.json
post.json: {"caption": "...", "video_url": "https://...mp4", "cover_url": "https://...jpg"(선택), "share_to_feed": true}
"""
import json, subprocess, sys, time

API = "https://graph.facebook.com/v23.0"
IG_ID = "17841415991773293"  # @littlepicks.life 인스타 계정 ID (앱 대시보드 > 액세스 토큰 생성)


def call(method, path, **params):
    cmd = ["curl", "-s", "-G" if method == "GET" else "-XPOST", f"{API}/{path}"]
    for k, v in params.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    r = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    return r


def wait_ready(cid, timeout=600):
    end = time.time() + timeout
    while time.time() < end:
        s = call("GET", cid, fields="status_code,status")
        if s.get("status_code") == "FINISHED":
            return
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {cid}: {s}")
        time.sleep(10)
    raise TimeoutError(cid)


def run(p):
    uid = IG_ID
    params = {"media_type": "REELS", "video_url": p["video_url"], "caption": p["caption"],
              "share_to_feed": "true" if p.get("share_to_feed", True) else "false"}
    if p.get("cover_url"):
        params["cover_url"] = p["cover_url"]
    cid = call("POST", f"{uid}/media", **params)["id"]
    wait_ready(cid)
    mid = call("POST", f"{uid}/media_publish", creation_id=cid)["id"]
    link = call("GET", mid, fields="permalink").get("permalink")
    return {"media_id": mid, "permalink": link}


if __name__ == "__main__":
    print(json.dumps(run(json.load(open(sys.argv[1]))), ensure_ascii=False))
