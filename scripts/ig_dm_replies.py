#!/usr/bin/env python3
"""인스타 댓글 → 쿠팡 링크 DM 자동 발송 (Private Replies).

ig/posts/*/post.json 의 coupang_link 와 result.json 의 media_id 를 보고
최근 7일 안에 달린 댓글(하트·이모지 등 아무 댓글)의 작성자에게 DM 1회를 보냄.
같은 사람이 같은 게시물에 여러 번 댓글을 달아도 DM은 1번만 보냄.
post.json 에 dm_keyword 가 있으면 그 단어가 들어간 댓글에만 보냄(선택).
보낸 댓글은 ig/dm_state.json 에 기록해 중복 발송을 막음.
인스타 규칙: 댓글 1개당 DM 1회, 댓글 작성 후 7일 이내만 가능.
토큰은 네트워크 시크릿이 graph.instagram.com 요청에 자동으로 붙임(코드에 토큰 없음).
사용: ig_dm_replies.py [--dry-run]
"""
import datetime, glob, json, os, subprocess, sys

API = "https://graph.instagram.com/v23.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = f"{ROOT}/ig/dm_state.json"
WINDOW = datetime.timedelta(days=7)
DRY = "--dry-run" in sys.argv

MSG = ("댓글 고마워! 링크 여기 있어 👇\n{link}\n\n"
       "(쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받아)")


def curl(args):
    out = subprocess.run(["curl", "-s"] + args, capture_output=True, text=True, check=True).stdout
    r = json.loads(out)
    if "error" in r:
        raise RuntimeError(r["error"].get("message"))
    return r


def get(path, **params):
    a = ["-G", f"{API}/{path}"]
    for k, v in params.items():
        a += ["--data-urlencode", f"{k}={v}"]
    return curl(a)


def get_all(path, **params):
    r = get(path, **params)
    items = r.get("data", [])
    while r.get("paging", {}).get("next"):
        r = curl([r["paging"]["next"]])
        items += r.get("data", [])
    return items


def ts(s):  # 2026-11-27T08:00:00+0000
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")


def norm(s):
    return "".join(s.split()).lower()


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"replied": {}}
    me = get("me", fields="user_id,username")
    uid, myname = me["user_id"], me.get("username")

    sent, skipped, errors = [], 0, []
    done_users = {(v.get("media"), v.get("user")) for v in state["replied"].values()}
    for d in sorted(glob.glob(f"{ROOT}/ig/posts/*/")):
        try:
            post = json.load(open(f"{d}post.json"))
            res = json.load(open(f"{d}result.json"))
        except FileNotFoundError:
            continue
        kw, link, mid = post.get("dm_keyword"), post.get("coupang_link"), res.get("media_id")
        if not (link and mid):
            continue
        comments = get_all(f"{mid}/comments", fields="id,text,timestamp,from,username", limit=50)
        for c in comments:
            cid = c["id"]
            who = (c.get("from") or {}).get("username") or c.get("username")
            if cid in state["replied"] or who == myname:
                continue
            if (mid, who) in done_users:
                continue
            if now - ts(c["timestamp"]) > WINDOW:
                continue
            if kw and norm(kw) not in norm(c.get("text", "")):
                skipped += 1
                continue
            body = {"recipient": {"comment_id": cid}, "message": {"text": MSG.format(link=link)}}
            if DRY:
                sent.append({"comment": cid, "user": who, "dry_run": True}); continue
            try:
                r = curl(["-XPOST", f"{API}/{uid}/messages", "-H", "Content-Type: application/json",
                          "-d", json.dumps(body, ensure_ascii=False)])
                state["replied"][cid] = {"user": who, "media": mid, "at": now.isoformat(timespec="seconds"),
                                         "message_id": r.get("message_id")}
                sent.append({"comment": cid, "user": who})
                done_users.add((mid, who))
            except RuntimeError as e:
                errors.append({"comment": cid, "error": str(e)})
                if "permission" in str(e).lower():
                    break

    if not DRY:
        json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"sent": sent, "skipped": skipped, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
