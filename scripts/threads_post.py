#!/usr/bin/env python3
"""Threads 게시: 본문(+영상/이미지) 게시 후 본인 답글로 링크 게시.
토큰은 클라우드 환경의 네트워크 시크릿이 graph.threads.net 요청에 자동으로 붙임(코드에 토큰 없음).
사용: threads_post.py post.json
post.json: {"text": "...", "video_url": "https://..." | "image_url": "https://...", "reply": "..."}
"""
import json, subprocess, sys, time

API = "https://graph.threads.net/v1.0"

def call(method, path, **params):
    cmd = ["curl", "-s", "-X", method, f"{API}/{path}"]
    if method == "GET":
        cmd[3:3] = ["-G"]
    for k, v in params.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    r = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    return r

def wait_ready(cid, timeout=300):
    end = time.time() + timeout
    while time.time() < end:
        s = call("GET", cid, fields="status,error_message")
        if s.get("status") == "FINISHED":
            return
        if s.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {cid}: {s}")
        time.sleep(5)
    raise TimeoutError(cid)

def publish(params):
    cid = call("POST", "me/threads", **params)["id"]
    wait_ready(cid)
    return call("POST", "me/threads_publish", creation_id=cid)["id"]

def main(path):
    p = json.load(open(path))
    main_params = {"text": p["text"]}
    if p.get("video_url"):
        main_params.update(media_type="VIDEO", video_url=p["video_url"])
    elif p.get("image_url"):
        main_params.update(media_type="IMAGE", image_url=p["image_url"])
    else:
        main_params.update(media_type="TEXT")
    post_id = publish(main_params)
    reply_id = None
    if p.get("reply"):
        time.sleep(10)
        reply_id = publish({"media_type": "TEXT", "text": p["reply"], "reply_to_id": post_id})
    link = call("GET", post_id, fields="permalink").get("permalink")
    print(json.dumps({"post_id": post_id, "reply_id": reply_id, "permalink": link}, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1])
