#!/usr/bin/env python3
"""Connect Telegram or Discord to Switch, then put the SwitchOps agents in a room there.

Standard library only; talks to the same gateway API as provision.py. Bot tokens are read
from environment variables only and are never printed, logged or stored in this repo.

  TELEGRAM_BOT_TOKEN=... TELEGRAM_BOT_USERNAME=... add_bridge.py connect telegram
  DISCORD_BOT_TOKEN=...  DISCORD_GUILD_ID=...       add_bridge.py connect discord
  add_bridge.py adopt Telegram "<room name>"   # agents, roles and instructions into that one room
  add_bridge.py link Telegram <your_username>   # claim your chat account (owner-only agents)

Telegram cannot create chats: add the bot to a group first and Switch creates the room, then
run `adopt`. On Discord, post a message in the channel first (that creates the room), then adopt.
See docs/official/deploy/messaging-apps/{telegram,discord}.md in the Switch repository.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provision as P  # noqa: E402  (same API helper, agent definitions and role texts)

SECRET_ENV = ("TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN")


def scrub(text):
    for k in SECRET_ENV:
        v = os.environ.get(k)
        if v:
            text = text.replace(v, "<redacted>")
    return text


def api(method, path, body=None):
    try:
        return P.call(method, path, body)
    except SystemExit as e:  # P.call exits with the server's message; never echo a token
        sys.exit(scrub(str(e)))


def login():
    email, password = os.environ.get("GATEWAY_ADMIN_EMAIL"), os.environ.get("GATEWAY_ADMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set GATEWAY_ADMIN_EMAIL and GATEWAY_ADMIN_PASSWORD (see .env of the Switch checkout).")
    api("POST", "/gateway/auth/login", {"email": email, "password": password})


def need(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit("Missing environment variable(s): " + ", ".join(missing))
    return [os.environ[n] for n in names]


def bridges():
    r = api("GET", "/gateway/collaborations")
    return r if isinstance(r, list) else r.get("bridges", r.get("collaborations", []))


def find_bridge(name):
    hit = [b for b in bridges() if name.lower() in (b.get("display_name", "") + " " + b.get("bridge_type", "")).lower()]
    if not hit:
        sys.exit(f"No connected messaging app matches {name!r}. Run `connect` first.")
    return hit[0]


def connect(platform):
    if platform == "telegram":
        token, username = need("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME")
        body = {"bridge_type": "telegram", "display_name": "Telegram",
                "connection_config": {"bot_token": token, "bot_username": username.lstrip("@")},
                "channel_creation_enabled": False}  # Telegram bots cannot create chats
    elif platform == "discord":
        token, guild = need("DISCORD_BOT_TOKEN", "DISCORD_GUILD_ID")
        body = {"bridge_type": "discord", "display_name": "Discord",
                "connection_config": {"bot_token": token, "guild_id": guild}}
    else:
        sys.exit("platform must be telegram or discord")
    r = api("POST", "/gateway/collaborations", body)
    print(f"connected {platform}: bridge id {r.get('id') or r.get('bridge_id')}")


def adopt(bridge_name, room_name=None):
    b = find_bridge(bridge_name)
    bid = b.get("id") or b.get("bridge_id")
    rooms = api("GET", "/gateway/rooms")
    rooms = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
    rooms = [r for r in rooms if r.get("bridge_id") == bid and not r.get("archived")]
    if not rooms:
        sys.exit("No room on that app yet. Telegram: add the bot to a group. Discord: post a message in a channel.")
    if not room_name:  # never touch rooms the user did not name
        sys.exit("Name the room to adopt. Rooms on that app: " + ", ".join(r.get("name", "?") for r in rooms))
    rooms = [r for r in rooms if r.get("name") == room_name]
    if not rooms:
        sys.exit(f"No room named {room_name!r} on that app.")
    ids = {a["name"]: a["agent_id"] for a in api("GET", "/gateway/management/agents")}
    missing = [n for n in P.AGENTS if n not in ids]
    if missing:
        sys.exit(f"Agents not provisioned yet ({', '.join(missing)}). Run scripts/up.sh first.")
    instructions = (P.HERE / "room-instructions.md").read_text()
    for room in rooms:
        rid = room["id"]
        api("POST", f"/gateway/rooms/{rid}/agents", {"agent_ids": [ids[n] for n in P.AGENTS]})
        api("PATCH", f"/gateway/rooms/{rid}", {"instructions": instructions})
        have = {r["name"] for r in api("GET", f"/gateway/rooms/{rid}/roles")}
        for name, (_p, _w, role, summary) in P.AGENTS.items():
            if role not in have:
                api("POST", f"/gateway/rooms/{rid}/roles", {
                    "name": role, "exclusive": True,
                    "instructions": f"You are the {role} for SwitchOps. {summary} Follow your agent instructions."})
        print(f"adopted room {room.get('name')} ({rid}): 3 agents, instructions, roles")


def link(bridge_name, username):
    b = find_bridge(bridge_name)
    bid = b.get("id") or b.get("bridge_id")
    users = api("GET", f"/gateway/collaborations/{bid}/directory?query={username.lstrip('@')}").get("users", [])
    if not users:
        sys.exit("Switch has not seen that account yet. Post a message in the chat first (tag the bot if needed).")
    u = users[0]
    r = api("POST", f"/gateway/collaborations/{bid}/identities",
            {"external_user_id": u["external_user_id"], "username": u.get("username", username), "expects_confirmation": True})
    print("claimed. Next, confirm it from your chat account:")
    print(json.dumps(r, indent=2)[:600])


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("connect", "adopt", "link"):
        sys.exit(__doc__)
    login()
    {"connect": lambda: connect(a[1].lower()), "adopt": lambda: adopt(a[1], a[2] if len(a) > 2 else None), "link": lambda: link(a[1], a[2])}[a[0]]()
