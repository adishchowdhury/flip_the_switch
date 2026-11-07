#!/usr/bin/env bash
# Bring up the whole SwitchOps stack from a clean machine. Safe to re-run.
#
# Needs: git, docker (running), uv, node 22+, pnpm, python3, and `claude` signed in.
# Starts: Postgres + Mattermost (docker), switch-core (from source), the Switch agent
# controller (headless, runs Claude Code agents), then provisions the SwitchOps agents/room.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SWITCH_DIR="${SWITCH_DIR:-$ROOT/../switch}"
DATA="${SWITCHOPS_DATA:-$HOME/.switchops}"
export SWITCHOPS_HOME="${SWITCHOPS_HOME:-$HOME/switchops-workspace}"
mkdir -p "$DATA"

# Skip developer-only tools (ruff, mypy): not needed to run Switch, and fewer downloads to corrupt.
export UV_NO_DEV=1

say() { printf '\n== %s\n' "$*"; }

for bin in git docker uv node pnpm python3 claude; do
  command -v "$bin" >/dev/null || { echo "missing prerequisite: $bin" >&2; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "docker daemon is not running" >&2; exit 1; }

say "Switch source"
[ -d "$SWITCH_DIR/.git" ] || git clone --depth 1 https://github.com/sandbox-quantum/switch "$SWITCH_DIR"
cd "$SWITCH_DIR"

say "Switch .env (secrets are generated locally, never committed)"
if [ ! -e .env ]; then
  cp .env.example .env
  deploy/local/generate-env-secrets.sh .env local >/dev/null
fi
setenv() { grep -q "^$1=" .env && sed -i.bak "s|^$1=.*|$1=$2|" .env && rm -f .env.bak || echo "$1=$2" >> .env; }
setenv FEATURE_FLAGS_ENABLED agent_management
grep -q '^CONTROLLER_TOKEN_SECRET=.' .env || setenv CONTROLLER_TOKEN_SECRET "$(openssl rand -hex 32)"
set -a; . ./.env; set +a

say "Postgres + Mattermost"
docker compose -f deploy/local/docker-compose.yml --project-directory . up -d postgres init-db mattermost
until curl -fsS localhost:8065/api/v4/system/ping >/dev/null 2>&1; do sleep 3; done

say "Database migrations"
uv sync --project core >/dev/null
uv run --project core alembic -c core/alembic.ini upgrade head >/dev/null

say "switch-core"
if ! curl -fsS localhost:8000/health >/dev/null 2>&1; then
  GATEWAY_PUBLIC_URL=http://localhost:8000 GATEWAY_COOKIE_SECURE=false \
    nohup uv run --project core python -m switch_core.main > "$DATA/switch-core.log" 2>&1 &
  until curl -fsS localhost:8000/health >/dev/null 2>&1; do sleep 2; done
fi

say "Mattermost team, bridge and account link (Switch's own setup script)"
SWITCH_URL=http://localhost:8000 MATTERMOST_URL=http://localhost:8065 \
MATTERMOST_URL_FOR_SWITCH=http://localhost:8065 MATTERMOST_CALLBACK_BASE_URL=http://localhost:8081 \
  core/.venv/bin/python deploy/shared_resources/setup.py | tail -3

say "Agent controller (runs the Claude Code agents)"
CTL=console/packages/agent-controller
if [ ! -f "$CTL/dist/cli.mjs" ]; then
  (cd console && pnpm install --ignore-scripts --filter '@switch-console/agent-controller...' >/dev/null \
    && pnpm --filter '@switch-console/agent-controller...' run build >/dev/null)
fi
CDIR="$DATA/controller"
if [ ! -d "$CDIR" ]; then
  jar="$(mktemp)"
  curl -fsS -c "$jar" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$GATEWAY_ADMIN_EMAIL\",\"password\":\"$GATEWAY_ADMIN_PASSWORD\"}" localhost:8000/gateway/auth/login >/dev/null
  code="$(curl -fsS -b "$jar" -X POST localhost:8000/gateway/management/enrollment-codes | python3 -c 'import sys,json;print(json.load(sys.stdin)["code"])')"
  node "$CTL/dist/cli.mjs" enroll --server http://localhost:8000 --code "$code" --name switchops-box \
    --data-dir "$CDIR" --secret-store file
fi
if ! pgrep -f "agent-controller/dist/cli.mjs run" >/dev/null; then
  nohup node "$CTL/dist/cli.mjs" run --data-dir "$CDIR" > "$DATA/controller.log" 2>&1 &
  sleep 5
fi

say "Demo workspace and SwitchOps agents + room"
[ -d "$SWITCHOPS_HOME/origin.git" ] && [ -z "${RESET_WORKSPACE:-}" ] || "$ROOT/scripts/build_demo_workspace.sh"
python3 "$ROOT/switchops/provision.py"

cat <<MSG

SwitchOps is up.
  Chat (Mattermost): http://localhost:8065  team 'switch', channel 'switchops-incidents'
                     login: $MATTERMOST_USER / (MATTERMOST_USER_PASSWORD in $SWITCH_DIR/.env)
  Switch gateway:    http://localhost:8000
  Try it headlessly: set -a; . $SWITCH_DIR/.env; set +a
                     $ROOT/scripts/chat.py say "@switchops-commander Checkout has been failing since this morning. Please investigate."
                     $ROOT/scripts/chat.py watch
MSG
