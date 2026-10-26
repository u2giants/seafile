"""Verify entrypoint.py _dispatch_command verb routing without a live daemon.

The 'seafile' C-extension and seaf-cli binary are stubbed, so this runs anywhere.

Run:  python test_entrypoint.py
"""
import os
import sys
import tempfile
import types
import importlib.util
from pathlib import Path

# Stub the 'seafile' C module so entrypoint.py imports without the daemon libs.
sys.modules["seafile"] = types.SimpleNamespace(RpcClient=lambda *a, **k: None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrypoint as ep  # noqa: E402

PASS = []
def check(name, cond):
    PASS.append(bool(cond))
    print(("  ok " if cond else "FAIL ") + name)

# Build a Client without running __init__ (which needs env + a daemon).
c = ep.Client.__new__(ep.Client)
c.binary = ["seaf-cli"]
c.password = "SECRET_PW"; c.token = None
c.url = "https://seafile.designflow.app"; c.username = "nas@pop"
c.ini = Path("/home/seafile/.ccnet/seafile.ini")
c.socket = Path("/seafile/seafile-data/seafile.sock")
c.seafile = Path("/seafile")
c.source = Path(tempfile.mkdtemp())
c.folder_size_cache_path = Path(tempfile.mkdtemp()) / "folder-size-cache.json"
c.health_cache_path = Path(tempfile.mkdtemp()) / "health-cache.json"
c.log = Path(tempfile.mkdtemp()) / "seafile.log"
c.log.write_text("")
c._folder_size_scan_running = False
c._verification_cache = {}
c._last_canary_at = {}
c._api_token = "TOKEN"
c._api_token_checked_at = 0.0
c.alert_webhook_url = None

calls = []
def fake_run(args, timeout=120):
    calls.append(args)
    return True, "fake output"
c._run_seaf = fake_run
c._refresh_config_cache = lambda: setattr(c, "_config_cache", {})

class FakeRepo:
    def __init__(self, rid):
        self.id = rid
        self.name = "lib"
        self.auto_sync = 1
        self.worktree = f"/library/{rid}"
        self.head_cmmt_id = f"head-{rid}"
class FakeRpc:
    def __init__(self):
        self.props = {}
        self._repos = [FakeRepo("repo1"), FakeRepo("repo2")]
    def get_repo_list(self, a, b): return self._repos
    def get_repo(self, rid):
        return next((repo for repo in self._repos if repo.id == rid), None)
    def is_auto_sync_enabled(self): return True
    def get_repo_sync_task(self, rid): return None
    def set_repo_property(self, rid, key, value): self.props[(rid, key)] = value
c.rpc = FakeRpc()
c.libraries = {
    "repo1": {"uuid": "repo1"},
    "repo2": {"uuid": "repo2"},
}
c.target = Path(tempfile.mkdtemp())
c.synchronize()
expected_ignore = "@eaDir\n#recycle\n#snapshot\n@tmp\n.DS_Store\nThumbs.db\n*@SynoEAStream\n*@SynoResource\n*.tmp\n"
check("ignore file is refreshed for already-synced repos",
      (c.target / "repo1" / "seafile-ignore.txt").read_text() == expected_ignore
      and (c.target / "repo2" / "seafile-ignore.txt").read_text() == expected_ignore)

def disp(verb, args=None):
    calls.clear()
    return c._dispatch_command({"id": "cmd1", "verb": verb, "args": args or {}})

check("pause -> set auto-sync false",
      disp("pause")["ok"]
      and c.rpc.props[("repo1", "auto-sync")] == "false"
      and c.rpc.props[("repo2", "auto-sync")] == "false")
check("resume -> set auto-sync true",
      disp("resume")["ok"]
      and c.rpc.props[("repo1", "auto-sync")] == "true"
      and c.rpc.props[("repo2", "auto-sync")] == "true")
calls.clear()
targeted = c._dispatch_command({
    "id": "cmd1",
    "verb": "pause",
    "args": {},
    "library_uuid": "repo2",
})
check("targeted pause only affects matching repo",
      targeted["ok"]
      and c.rpc.props[("repo2", "auto-sync")] == "false"
      and c.rpc.props[("repo1", "auto-sync")] == "true")
check("config_set -> config -k -v",
      disp("config_set", {"key": "upload_limit", "value": 1024})["ok"]
      and calls == [["config", "-k", "upload_limit", "-v", "1024"]])
check("config_get -> config -k",
      disp("config_get", {"key": "download_limit"})["ok"]
      and calls == [["config", "-k", "download_limit"]])
r = disp("config_set", {}); check("config_set without key errors", not r["ok"] and "key" in r["error"])
check("list -> seaf-cli list", disp("list")["ok"] and calls == [["list"]])
r = disp("list_remote")
check("list_remote includes creds",
      r["ok"] and calls[0][0] == "list-remote" and "-s" in calls[0] and "-u" in calls[0])
c._refresh_folder_size_cache_async = lambda force=False: calls.append(["refresh_folder_sizes", force])
check("refresh_folder_sizes starts scanner",
      disp("refresh_folder_sizes")["ok"] and calls == [["refresh_folder_sizes", True]])
c._set_container_memory_limit = lambda value: calls.append(["set_memory_limit", value]) or f"set {value}"
check("set_memory_limit updates container runtime",
      disp("set_memory_limit", {"memory_limit": "8g"})["ok"]
      and calls == [["set_memory_limit", "8g"]])
c._verify_library = lambda name, repo, state, daemon_health=None: {"status": "healthy", "reason": "checked"}
c._daemon_health = lambda pid=None: {"status": "healthy", "issues": []}
c._daemon_pid = lambda: 123
check("verify_now runs sync verification",
      c._dispatch_command({"id": "cmd1", "verb": "verify_now", "args": {}, "library_uuid": "repo1"})["ok"])
c._last_canary_at = {"repo1": 1}
c._dispatch_command({"id": "cmd1", "verb": "write_canary", "args": {}, "library_uuid": "repo1"})
check("write_canary resets canary timer",
      c._last_canary_at.get("repo1") == 0)
check("desync -> desync -d", disp("desync", {"worktree": "/library"})["ok"]
      and calls == [["desync", "-d", "/library"]])
r = disp("desync", {}); check("desync without worktree errors", not r["ok"] and "worktree" in r["error"])
r = disp("create", {"name": "Marketing", "desc": "Assets", "enc_password": "p"})
check("create builds creds + -n -t -e", r["ok"] and "-n" in calls[0] and "Marketing" in calls[0] and "-e" in calls[0])
r = disp("create", {}); check("create without name errors", not r["ok"] and "name" in r["error"])
check("restart stops daemon", disp("restart")["ok"] and calls == [["stop"]])
check("reinit stops daemon", disp("reinit")["ok"] and ["stop"] in calls)
r = disp("bogus"); check("unknown verb errors", not r["ok"] and "unknown verb" in r["error"])

check("disabled schedule allows sync",
      c._schedule_allows_sync({"enabled": False}) is True)
check("empty-day schedule blocks sync",
      c._schedule_allows_sync({"enabled": True, "days": [], "start": "00:00", "end": "23:59", "timezone": "UTC"}) is False)
check("all disabled schedule windows block sync",
      c._schedule_allows_sync({"enabled": True, "timezone": "UTC", "windows": {
          "weekdays": {"enabled": False, "days": [0, 1, 2, 3, 4], "start": "00:00", "end": "23:59"},
          "weekends": {"enabled": False, "days": [5, 6], "start": "00:00", "end": "23:59"},
      }}) is False)
c._apply_schedule({"enabled": True, "days": [], "start": "00:00", "end": "23:59", "timezone": "UTC"})
check("schedule disables repo auto-sync",
      c.rpc.props[("repo1", "auto-sync")] == "false")

c.libraries = {
    "char": {"uuid": "repo1"},
    "decor": {"uuid": "repo2"},
}
check("multi-library env produces per-library status targets",
      c._library_targets() == [("char", "repo1"), ("decor", "repo2")])
c._config_cache = {}
status = c._collect_status("repo2")
check("status report is keyed to requested library uuid",
      status["library_uuid"] == "repo2"
      and [repo["id"] for repo in status["repos"]] == ["repo2"])

check("daemon health flags low inotify limit",
      "below minimum" in ep.Client._daemon_health(c, None)["issues"][0])
check("memory limit normalizes units",
      ep.Client._normalize_memory_limit(c, "8g") == ("8g", 8 * 1024 ** 3)
      and ep.Client._normalize_memory_limit(c, "4096m") == ("4096m", 4096 * 1024 ** 2))
try:
    ep.Client._normalize_memory_limit(c, "8k")
    check("below-floor memory limit rejected", False)
except ValueError as exc:
    check("below-floor memory limit rejected", "at least 16m" in str(exc))

print("== docker socket client (fake unix socket) ==")
import json
import socket as socket_mod
import threading

fake_dir = Path(tempfile.mkdtemp())
fake_sock = fake_dir / "docker.sock"
server = socket_mod.socket(socket_mod.AF_UNIX, socket_mod.SOCK_STREAM)
server.bind(str(fake_sock))
server.listen(4)
seen = []

def reply(request_line, body):
    payload = json.dumps(body).encode()
    return (
        f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
    ).encode() + payload

def serve():
    while True:
        try:
            conn, _ = server.accept()
        except OSError:
            return
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        request_line = head.split(b"\r\n")[0].decode()
        seen.append((request_line, body.decode()))
        if "/update" in request_line:
            conn.sendall(reply(request_line, {"Warnings": None}))
        else:
            conn.sendall(reply(request_line, {
                "HostConfig": {"Memory": 2 * 1024 ** 3,
                               "MemorySwap": 4 * 1024 ** 3}}))
        conn.close()

threading.Thread(target=serve, daemon=True).start()
ep.DOCKER_SOCKET = fake_sock
runtime = ep.Client._container_runtime_status(c)
check("docker status parses live memory",
      runtime["memory_limit"] == 2 * 1024 ** 3
      and runtime["memory_limit_human"] == "2g"
      and runtime["memory_swap"] == 4 * 1024 ** 3)
check("docker status request targets container inspect",
      seen and seen[-1][0].startswith("GET /containers/")
      and "/json" in seen[-1][0])
set_output = ep.Client._set_container_memory_limit(c, "6g")
check("docker update applies and reports",
      set_output == "container memory limit set to 6g"
      and seen[-1][0].startswith("POST /containers/")
      and "/update" in seen[-1][0])
check("docker update body pins memory and 2x swap",
      json.loads(seen[-1][1]) == {"Memory": 6 * 1024 ** 3,
                                  "MemorySwap": 12 * 1024 ** 3})
server.close()

spec = importlib.util.spec_from_file_location(
    "seaf_entrypoint", Path(__file__).with_name("seaf-entrypoint.py")
)
seaf_entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seaf_entrypoint)
src = Path(tempfile.mkdtemp())
library = Path(tempfile.mkdtemp())
(src / "@eaDir").mkdir()
(src / "@eaDir" / "thumb.jpg").write_bytes(b"thumb")
(src / "visible.txt").write_bytes(b"visible")
seaf_entrypoint.SOURCE = src
seaf_entrypoint.LIBRARY = library
wanted = seaf_entrypoint.scan_source(None)
check("@eaDir is ignored by default",
      Path("visible.txt") in wanted and Path("@eaDir/thumb.jpg") not in wanted)
check("SEAF_IGNORE_DIRS can override ignored dirs",
      Path("@eaDir/thumb.jpg") in seaf_entrypoint.scan_source(None, ignored_dirs=set()))
staged = Path(tempfile.mkdtemp())
(staged / "nested").mkdir()
(staged / "nested" / "old.bin").write_bytes(b"old")
(staged / "root.bin").write_bytes(b"root")
seaf_entrypoint.LIBRARY = staged
cleanup_result = seaf_entrypoint.cleanup_staging("test")
check("staging cleanup removes files and dirs",
      cleanup_result["files"] == 2
      and cleanup_result["dirs"] == 1
      and cleanup_result["errors"] == 0
      and list(staged.iterdir()) == [])

scanner = ep.Client.__new__(ep.Client)
scanner.source = Path(tempfile.mkdtemp())
scanner.seafile = Path(tempfile.mkdtemp())
scanner.folder_size_cache_path = scanner.seafile / "folder-size-cache.json"
(scanner.source / "A").mkdir()
(scanner.source / "A" / "one.bin").write_bytes(b"abc")
(scanner.source / "two.bin").write_bytes(b"12345")
cache = ep.Client._build_folder_size_cache(scanner)
check("folder-size cache totals bytes",
      cache["root"]["bytes"] == 8 and cache["root"]["files"] == 2)
check("folder-size cache includes child folder",
      any(x["name"] == "A" and x["bytes"] == 3 for x in cache["children"]))

clone_client = ep.Client.__new__(ep.Client)
clone_client.seafile = Path(tempfile.mkdtemp())
data_dir = clone_client.seafile / "seafile-data"
data_dir.mkdir()
clone_db = data_dir / "clone.db"
import sqlite3  # noqa: E402
with sqlite3.connect(clone_db) as con:
    for table in ["CloneTasks", "CloneTasksMoreInfo", "CloneVersionInfo",
                  "CloneEncInfo", "CloneServerURL"]:
        con.execute(f"create table {table} (repo_id TEXT PRIMARY KEY, value TEXT)")
        con.execute(f"insert into {table} values (?, ?)", ("failed-repo", "x"))
        con.execute(f"insert into {table} values (?, ?)", ("other-repo", "y"))
class FakeCloneTask:
    def __init__(self, rid, state):
        self.repo_id = rid
        self.state = state
class FakeCloneRpc:
    def __init__(self, tasks):
        self._tasks = tasks
    def get_clone_tasks(self):
        return self._tasks
clone_client.rpc = FakeCloneRpc([FakeCloneTask("failed-repo", "error"),
                                 FakeCloneTask("active-repo", "fetch")])
check("failed clone task cleanup runs",
      ep.Client._clear_failed_clone_task(clone_client, "failed-repo") is True)
with sqlite3.connect(clone_db) as con:
    failed_left = con.execute(
        "select count(*) from CloneTasks where repo_id = 'failed-repo'"
    ).fetchone()[0]
    other_left = con.execute(
        "select count(*) from CloneTasks where repo_id = 'other-repo'"
    ).fetchone()[0]
check("failed clone task row removed only for target repo",
      failed_left == 0 and other_left == 1)
check("active clone task cleanup is skipped",
      ep.Client._clear_failed_clone_task(clone_client, "active-repo") is False)
check("clone.db backup created",
      len(list(data_dir.glob("clone.db.bak.*"))) == 1)

# Credential redaction in real _run_seaf output.
import subprocess  # noqa: E402
class _P:
    returncode = 0; stdout = "leaked SECRET_PW here"; stderr = ""
_orig = subprocess.run
subprocess.run = lambda *a, **k: _P()
try:
    ok, out = ep.Client._run_seaf(c, ["whatever"])
    check("credentials redacted in output", "SECRET_PW" not in out and "***" in out)
finally:
    subprocess.run = _orig

# synchronize retries when seaf-daemon silently drops the clone request.
class FakeSyncRpc:
    def __init__(self, register_on):
        self.calls = 0; self.register_on = register_on; self.registered = False
    def get_repo(self, rid): return None
    def get_clone_tasks(self):
        return [FakeCloneTask("new-repo", "fetch")] if self.registered else []
sync_runs = []
def _sync_run(cmd, *a, **k):
    if "sync" in cmd:
        sync_runs.append(cmd)
        if len(sync_runs) >= c.rpc.register_on: c.rpc.registered = True
    return _P()
_saved = (c.rpc, c.libraries, ep.SYNC_REGISTER_TIMEOUT, c._clear_failed_clone_task)
c._clear_failed_clone_task = lambda rid: False
ep.SYNC_REGISTER_TIMEOUT = 0
c.mfa_secret = None
c.rpc = FakeSyncRpc(register_on=2); c.libraries = {"newlib": {"uuid": "new-repo"}}
subprocess.run = _sync_run
try:
    c.synchronize()
    check("sync retried until daemon registers the library", len(sync_runs) == 2)
    sync_runs.clear(); c.rpc = FakeSyncRpc(register_on=99)
    c.synchronize()
    check("sync gives up after SYNC_ATTEMPTS", len(sync_runs) == ep.SYNC_ATTEMPTS)
finally:
    subprocess.run = _orig
    c.rpc, c.libraries, ep.SYNC_REGISTER_TIMEOUT, c._clear_failed_clone_task = _saved

print(f"\n{sum(PASS)}/{len(PASS)} checks passed")
sys.exit(0 if all(PASS) else 1)
