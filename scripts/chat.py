#!/usr/bin/env python3
"""Act as the human teammate in the local Mattermost room (for headless demos/tests).

  chat.py say "@switchops-commander Checkout is failing..."
  chat.py tail [N]        print the last N posts (default 40)
  chat.py watch           follow new posts until Ctrl-C

Env: MATTERMOST_URL (http://localhost:8065), MATTERMOST_USER, MATTERMOST_USER_PASSWORD,
MATTERMOST_TEAM_NAME, SWITCHOPS_ROOM (default switchops-incidents).
"""
import json, os, sys, time, urllib.request

MM = os.environ.get("MATTERMOST_URL", "http://localhost:8065")
ROOM = os.environ.get("SWITCHOPS_ROOM", "switchops-incidents")


def req(method, path, token=None, body=None):
    r = urllib.request.Request(MM + "/api/v4" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None)
    if token:
        r.add_header("Authorization", "Bearer " + token)
    return urllib.request.urlopen(r, timeout=30)


def session():
    resp = req("POST", "/users/login", body={"login_id": os.environ["MATTERMOST_USER"],
                                             "password": os.environ["MATTERMOST_USER_PASSWORD"]})
    token = resp.headers["Token"]
    team = json.load(req("GET", "/teams/name/" + os.environ["MATTERMOST_TEAM_NAME"], token))["id"]
    chan = json.load(req("GET", f"/teams/{team}/channels/name/{ROOM}", token))["id"]
    return token, chan


def names(token, ids, cache={}):
    for i in ids:
        if i not in cache:
            cache[i] = json.load(req("GET", "/users/" + i, token))["username"]
    return cache


def posts(token, chan, since=0):
    d = json.load(req("GET", f"/channels/{chan}/posts?since={since}" if since else f"/channels/{chan}/posts?per_page=200", token))
    out = [d["posts"][i] for i in d["order"]]
    out.sort(key=lambda p: p["create_at"])
    return out


def show(token, ps):
    names(token, {p["user_id"] for p in ps})
    for p in ps:
        who = names(token, [p["user_id"]])[p["user_id"]]
        print(f"[{time.strftime('%H:%M:%S', time.localtime(p['create_at']/1000))}] {who}: {p['message']}\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tail"
    token, chan = session()
    if cmd == "say":
        req("POST", "/posts", token, {"channel_id": chan, "message": sys.argv[2]})
    elif cmd == "tail":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
        show(token, posts(token, chan)[-n:])
    elif cmd == "watch":
        last = int(time.time() * 1000)
        while True:
            ps = [p for p in posts(token, chan, last) if p["create_at"] > last]
            if ps:
                show(token, ps); last = max(p["create_at"] for p in ps)
            time.sleep(3)


if __name__ == "__main__":
    main()
