#!/usr/bin/env python3
"""Create the SwitchOps agents and room on a running Switch server.

Uses only Switch's own gateway API (the same one the Console uses): managed
agents bound to an enrolled agent controller, plus one room with roles.
Standard library only. Idempotent: re-running updates agents, reuses the room.

Environment (defaults match scripts/up.sh):
  SWITCH_GATEWAY_URL      http://localhost:8000
  GATEWAY_ADMIN_EMAIL / GATEWAY_ADMIN_PASSWORD   gateway login
  SWITCHOPS_HOME          workspace from scripts/build_demo_workspace.sh
  SWITCHOPS_ROOM          room name (default: switchops-incidents)
  SWITCHOPS_MM_USER       chat user added to the room (default: user)
"""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("SWITCH_GATEWAY_URL", "http://localhost:8000").rstrip("/")
WORKSPACE = Path(os.environ.get("SWITCHOPS_HOME", Path.home() / "switchops-workspace"))
ROOM = os.environ.get("SWITCHOPS_ROOM", "switchops-incidents")
CHAT_USER = os.environ.get("SWITCHOPS_MM_USER", "user")

# agent name -> (prompt file, workdir, switch role, role summary)
AGENTS = {
    "switchops-commander": ("commander.md", "commander", "incident-commander",
                            "Incident commander: triage, delegation, ledger. Does not edit code."),
    "switchops-engineer": ("engineer.md", "engineer", "engineer",
                           "Investigates, reproduces and fixes on a branch. Cannot push."),
    "switchops-qa": ("qa.md", "qa", "qa-reviewer",
                     "Independent reviewer. Re-runs tests, may reject a fix."),
}

# Claude Code permission rules written into each agent's directory. These are
# enforced by Claude Code itself, in addition to the written rules.
CLAUDE_SETTINGS = {
    "permissions": {
        "deny": [
            "Bash(git push:*)", "Bash(git remote:*)", "Bash(gh:*)",
            "Bash(curl:*)", "Bash(wget:*)", "Bash(ssh:*)", "Bash(scp:*)",
            "Bash(printenv:*)", "Bash(env:*)",
            "Read(.switch/**)", "Read(**/.env*)", "Read(**/.switch/**)",
        ]
    }
}

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, ok=(200, 201)):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {detail}")


def main():
    email = os.environ.get("GATEWAY_ADMIN_EMAIL")
    password = os.environ.get("GATEWAY_ADMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set GATEWAY_ADMIN_EMAIL and GATEWAY_ADMIN_PASSWORD (see .env of the Switch checkout).")
    call("POST", "/gateway/auth/login", {"email": email, "password": password})

    controllers = [c for c in call("GET", "/gateway/management/controllers") if c.get("state") == "online"]
    if not controllers:
        sys.exit("No online agent controller. Run scripts/up.sh (it enrolls and starts one).")
    controller_id = controllers[0].get("controller_id") or controllers[0].get("id")

    common = (HERE / "prompts" / "common.md").read_text()
    existing = {a["name"]: a for a in call("GET", "/gateway/management/agents")}
    for name, (prompt, workdir, _role, summary) in AGENTS.items():
        directory = WORKSPACE / workdir
        directory.mkdir(parents=True, exist_ok=True)
        settings_dir = directory / ".claude"
        settings_dir.mkdir(exist_ok=True)
        (settings_dir / "settings.json").write_text(json.dumps(CLAUDE_SETTINGS, indent=2))
        definition = {
            "provider": "claude",
            "instructions": common + "\n\n" + (HERE / "prompts" / prompt).read_text(),
            "directory": str(directory),
        }
        if name in existing:
            call("PUT", f"/gateway/management/agents/{existing[name]['agent_id']}",
                 {"controller_id": controller_id, "desired_state": "running", "definition": definition})
            print(f"updated agent {name}")
        else:
            call("POST", "/gateway/management/agents",
                 {"name": name, "description": summary, "controller_id": controller_id,
                  "desired_state": "running", "definition": definition})
            print(f"created agent {name}")

    roles = [{"name": role, "instructions": f"You are the {role} for SwitchOps. {summary} Follow your agent instructions.",
              "exclusive": True} for _n, (_p, _w, role, summary) in AGENTS.items()]
    rooms = call("GET", "/gateway/rooms")
    rooms = rooms if isinstance(rooms, list) else rooms.get("rooms", [])
    match = [r for r in rooms if r["name"] == ROOM and not r.get("archived")]
    if match:
        print(f"room {ROOM} already exists: {match[0]['id']}")
        return
    room = call("POST", "/gateway/rooms", {
        "name": ROOM,
        "description": "SwitchOps: humans and AI agents take incidents from report to verified fix",
        "instructions": (HERE / "room-instructions.md").read_text(),
        "agent_names": list(AGENTS),
        "user_names": [CHAT_USER],
        "roles": roles,
    })
    print(f"created room {ROOM}: {room['id']}  ({room.get('external_channel_url')})")


if __name__ == "__main__":
    main()
