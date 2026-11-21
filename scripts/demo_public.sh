#!/usr/bin/env bash
# Public HOUSIA demo: a Cloudflare quick tunnel (no account) in front of the local app.
#
#   scripts/demo_public.sh              # tunnel + app + worker
#   scripts/demo_public.sh --no-worker  # tunnel + app only
#
# Needs: cloudflared on PATH, OWNER_PASSWORD set (environment or .env).
# Logs go to instance/demo-*.log. Ctrl-C stops everything.
set -euo pipefail

cd "$(dirname "$0")/.."

RUN_WORKER=1
for arg in "$@"; do
  case "$arg" in
    --no-worker) RUN_WORKER=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (use --no-worker or --help)" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

command -v cloudflared >/dev/null 2>&1 || die "cloudflared is not installed. Download
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  to ~/.local/bin/cloudflared, run chmod +x on it, and make sure ~/.local/bin is on PATH."
command -v uv >/dev/null 2>&1 || die "uv is not installed (see README.md)."

if [[ -n "${CHANNEL:-}" && "${CHANNEL}" != "mock" ]]; then
  die "CHANNEL=${CHANNEL} is not allowed. The public demo uses only the mock portal (unset CHANNEL)."
fi

# Resolve settings the way the app does (environment first, then .env). Prints only names and
# yes/no flags, never values of secrets.
settings="$(uv run --quiet python -c '
from housia import config
print(config.CHANNEL)
print(config.PORT)
print("yes" if config.OWNER_PASSWORD else "no")
print("yes" if config.SECRET_KEY and config.SECRET_KEY != "dev" else "no")
print("yes" if config.JUDGE_PASSWORD and config.JUDGE_PASSWORD != config.OWNER_PASSWORD else "no")
print("yes" if config.GUEST_LINK_CODE else "no")
')" || die "could not read the HOUSIA configuration (run: uv sync)."
{ read -r cfg_channel; read -r cfg_port; read -r has_password; read -r has_secret; read -r has_judge; read -r has_guest; } <<<"$settings"

[[ "$cfg_channel" == "mock" ]] \
  || die "CHANNEL=${cfg_channel} (from .env) is not allowed. The public demo uses only the mock portal:
  CHANNEL=mock scripts/demo_public.sh"
[[ "$has_password" == "yes" ]] || die "OWNER_PASSWORD is not set. Set it in .env or run:
  OWNER_PASSWORD='choose-a-long-password' scripts/demo_public.sh
The owner signs in with username 'owner' and that password."

export CHANNEL=mock
export PORT="$cfg_port"
export HOUSIA_DB="${HOUSIA_DB:-instance/demo.db}"
export PYTHONUNBUFFERED=1
if [[ "$has_secret" != "yes" ]]; then
  # A random key for this run only; owner sessions end when the script stops.
  SECRET_KEY="$(uv run --quiet python -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export SECRET_KEY
fi

mkdir -p instance
TUNNEL_LOG=instance/demo-cloudflared.log
APP_LOG=instance/demo-app.log
WORKER_LOG=instance/demo-worker.log

if (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
  die "port ${PORT} is already in use. Stop that process or set PORT=another-port."
fi

PIDS=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#PIDS[@]})); then
    echo "Stopping tunnel, app and worker..."
    for pid in "${PIDS[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
    for _ in $(seq 1 50); do
      alive=0
      for pid in "${PIDS[@]}"; do kill -0 -- "-$pid" 2>/dev/null && alive=1; done
      ((alive)) || break
      sleep 0.1
    done
    for pid in "${PIDS[@]}"; do kill -KILL -- "-$pid" 2>/dev/null || true; done
    echo "Stopped."
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Each child runs in its own process group (setsid), so cleanup stops it and all its children.
start() { # start LOGFILE COMMAND...
  local log="$1"; shift
  setsid "$@" >"$log" 2>&1 </dev/null &
  PIDS+=("$!")
}

# 1. Tunnel.
start "$TUNNEL_LOG" cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${PORT}"
tunnel_pid="${PIDS[-1]}"
PUBLIC_URL=""
for _ in $(seq 1 80); do
  PUBLIC_URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -n1 || true)"
  [[ -n "$PUBLIC_URL" ]] && break
  kill -0 "$tunnel_pid" 2>/dev/null || die "cloudflared stopped early. See ${TUNNEL_LOG}."
  sleep 0.5
done
[[ -n "$PUBLIC_URL" ]] || die "no trycloudflare.com address after 40 seconds. See ${TUNNEL_LOG}."

# 2. Database: seed a fresh one so the demo has data.
if [[ ! -f "$HOUSIA_DB" ]]; then
  uv run --quiet python -c 'from housia import db; db.reset_db()' >>"$APP_LOG" 2>&1 \
    || die "could not create the demo database. See ${APP_LOG}."
fi
# Guest demos start from a copy of the database as it is now.
if [[ "$has_guest" == "yes" ]]; then
  uv run --quiet python -m housia.sandbox make-template >>"$APP_LOG" 2>&1 \
    || die "could not build the guest demo template. See ${APP_LOG}."
fi

# 3. App, with request lines kept out of the log (applicant links are private bearer links).
export BASE_URL="$PUBLIC_URL"
start "$APP_LOG" uv run --quiet python -c '
import logging, runpy
logging.getLogger("werkzeug").setLevel(logging.WARNING)
runpy.run_path("run.py", run_name="__main__")
'
app_pid="${PIDS[-1]}"
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/static/favicon.svg" 2>/dev/null && break
  kill -0 "$app_pid" 2>/dev/null || die "the app stopped early. See ${APP_LOG}."
  sleep 0.5
done
curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/static/favicon.svg" 2>/dev/null \
  || die "the app did not start within 30 seconds. See ${APP_LOG}."

# 4. Worker.
if ((RUN_WORKER)); then
  start "$WORKER_LOG" uv run --quiet python -m housia.worker
fi

echo
echo "HOUSIA public demo is running."
echo "  Public address:   ${PUBLIC_URL}"
echo "  Applicant page:   ${PUBLIC_URL}/apply/1   (personal links: ${PUBLIC_URL}/a/<token>)"
echo "  Owner pages:      ${PUBLIC_URL}/guide   (sign in as 'owner' with OWNER_PASSWORD; the guide has the demo clock and reset)"
if [[ "$has_judge" == "yes" ]]; then
  echo "  Judge login:      available, read-only (sign in as 'judge' with JUDGE_PASSWORD)"
fi
if [[ "$has_guest" == "yes" ]]; then
  GUEST_CODE="$(uv run --quiet python -c 'from housia import config; print(config.GUEST_LINK_CODE)')"
  echo "  Guest link:       ${PUBLIC_URL}/guest/${GUEST_CODE}   (each visitor gets a private copy)"
fi
echo "  Database:         ${HOUSIA_DB}   Worker: $( ((RUN_WORKER)) && echo on || echo off )"
echo "  Logs:             instance/demo-*.log"
echo "Press Ctrl-C to stop the tunnel, the app and the worker."

# Exit (and clean up) when any process stops.
set +e
wait -n
echo "A process stopped; see instance/demo-*.log." >&2
exit 1
