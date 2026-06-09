"""Local verification of app.py: template rendering + command/status queue logic.

Stubs the Seafile admin-session check and points /data persistence at a temp
dir, then drives the Flask test client through the seaf-cli control surface.

Run:  pip install flask && python test_app.py
(No live Seafile/NAS needed — auth and persistence are stubbed.)
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("STATUS_TOKEN", "test-token")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as nas  # noqa: E402

tmp = Path(tempfile.mkdtemp())
nas.SETTINGS_PATH = tmp / "settings.json"
nas.STATUS_PATH = tmp / "status.json"
nas.COMMANDS_PATH = tmp / "commands.json"
nas.RESULTS_PATH = tmp / "results.json"
nas.is_seafile_admin = lambda: True

CHAR = "177cf9de-3066-482e-956a-7ae8d8786c6d"   # Character Licensed UUID
BASE = "https://seafile.designflow.app/nas-settings"
client = nas.app.test_client()

PASS = []
def check(name, cond):
    PASS.append(bool(cond))
    print(("  ok " if cond else "FAIL ") + name)

print("== templates render (admin) ==")
for path in ["/", "/status", "/controls", "/config", "/libraries"]:
    r = client.get(path, base_url=BASE)
    check(f"GET {path} -> 200", r.status_code == 200)
    check(f"GET {path} has nav", b"page-nav" in r.data)

print("== command queue: tiers + confirm gating ==")
r = client.post("/api/command", json={"library_uuid": CHAR, "verb": "pause"})
check("pause queued", r.status_code == 200 and r.get_json().get("ok"))
cmd_id = r.get_json()["id"]

r = client.post("/api/command", json={"library_uuid": CHAR, "verb": "desync", "args": {"worktree": "/x"}})
check("desync without confirm rejected (400)", r.status_code == 400)

r = client.post("/api/command", json={"library_uuid": CHAR, "verb": "desync",
                                       "args": {"worktree": "/x"}, "confirm": True})
check("desync with confirm accepted", r.status_code == 200)

r = client.post("/api/command", json={"library_uuid": CHAR, "verb": "rm-rf"})
check("unknown verb rejected (400)", r.status_code == 400)

r = client.post("/api/command", json={"library_uuid": "nope", "verb": "pause"})
check("unknown library rejected (400)", r.status_code == 400)

r = client.post("/api/command", json={"container_id": "seaf-cli-char-licensed", "command": "resume"})
check("legacy container_id+command accepted", r.status_code == 200)

r = client.post("/api/command", json={"library_uuid": CHAR, "verb": "refresh_folder_sizes"})
check("folder-size refresh command accepted", r.status_code == 200 and r.get_json().get("ok"))

print("== status POST: uuid routing, command handback, result persist ==")
r = client.post("/api/status", json={"library_uuid": CHAR, "container_id": "abc123",
                                      "daemon_alive": True, "reported_at": "2026-06-07T00:00:00Z"},
                headers={"X-Status-Token": "test-token"})
body = r.get_json()
check("status POST 200", r.status_code == 200)
check("first queued command handed back is pause", body.get("command", {}).get("verb") == "pause")
check("handed-back id matches", body.get("command", {}).get("id") == cmd_id)
check("status response includes schedule", "schedule" in body)

r = client.post("/api/status", json={"library_uuid": CHAR}, headers={"X-Status-Token": "bad"})
check("bad status token rejected (401)", r.status_code == 401)

r = client.post("/api/status", json={"library_uuid": CHAR, "container_id": "abc123",
                                      "command_results": [{"id": cmd_id, "verb": "pause", "ok": True,
                                                           "output": "auto-sync disabled"}],
                                      "reported_at": "2026-06-07T00:00:30Z"},
                headers={"X-Status-Token": "test-token"})
check("FIFO: next command is desync", r.get_json().get("command", {}).get("verb") == "desync")

print("== status-data: admin view has results + pending ==")
r = client.get("/api/status-data", base_url=BASE)
entry = r.get_json().get(CHAR, {})
check("status-data keyed by uuid", CHAR in r.get_json())
check("recent_results includes pause result",
      any(x.get("verb") == "pause" and x.get("ok") for x in entry.get("recent_results", [])))
check("resume still pending in queue",
      any(c.get("verb") == "resume" for c in entry.get("pending_commands", [])))

print("== /api/settings (container poll) unchanged ==")
client.post("/", data={
    "preset_seaf-cli-char-licensed": "365",
    "schedule_enabled_seaf-cli-char-licensed": "on",
    "schedule_weekdays_enabled_seaf-cli-char-licensed": "on",
    "schedule_weekdays_start_seaf-cli-char-licensed": "18:30",
    "schedule_weekdays_end_seaf-cli-char-licensed": "06:45",
    "schedule_weekends_enabled_seaf-cli-char-licensed": "on",
    "schedule_weekends_start_seaf-cli-char-licensed": "10:00",
    "schedule_weekends_end_seaf-cli-char-licensed": "16:00",
    "schedule_timezone_seaf-cli-char-licensed": "America/New_York",
    "preset_seaf-cli-generic-decor": "730",
    "schedule_timezone_seaf-cli-generic-decor": "America/New_York",
}, base_url=BASE)
r = client.get("/api/settings")
check("/api/settings returns lib uuid",
      r.status_code == 200 and r.get_json().get("seaf-cli-char-licensed", {}).get("uuid") == CHAR)
check("/api/settings returns schedule",
      isinstance(r.get_json().get("seaf-cli-char-licensed", {}).get("schedule"), dict))
schedule = r.get_json()["seaf-cli-char-licensed"]["schedule"]
check("/api/settings returns weekday/weekend windows",
      schedule["windows"]["weekdays"]["start"] == "18:30"
      and schedule["windows"]["weekends"]["end"] == "16:00")
legacy = nas.normalize_schedule({
    "enabled": True,
    "days": [0, 1, 2, 3, 4],
    "start": "20:00",
    "end": "06:00",
    "timezone": "America/New_York",
})
check("legacy schedule normalizes to windows",
      legacy["windows"]["weekdays"]["start"] == "20:00"
      and legacy["windows"]["weekends"]["enabled"] is False)

print(f"\n{sum(PASS)}/{len(PASS)} checks passed")
sys.exit(0 if all(PASS) else 1)
