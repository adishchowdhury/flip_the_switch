#!/usr/bin/env bash
# Build the demo workspace SwitchOps agents work in.
#
#   $SWITCHOPS_HOME/origin.git                 bare repo = the "production remote".
#                                              Only scripts/approve.py (run by a human) writes to it.
#   $SWITCHOPS_HOME/engineer/checkout-service engineer's clone, remote REMOVED (cannot push)
#   $SWITCHOPS_HOME/qa/checkout-service        QA's clone, remote REMOVED
#   $SWITCHOPS_HOME/commander                  commander's directory (no code)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="${SWITCHOPS_HOME:-$HOME/switchops-workspace}"
SRC="$ROOT/demo/checkout-service"
V2="$ROOT/demo/_v2"

rm -rf "$HOME_DIR"
mkdir -p "$HOME_DIR/commander"
export GIT_AUTHOR_NAME="Checkout Team" GIT_AUTHOR_EMAIL="team@example.com"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

seed="$(mktemp -d)"
trap 'rm -rf "$seed"' EXIT
git -C "$seed" init -q -b main
cp -r "$SRC/checkout" "$SRC/tests" "$SRC/README.md" "$SRC/.gitignore" "$seed/"
find "$seed" -name __pycache__ -prune -exec rm -rf {} +
git -C "$seed" add -A && git -C "$seed" commit -q -m "Checkout handler and tests (payment provider API v1)"

cp "$V2/provider.py" "$seed/checkout/provider.py"
mkdir -p "$seed/docs" "$seed/logs"
cp "$SRC/docs/"* "$seed/docs/"
cp "$SRC/logs/"* "$seed/logs/"
git -C "$seed" add -A && git -C "$seed" commit -q -m "Upgrade payment provider client to API v2"

git clone -q --bare "$seed" "$HOME_DIR/origin.git"
for role in engineer qa; do
  mkdir -p "$HOME_DIR/$role"
  git clone -q "$HOME_DIR/origin.git" "$HOME_DIR/$role/checkout-service"
  git -C "$HOME_DIR/$role/checkout-service" remote remove origin   # no remote => nothing to push to
  git -C "$HOME_DIR/$role/checkout-service" config user.name  "switchops-$role"
  git -C "$HOME_DIR/$role/checkout-service" config user.email "switchops-$role@example.com"
done
echo "Workspace ready at $HOME_DIR"
