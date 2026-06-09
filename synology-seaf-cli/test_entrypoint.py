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
c._folder_size_scan_running = False

calls = []
def fake_run(args, timeout=120):
    calls.append(args)
    return True, "fake output"
c._run_seaf = fake_run
c._refresh_config_cache = lambda: setattr(c, "_config_cache", {})

class FakeRepo:
    def __init__(self, rid): self.id = rid; self.name = "lib"; self.auto_sync = 1
class FakeRpc:
    def __init__(self): self.props = {}; self._repos = [FakeRepo("repo1")]
    def get_repo_list(self, a, b): return self._repos
    def set_repo_property(self, rid, key, value): self.props[(rid, key)] = value
c.rpc = FakeRpc()

def disp(verb, args=None):
    calls.clear()
    return c._dispatch_command({"id": "cmd1", "verb": verb, "args": args or {}})

check("pause -> set auto-sync false",
      disp("pause")["ok"] and c.rpc.props[("repo1", "auto-sync")] == "false")
check("resume -> set auto-sync true",
      disp("resume")["ok"] and c.rpc.props[("repo1", "auto-sync")] == "true")
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

print(f"\n{sum(PASS)}/{len(PASS)} checks passed")
sys.exit(0 if all(PASS) else 1)
