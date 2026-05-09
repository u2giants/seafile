#!/usr/bin/env python3
"""
nas-settings/app.py

Flask web app for managing NAS sync configuration (SEAF_INGEST_DAYS)
per Seafile library. Runs behind Caddy at /nas-settings/.

Env vars:
  AUTH_PASSWORD   Required. Password for the settings UI.
  SECRET_KEY      Required. Random string for Flask session signing.

State is persisted to /data/settings.json.
"""
import json
import os
import urllib.request
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
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
DEFAULT_INGEST_DAYS = 730

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

AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
if not AUTH_PASSWORD:
    raise RuntimeError("AUTH_PASSWORD env var is required")

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


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def logged_in() -> bool:
    return session.get("authenticated") is True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == AUTH_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "Incorrect password. Please try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
def index():
    if not logged_in():
        return redirect(url_for("login"))

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
