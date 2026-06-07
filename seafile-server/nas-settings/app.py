#!/usr/bin/env python3
"""
nas-settings/app.py

Flask web app for managing NAS sync configuration (SEAF_INGEST_DAYS)
per Seafile library. Runs behind Caddy at /nas-settings/.

Auth: delegates to Seafile admin session. Any request that carries a valid
Seafile sessionid cookie belonging to a system admin is allowed in. No
separate login required — the user's existing Seafile session is reused.

Env vars:
  SEAFILE_INTERNAL_URL  Base URL for Seafile's internal API (default: http://seafile:8000)
  SEAFILE_PUBLIC_HOST   Public hostname used in the Cookie/Host header (default: seafile.designflow.app)
  SECRET_KEY            Required. Random string for Flask session signing.

State is persisted to /data/settings.json.
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LIBRARIES = [
    {
        "id": "seaf-cli-char-licensed",
        "name": "Character Licensed",
        "uuid": "177cf9de-3066-482e-956a-7ae8d8786c6d",
    },
    {
        "id": "seaf-cli-generic-decor",
        "name": "Generic Decor",
        "uuid": "1b116ab7-d66b-4411-a691-21f34eadb731",
    },
]

SETTINGS_PATH = Path("/data/settings.json")
STATUS_PATH = Path("/data/status.json")
COMMANDS_PATH = Path("/data/commands.json")
DEFAULT_INGEST_DAYS = 730
STATUS_STALE_SECONDS = 120  # containers reporting older than this are shown as offline

PRESET_OPTIONS = [
    ("", "All files (no limit)"),
    ("180", "Last 6 months (180 days)"),
    ("365", "Last 1 year (365 days)"),
    ("730", "Last 2 years (730 days)"),
    ("1095", "Last 3 years (1095 days)"),
    ("1825", "Last 5 years (1825 days)"),
    ("custom", "Custom…"),
]

PRESET_VALUES = {opt[0] for opt in PRESET_OPTIONS if opt[0] not in ("", "custom")}

# ---------------------------------------------------------------------------
# WSGI prefix middleware (strips /nas-settings so url_for works correctly)
# ---------------------------------------------------------------------------


class PrefixMiddleware:
    def __init__(self, app, prefix=""):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = self.prefix
        return self.app(environ, start_response)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY env var is required")

_SEAFILE_INTERNAL = os.environ.get("SEAFILE_INTERNAL_URL", "http://seafile:8000").rstrip("/")
_SEAFILE_PUBLIC_HOST = os.environ.get("SEAFILE_PUBLIC_HOST", "seafile.designflow.app")
_SEAFILE_ADMIN_API = f"{_SEAFILE_INTERNAL}/api/v2.1/admin/sysinfo/"
_SEAFILE_LOGIN_URL = f"https://{_SEAFILE_PUBLIC_HOST}/accounts/login/"
_STATUS_TOKEN = os.environ.get("STATUS_TOKEN", "")

app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix="/nas-settings")

# ---------------------------------------------------------------------------
# Settings I/O
# ---------------------------------------------------------------------------


def load_settings() -> dict:
    """Load settings from /data/settings.json, returning defaults if missing."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        lib["id"]: {"ingest_days": DEFAULT_INGEST_DAYS, "uuid": lib["uuid"]}
        for lib in LIBRARIES
    }


def save_settings(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_status() -> dict:
    if STATUS_PATH.exists():
        try:
            with open(STATUS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_status(data: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_commands() -> dict:
    if COMMANDS_PATH.exists():
        try:
            with open(COMMANDS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_commands(data: dict) -> None:
    COMMANDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COMMANDS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def is_seafile_admin() -> bool:
    """Return True if the current request carries a valid Seafile admin session."""
    sessionid = request.cookies.get("sessionid", "")
    if not sessionid:
        return False
    try:
        req = urllib.request.Request(
            _SEAFILE_ADMIN_API,
            headers={
                "Cookie": f"sessionid={sessionid}",
                "Host": _SEAFILE_PUBLIC_HOST,
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        # 403 = authenticated but not admin; 401 = not authenticated — both mean no access
        if exc.code in (401, 403):
            return False
        raise
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
def index():
    if not is_seafile_admin():
        next_url = urllib.parse.quote(request.path, safe="")
        return redirect(f"{_SEAFILE_LOGIN_URL}?next={next_url}")

    settings = load_settings()
    saved = False

    if request.method == "POST":
        for lib in LIBRARIES:
            lid = lib["id"]
            preset = request.form.get(f"preset_{lid}", "730")
            if preset == "custom":
                raw = request.form.get(f"custom_days_{lid}", "").strip()
                try:
                    ingest_days = max(1, int(raw))
                except ValueError:
                    ingest_days = DEFAULT_INGEST_DAYS
            elif preset == "":
                ingest_days = None  # no limit
            else:
                try:
                    ingest_days = int(preset)
                except ValueError:
                    ingest_days = DEFAULT_INGEST_DAYS

            if lid not in settings:
                settings[lid] = {"uuid": lib["uuid"]}
            settings[lid]["ingest_days"] = ingest_days

        save_settings(settings)
        saved = True

    return render_template(
        "settings.html",
        libraries=LIBRARIES,
        settings=settings,
        preset_options=PRESET_OPTIONS,
        preset_values=PRESET_VALUES,
        saved=saved,
    )


@app.route("/status")
def status_page():
    if not is_seafile_admin():
        next_url = urllib.parse.quote(request.path, safe="")
        return redirect(f"{_SEAFILE_LOGIN_URL}?next={next_url}")
    return render_template("status.html", libraries=LIBRARIES)


@app.route("/api/status", methods=["POST"])
def api_status_post():
    """Receive a status report from a seaf-cli container."""
    if not _STATUS_TOKEN:
        return jsonify({"error": "status reporting not configured"}), 404
    if request.headers.get("X-Status-Token") != _STATUS_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    container_id = data.get("container_id", "")
    if not container_id:
        return jsonify({"error": "missing container_id"}), 400
    status = load_status()
    status[container_id] = data
    save_status(status)

    commands = load_commands()
    command = commands.pop(container_id, None)
    if command:
        save_commands(commands)

    return jsonify({"ok": True, **({"command": command} if command else {})})


@app.route("/api/status-data")
def api_status_data():
    """Return current container status with staleness annotations. Requires admin session."""
    if not is_seafile_admin():
        return jsonify({"error": "unauthorized"}), 401
    raw = load_status()
    now = datetime.datetime.utcnow()
    result = {}
    for cid, entry in raw.items():
        reported_at = entry.get("reported_at", "")
        stale = True
        seconds_ago = None
        if reported_at:
            try:
                ts = datetime.datetime.fromisoformat(reported_at.rstrip("Z"))
                delta = (now - ts).total_seconds()
                stale = delta > STATUS_STALE_SECONDS
                seconds_ago = int(delta)
            except Exception:
                pass
        result[cid] = {**entry, "stale": stale, "seconds_ago": seconds_ago}
    return jsonify(result)


@app.route("/api/command", methods=["POST"])
def api_command():
    """Queue a pause or resume command for a seaf-cli container. Requires admin session."""
    if not is_seafile_admin():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    container_id = data.get("container_id", "")
    command = data.get("command", "")
    if not container_id or command not in ("pause", "resume"):
        return jsonify({"error": "invalid request"}), 400
    commands = load_commands()
    commands[container_id] = command
    save_commands(commands)
    return jsonify({"ok": True})


@app.route("/api/settings")
def api_settings():
    """Public JSON endpoint. Containers poll this to get per-library ingest_days."""
    settings = load_settings()
    # Ensure all libraries are present in the response
    result = {}
    for lib in LIBRARIES:
        lid = lib["id"]
        entry = settings.get(lid, {"ingest_days": DEFAULT_INGEST_DAYS, "uuid": lib["uuid"]})
        result[lid] = {
            "ingest_days": entry.get("ingest_days", DEFAULT_INGEST_DAYS),
            "uuid": lib["uuid"],
        }
    return jsonify(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
