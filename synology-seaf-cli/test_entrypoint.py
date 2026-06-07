"""Verify entrypoint.py _dispatch_command verb routing without a live daemon.

The 'seafile' C-extension and seaf-cli binary are stubbed, so this runs anywhere.

Run:  python test_entrypoint.py
"""
import os
import sys
import types
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

calls = []
def fake_run(args, timeout=120):
    calls.append(args)
    return True, "fake output"
c._run_seaf = fake_run
c._refresh_config_cache = lambda: setattr(c, "_config_cache", {})

class FakeRpc:
    def __init__(self): self.disabled = None
    def disable_auto_sync(self): self.disabled = True
    def enable_auto_sync(self): self.disabled = False
c.rpc = FakeRpc()

def disp(verb, args=None):
    calls.clear()
    return c._dispatch_command({"id": "cmd1", "verb": verb, "args": args or {}})

check("pause -> rpc disable", disp("pause")["ok"] and c.rpc.disabled is True)
check("resume -> rpc enable", disp("resume")["ok"] and c.rpc.disabled is False)
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
check("desync -> desync -d", disp("desync", {"worktree": "/library"})["ok"]
      and calls == [["desync", "-d", "/library"]])
r = disp("desync", {}); check("desync without worktree errors", not r["ok"] and "worktree" in r["error"])
r = disp("create", {"name": "Marketing", "desc": "Assets", "enc_password": "p"})
check("create builds creds + -n -t -e", r["ok"] and "-n" in calls[0] and "Marketing" in calls[0] and "-e" in calls[0])
r = disp("create", {}); check("create without name errors", not r["ok"] and "name" in r["error"])
check("restart stops daemon", disp("restart")["ok"] and calls == [["stop"]])
check("reinit stops daemon", disp("reinit")["ok"] and ["stop"] in calls)
r = disp("bogus"); check("unknown verb errors", not r["ok"] and "unknown verb" in r["error"])

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
