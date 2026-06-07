#!/usr/bin/env python3
"""
nas-settings/app.py

Flask web app that gives the Seafile server's web UI a GUI for the seaf-cli
client running on the Synology NAS. Runs behind Caddy at /nas-settings/.

It does two jobs:

  1. Ingest-window settings (SEAF_INGEST_DAYS) per library — the original panel.
  2. A full seaf-cli control surface: live status, sync controls (pause/resume,
     restart, stop), daemon config (upload/download limits, etc.), and library
     management (list, list-remote, desync, create). The server cannot reach
     the NAS directly, so every action is queued and the NAS container picks it
     up on its next status poll (~30 s), then reports the result back.

Commands are routed by **library UUID** (stable, known to both the server panel
and the container via SEAF_LIBRARY) — not by the container's ephemeral Docker
hostname.

Auth: delegates to Seafile admin session. Any request that carries a valid
Seafile sessionid cookie belonging to a system admin is allowed in. No
separate login required — the user's existing Seafile session is reused.

Env vars:
  SEAFILE_INTERNAL_URL  Base URL for Seafile's internal API (default: http://seafile:8000)
  SEAFILE_PUBLIC_HOST   Public hostname used in the Cookie/Host header (default: seafile.designflow.app)
  SECRET_KEY            Required. Random string for Flask session signing.
  STATUS_TOKEN          Shared secret the NAS containers send with status reports.

State is persisted under /data/ (settings.json, status.json, commands.json,
results.json).
"""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

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

# Fast lookups between the compose service id and the library UUID.
LIB_BY_UUID = {lib["uuid"]: lib for lib in LIBRARIES}
LIB_BY_ID = {lib["id"]: lib for lib in LIBRARIES}

RESULTS_PATH = Path("/data/results.json")
MAX_RESULTS_PER_LIB = 25  # keep only the most recent command results per library

# ---------------------------------------------------------------------------
# seaf-cli command surface
#
# Every verb the GUI can queue, grouped by safety tier. The NAS container's
# entrypoint.py dispatches these. "Guidance-only" seaf-cli commands (download /
# sync a brand-new folder, which need a new container bind-mount + redeploy) are
# deliberately NOT verbs — the Libraries page shows the manual steps instead.
# ---------------------------------------------------------------------------

READ_VERBS = {"list", "list_remote", "config_get"}        # read-only queries
SAFE_VERBS = {"pause", "resume", "restart", "stop", "config_set"}  # reversible
GUARDED_VERBS = {"desync", "create", "reinit"}            # require typed confirm
ALL_VERBS = READ_VERBS | SAFE_VERBS | GUARDED_VERBS

# Well-known seaf-daemon config keys (seaf-cli config -k <key> [-v <value>]).
# The Config page also accepts any free-form key so coverage is total.
KNOWN_CONFIG_KEYS = [
    {"key": "upload_limit", "label": "Upload limit (KB/s)", "type": "int",
     "help": "Cap upload speed in KB/s. 0 or blank = unlimited."},
    {"key": "download_limit", "label": "Download limit (KB/s)", "type": "int",
     "help": "Cap download speed in KB/s. 0 or blank = unlimited."},
    {"key": "disable_verify_certificate", "label": "Disable TLS verification", "type": "bool",
     "help": "Skip server certificate checks. Leave off unless the server uses a self-signed cert."},
    {"key": "sync_extra_temp_file", "label": "Sync extra temp files", "type": "bool",
     "help": "Also sync editor lock/temp files. Usually off."},
]
KNOWN_CONFIG_KEY_NAMES = [k["key"] for k in KNOWN_CONFIG_KEYS]

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


def load_results() -> dict:
    if RESULTS_PATH.exists():
        try:
            with open(RESULTS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_results(data: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
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


def _login_redirect():
    """Redirect an unauthenticated browser to the Seafile login, then back here."""
    next_url = urllib.parse.quote(request.path, safe="")
    return redirect(f"{_SEAFILE_LOGIN_URL}?next={next_url}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET", "POST"])
def index():
    if not is_seafile_admin():
        return _login_redirect()

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
        active_tab="settings",
    )


@app.route("/status")
def status_page():
    if not is_seafile_admin():
        return _login_redirect()
    return render_template("status.html", libraries=LIBRARIES, active_tab="dashboard")


@app.route("/controls")
def controls_page():
    if not is_seafile_admin():
        return _login_redirect()
    return render_template("controls.html", libraries=LIBRARIES, active_tab="controls")


@app.route("/config")
def config_page():
    if not is_seafile_admin():
        return _login_redirect()
    return render_template(
        "config.html",
        libraries=LIBRARIES,
        config_keys=KNOWN_CONFIG_KEYS,
        active_tab="config",
    )


@app.route("/libraries")
def libraries_page():
    if not is_seafile_admin():
        return _login_redirect()
    return render_template(
        "libraries.html",
        libraries=LIBRARIES,
        seafile_host=_SEAFILE_PUBLIC_HOST,
        active_tab="libraries",
    )


@app.route("/api/status", methods=["POST"])
def api_status_post():
    """Receive a status report from a seaf-cli container, persist any command
    results it carries, and hand back the next queued command.

    Reports and commands are keyed by the library UUID (data["library_uuid"]),
    which both sides know — not the container's ephemeral Docker hostname.
    """
    if not _STATUS_TOKEN:
        return jsonify({"error": "status reporting not configured"}), 404
    if request.headers.get("X-Status-Token") != _STATUS_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    uuid = data.get("library_uuid") or data.get("container_id", "")
    if not uuid:
        return jsonify({"error": "missing library_uuid"}), 400

    status = load_status()
    status[uuid] = data
    save_status(status)

    # Persist any command results the container is reporting back.
    reported = data.get("command_results") or []
    if reported:
        results = load_results()
        bucket = results.get(uuid, [])
        bucket.extend(reported)
        results[uuid] = bucket[-MAX_RESULTS_PER_LIB:]
        save_results(results)

    # Hand back the next queued command for this library, if any.
    commands = load_commands()
    queue = commands.get(uuid, [])
    command = queue.pop(0) if queue else None
    if command is not None:
        commands[uuid] = queue
        save_commands(commands)

    return jsonify({"ok": True, **({"command": command} if command else {})})


@app.route("/api/status-data")
def api_status_data():
    """Return current per-library status with staleness, pending commands, and
    recent command results. Keyed by library UUID. Requires admin session."""
    if not is_seafile_admin():
        return jsonify({"error": "unauthorized"}), 401
    raw = load_status()
    commands = load_commands()
    results = load_results()
    now = datetime.datetime.utcnow()
    result = {}
    for key, entry in raw.items():
        uuid = entry.get("library_uuid") or key
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
        result[uuid] = {
            **entry,
            "stale": stale,
            "seconds_ago": seconds_ago,
            "pending_commands": commands.get(uuid, []),
            "recent_results": list(reversed(results.get(uuid, []))),
        }
    return jsonify(result)


@app.route("/api/command", methods=["POST"])
def api_command():
    """Queue a seaf-cli command for a library's container. Requires admin session.

    Body: {library_uuid, verb, args?, confirm?}. Destructive verbs
    (desync/create/reinit) are rejected unless `confirm` is truthy.
    """
    if not is_seafile_admin():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}

    # Prefer library_uuid; accept a legacy container_id that maps to a known lib.
    uuid = data.get("library_uuid", "")
    if not uuid:
        legacy = data.get("container_id", "")
        uuid = LIB_BY_ID.get(legacy, {}).get("uuid", "")
    # Accept either {verb} (new) or {command} (legacy pause/resume).
    verb = data.get("verb") or data.get("command", "")
    args = data.get("args") or {}

    if uuid not in LIB_BY_UUID:
        return jsonify({"error": "unknown library"}), 400
    if verb not in ALL_VERBS:
        return jsonify({"error": "unknown verb"}), 400
    if verb in GUARDED_VERBS and not data.get("confirm"):
        return jsonify({"error": "confirmation required"}), 400

    cmd = {
        "id": uuid4().hex[:12],
        "verb": verb,
        "args": args,
        "queued_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    commands = load_commands()
    commands.setdefault(uuid, []).append(cmd)
    save_commands(commands)
    return jsonify({"ok": True, "id": cmd["id"]})


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
