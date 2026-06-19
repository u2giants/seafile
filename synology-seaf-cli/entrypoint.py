#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import datetime
import json
import logging
import os
import signal
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse

import seafile
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


DAEMON_START_TIMEOUT = 60  # seconds to wait for socket after seaf-cli start
INIT_TIMEOUT = 30          # seconds to wait for .ini after seaf-cli init
WATCHDOG_INTERVAL_SECONDS = 10
STATUS_REPORT_INTERVAL_SECONDS = 30
FOLDER_SIZE_SCAN_HOUR = 2
FOLDER_SIZE_SCAN_TZ = "America/New_York"
CANARY_FILENAME = os.environ.get("SEAF_CANARY_FILENAME", ".seafile-sync-canary.json")
CANARY_INTERVAL_SECONDS = int(os.environ.get("SEAF_CANARY_INTERVAL_SECONDS", "600"))
CANARY_GRACE_SECONDS = int(os.environ.get("SEAF_CANARY_GRACE_SECONDS", "180"))
INOTIFY_WARN_USAGE = float(os.environ.get("SEAF_INOTIFY_WARN_USAGE", "0.80"))
MIN_INOTIFY_WATCHES = int(os.environ.get("SEAF_MIN_INOTIFY_WATCHES", "1048576"))
ALERT_COOLDOWN_SECONDS = int(os.environ.get("SEAF_ALERT_COOLDOWN_SECONDS", "3600"))

# Well-known seaf-daemon config keys reported in the status snapshot so the
# nas-settings Config page can show current values. Any key can still be
# get/set on demand via a config_get / config_set command.
KNOWN_CONFIG_KEYS = [
    "upload_limit",
    "download_limit",
    "disable_verify_certificate",
    "sync_extra_temp_file",
]


class BadConfiguration(Exception):
    pass


def get_configuration(variable: str, *args) -> Any:
    """Helper function to get a configuration.
    see https://gitlab.com/-/snippets/1941025
    """
    if args:
        default = args[0]

    try:
        file = os.environ[f"{variable}_FILE"]
    except KeyError:
        pass
    else:
        with open(file, "rt") as fo:
            return fo.read()

    try:
        return os.environ[variable]
    except KeyError:
        pass

    try:
        return default
    except UnboundLocalError:
        raise BadConfiguration(
            f"Environment variable {variable} was not found but is required."
        )


class Client:

    def __init__(self) -> None:
        self.username: str = get_configuration("SEAF_USERNAME")
        self.url: str = get_configuration("SEAF_SERVER_URL")
        self.skip_ssl_cert: bool = bool(get_configuration("SEAF_SKIP_SSL_CERT", None))
        self.upload_limit: int = get_configuration("SEAF_UPLOAD_LIMIT", None)
        self.download_limit: int = get_configuration("SEAF_DOWNLOAD_LIMIT", None)
        self.mfa_secret: str = get_configuration("SEAF_2FA_SECRET", None)

        self.password: str = get_configuration("SEAF_PASSWORD", None)
        self.token: str = get_configuration("SEAF_TOKEN", None)
        if not (self.password or self.token):
            raise BadConfiguration(
                "At least one of SEAF_PASSWORD or SEAF_TOKEN are required."
            )

        self.ini = Path.home().joinpath(".ccnet", "seafile.ini")
        self.log = Path.home().joinpath(".ccnet", "logs", "seafile.log")
        self.seafile = Path("/seafile")
        self.socket = self.seafile.joinpath("seafile-data", "seafile.sock")
        self.target = Path("/library")
        self.source = Path("/library")
        self.folder_size_cache_path = self.seafile / "folder-size-cache.json"
        self.health_cache_path = self.seafile / "health-cache.json"
        self._folder_size_scan_lock = threading.Lock()
        self._folder_size_scan_running = False
        self._api_token: str | None = None
        self._api_token_checked_at = 0.0
        self._verification_cache: dict[str, dict] = {}
        self._last_canary_at: dict[str, float] = {}
        self.alert_webhook_url = get_configuration("SEAF_ALERT_WEBHOOK_URL", None)

        if self.socket.exists():
            self.rpc = seafile.RpcClient(str(self.socket))

        self.binary = ["seaf-cli"]
        self._get_librairies()

    def _get_librairies(self):
        self.libraries = {}

        single_library_variables = ["SEAF_LIBRARY", "SEAF_LIBRARY_UUID", "SEAF_LIBRARY_PASSWORD"]
        if any(environ in single_library_variables for environ in os.environ):
            logger.info("Single library detected. Multiple libraries will be ignored.")
            library = {}

            uuid = None
            if legacy := os.getenv("SEAF_LIBRARY_UUID", None):
                logger.warning("SEAF_LIBRARY_UUID is obsolete, please use SEAF_LIBRARY instead.")
                uuid = legacy
            if current := os.getenv("SEAF_LIBRARY", None):
                uuid = current

            if uuid is None:
                raise Exception("Please provide an UUID with SEAF_LIBRARY for single library usage.")
            library["uuid"] = uuid

            if password := os.getenv("SEAF_LIBRARY_PASSWORD", None):
                library["password"] = password

            self.libraries["_"] = library
            return

        for variable in sorted(os.environ):
            if variable.startswith("SEAF_LIBRARY"):
                name = variable.split("_")[2].lower()

                if "_PASSWORD" in variable:
                    password = get_configuration(variable, None)
                    try:
                        if password:
                            self.libraries[name]["password"] = password
                    except KeyError:
                        logger.warning(f"Cannot set a password to unknown library {name}")
                else:
                    self.libraries[name] = {}
                    uuid = os.environ[variable]
                    self.libraries[name]["uuid"] = uuid

    def _get_credential_args(self) -> list[str]:
        return [
            "-s", self.url,
            "-u", self.username,
            *(["-T", self.token] if self.token else ["-p", self.password])
        ]

    def _wait_for_path(self, path: Path, label: str, timeout: int) -> None:
        deadline = time.monotonic() + timeout
        while not path.exists():
            if time.monotonic() > deadline:
                logger.error(f"Timed out after {timeout}s waiting for {label} — daemon may have failed to start")
                sys.exit(1)
            logger.debug(f"Waiting for {label}...")
            time.sleep(1)

    def _daemon_pid(self) -> int | None:
        for pidfile in [
            self.seafile / "seafile-data" / "seafile.pid",
            Path.home() / ".ccnet" / "seafile.pid",
        ]:
            if pidfile.exists():
                try:
                    return int(pidfile.read_text().strip())
                except (ValueError, OSError):
                    pass
        # fallback: scan /proc for seaf-daemon
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmdline = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode()
                if "seaf-daemon" in cmdline:
                    return int(entry.name)
            except OSError:
                pass
        return None

    def initialize(self):
        logger.info("Initializing `seaf-cli`.")
        if not self.ini.exists():
            logger.info("Seafile .ini file not found, running `seaf-cli init`")
            result = subprocess.run(self.binary + ["init", "-d", str(self.seafile)])
            if result.returncode != 0:
                logger.error(f"`seaf-cli init` failed (exit {result.returncode})")
                sys.exit(1)
            self._wait_for_path(self.ini, "seafile.ini", INIT_TIMEOUT)

        # Remove stale PID/socket left by a previous container (same volume, new PID
        # namespace) — seaf-cli start checks the PID file and exits 1 if that PID
        # currently exists (even if it's an unrelated process in the new namespace).
        for stale in [self.seafile / "seafile-data" / "seafile.pid", self.socket]:
            stale.unlink(missing_ok=True)

        logger.info("Starting `seaf-cli`.")
        result = subprocess.run(self.binary + ["start"])
        if result.returncode != 0:
            logger.error(f"`seaf-cli start` failed (exit {result.returncode})")
            sys.exit(1)
        self._wait_for_path(self.socket, "seafile socket", DAEMON_START_TIMEOUT)

        self.rpc = seafile.RpcClient(str(self.socket))

    def configure(self):
        command = self.binary + ["config"]
        if self.skip_ssl_cert:
            subprocess.run(command + ["-k", "disable_verify_certificate", "-v", str(self.skip_ssl_cert)], check=True)
        if self.download_limit:
            subprocess.run(command + ["-k", "download_limit", "-v", self.download_limit], check=True)
        if self.upload_limit:
            subprocess.run(command + ["-k", "upload_limit", "-v", self.upload_limit], check=True)

    def _write_seafile_ignore(self, target: Path) -> None:
        ignore_file = target / "seafile-ignore.txt"
        content = "@eaDir\n#recycle\n#snapshot\n@tmp\n.DS_Store\nThumbs.db\n*.tmp\n"
        try:
            current = ignore_file.read_text()
        except OSError:
            current = None
        if current != content:
            ignore_file.write_text(content)
            logger.info("Wrote seafile-ignore.txt to %s", target)

    def synchronize(self):
        core = [*self.binary, "sync", *self._get_credential_args()]
        for name, configuration in self.libraries.items():
            uuid = configuration["uuid"]

            target = self.target if name == "_" else self.target.joinpath(name)
            target.mkdir(parents=True, exist_ok=True)
            self._write_seafile_ignore(target)

            repository = self.rpc.get_repo(uuid)
            if repository is not None:
                logger.info(f"Library {name} is already synced.")
                continue

            command = core + ["-l", uuid]

            if "password" in configuration:
                command += ["-e", configuration["password"]]
            command += ["-d", str(target)]

            if self.mfa_secret:
                result = subprocess.run(
                    ["oathtool", "--base32", "--totp", self.mfa_secret],
                    capture_output=True, text=True, check=True,
                )
                command += ["-a", result.stdout.strip()]

            # Redact credentials before logging
            secrets = {s for s in (self.password, self.token) if s}
            safe = ["***" if a in secrets else a for a in command]
            logger.debug(f"Running: {' '.join(safe)}")

            self._clear_failed_clone_task(uuid)
            result = subprocess.run(command)
            if result.returncode != 0:
                logger.error(f"`seaf-cli sync` for library {name!r} failed (exit {result.returncode})")

    def _clear_failed_clone_task(self, repo_id: str) -> bool:
        """Remove a stale failed clone task so seaf-cli can retry the library.

        seaf-daemon keeps failed initial syncs in clone.db. A later `seaf-cli sync`
        for the same repo then exits with "Task is already in progress", even
        after the server-side cause is fixed. Only clear tasks already marked
        error; active fetch/upload tasks are left alone.
        """
        try:
            tasks = self.rpc.get_clone_tasks()
        except Exception:
            return False

        failed = False
        for task in tasks:
            if getattr(task, "repo_id", "") != repo_id:
                continue
            if getattr(task, "state", "") == "error":
                failed = True
                break
        if not failed:
            return False

        db = self.seafile / "seafile-data" / "clone.db"
        if not db.exists():
            return False

        backup = db.with_name(f"{db.name}.bak.{int(time.time())}")
        shutil.copy2(db, backup)
        tables = [
            "CloneTasks",
            "CloneTasksMoreInfo",
            "CloneVersionInfo",
            "CloneEncInfo",
            "CloneServerURL",
        ]
        removed = 0
        with sqlite3.connect(db) as con:
            for table in tables:
                try:
                    cur = con.execute(
                        f"delete from {table} where repo_id = ?", (repo_id,)
                    )
                    removed += cur.rowcount
                except sqlite3.Error as exc:
                    logger.warning("Could not clean %s in clone.db: %s", table, exc)
            con.commit()

        if removed:
            logger.warning(
                "Cleared failed clone task for %s from clone.db; backup at %s",
                repo_id, backup,
            )
            return True
        backup.unlink(missing_ok=True)
        return False

    def watch(self):
        pid = self._daemon_pid()
        if pid is None:
            logger.error("Cannot locate seaf-daemon PID — exiting to trigger container restart")
            sys.exit(1)
        logger.info(f"Monitoring seaf-daemon (PID {pid})")
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                logger.error(f"seaf-daemon (PID {pid}) has exited — restarting container")
                sys.exit(1)
            time.sleep(WATCHDOG_INTERVAL_SECONDS)

    def _library_targets(self) -> list[tuple[str, str]]:
        """Return (name, uuid) pairs that should report status."""
        targets = [
            (name, config.get("uuid", ""))
            for name, config in self.libraries.items()
            if config.get("uuid")
        ]
        if targets:
            return targets
        uuid = os.environ.get("SEAF_LIBRARY", "")
        return [("_", uuid)] if uuid else []

    def _name_for_library_uuid(self, library_uuid: str | None) -> str:
        for name, uuid in self._library_targets():
            if uuid == library_uuid:
                return name
        return "_"

    def _repos_for_library(self, library_uuid: str | None):
        repos = self.rpc.get_repo_list(-1, -1)
        if not library_uuid:
            return repos
        return [repo for repo in repos if getattr(repo, "id", "") == library_uuid]

    def _collect_status(self, library_uuid: str | None = None) -> dict:
        """Gather current sync state for reporting to the nas-settings panel."""
        pid = self._daemon_pid()
        daemon_alive = False
        if pid is not None:
            try:
                os.kill(pid, 0)
                daemon_alive = True
            except ProcessLookupError:
                pass

        repos = []
        verification = None
        daemon_health = self._daemon_health(pid)
        if hasattr(self, "rpc"):
            try:
                rpc_repos = self._repos_for_library(library_uuid)
                auto_sync = self.rpc.is_auto_sync_enabled()
                for repo in rpc_repos:
                    entry: dict = {
                        "name": repo.name,
                        "id": repo.id,
                        "state": None,
                        "rate_kb": None,
                        "progress_pct": None,
                        "error": None,
                    }
                    if not auto_sync or not repo.auto_sync:
                        entry["state"] = "auto sync disabled"
                    else:
                        task = self.rpc.get_repo_sync_task(repo.id)
                        if task is None:
                            entry["state"] = "waiting"
                        else:
                            entry["state"] = task.state
                            if task.state in ("uploading", "downloading"):
                                tx = self.rpc.find_transfer_task(repo.id)
                                if tx is not None:
                                    if tx.block_total > 0:
                                        entry["progress_pct"] = round(
                                            tx.block_done / tx.block_total * 100, 1
                                        )
                                    entry["rate_kb"] = round(tx.rate / 1024.0, 1)
                                    entry["blocks_done"] = getattr(tx, "block_done", None)
                                    entry["blocks_total"] = getattr(tx, "block_total", None)
                            elif task.state == "error":
                                entry["error"] = self.rpc.sync_error_id_to_str(task.error)
                    if library_uuid and repo.id == library_uuid:
                        verification = self._verify_library(
                            self._name_for_library_uuid(library_uuid),
                            repo,
                            entry.get("state"),
                            daemon_health,
                        )
                        if verification.get("status") == "anomaly":
                            entry["error"] = verification.get("reason")
                    repos.append(entry)
            except Exception:
                pass

        ingest: dict = {}
        ingest_path = Path("/tmp/ingest-status.json")
        if ingest_path.exists():
            try:
                ingest = json.loads(ingest_path.read_text())
            except Exception:
                pass

        # "Paused" reflects the per-repo auto-sync property (there is no global
        # toggle in this client): paused when every synced repo has auto-sync off.
        paused = False
        if hasattr(self, "rpc"):
            try:
                rl = self._repos_for_library(library_uuid)
                if rl:
                    paused = all(not r.auto_sync for r in rl)
            except Exception:
                pass

        # Local libraries (seaf-cli list) — name/id/worktree, the worktree being
        # the path the Libraries page passes back for a desync.
        local_repos = []
        if hasattr(self, "rpc"):
            try:
                for repo in self._repos_for_library(library_uuid):
                    local_repos.append({
                        "name": repo.name,
                        "id": repo.id,
                        "worktree": getattr(repo, "worktree", None),
                    })
            except Exception:
                pass

        # Daemon config snapshot (seaf-cli config -k). Cached and refreshed only
        # on config_set, so the 30 s status loop stays cheap.
        if getattr(self, "_config_cache", None) is None:
            try:
                self._refresh_config_cache()
            except Exception:
                self._config_cache = {}

        return {
            "container_id": os.environ.get("HOSTNAME", "unknown"),
            "library_uuid": library_uuid or os.environ.get("SEAF_LIBRARY", ""),
            "reported_at": datetime.datetime.utcnow().isoformat() + "Z",
            "daemon_pid": pid,
            "daemon_alive": daemon_alive,
            "daemon_health": daemon_health,
            "heartbeat_interval_seconds": STATUS_REPORT_INTERVAL_SECONDS,
            "watchdog_interval_seconds": WATCHDOG_INTERVAL_SECONDS,
            "paused": paused,
            "repos": repos,
            "local_repos": local_repos,
            "verification": verification or self._verification_cache.get(library_uuid or ""),
            "config": self._config_cache or {},
            "confdir": str(self.ini.parent),
            "initialized": self.ini.exists(),
            "staging_files": ingest.get("files"),
            "staging_changed_files": ingest.get("changed_files"),
            "staging_method": ingest.get("method"),
            "source_path": ingest.get("source_path"),
            "source_label": ingest.get("source_label"),
            "staging_path": ingest.get("staging_path"),
            "last_ingest_at": ingest.get("last_ingest_at"),
            "ingest_days": ingest.get("ingest_days"),
            "folder_size_cache": self._load_folder_size_cache(),
        }

    def _run_seaf(self, args: list[str], timeout: int = 120) -> tuple[bool, str]:
        """Run a seaf-cli subcommand; return (ok, combined output) with any
        credentials redacted so they never reach the server's result log."""
        try:
            proc = subprocess.run(
                self.binary + args, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, "command timed out"
        except Exception as exc:
            return False, str(exc)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        for secret in {s for s in (self.password, self.token) if s}:
            out = out.replace(secret, "***")
        return proc.returncode == 0, out

    def _refresh_config_cache(self) -> None:
        """Populate self._config_cache with current values of the known keys."""
        cache: dict = {}
        for key in KNOWN_CONFIG_KEYS:
            ok, out = self._run_seaf(["config", "-k", key], timeout=10)
            cache[key] = out if (ok and out) else None
        self._config_cache = cache

    def _load_folder_size_cache(self) -> dict | None:
        try:
            return json.loads(self.folder_size_cache_path.read_text())
        except Exception:
            return None

    def _load_health_cache(self) -> dict:
        try:
            data = json.loads(self.health_cache_path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_health_cache(self, data: dict) -> None:
        self.health_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.health_cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.health_cache_path)

    def _api_request(self, path: str, *, data: dict | None = None) -> Any:
        if data is not None:
            encoded = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(self.url.rstrip("/") + path, data=encoded, method="POST")
        else:
            req = urllib.request.Request(self.url.rstrip("/") + path)
        if self._api_token:
            req.add_header("Authorization", f"Token {self._api_token}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
        return json.loads(raw) if raw else None

    def _ensure_api_token(self) -> bool:
        if self._api_token:
            return True
        # Avoid hammering auth if credentials are wrong or the API is temporarily down.
        if time.monotonic() - self._api_token_checked_at < 300:
            return False
        self._api_token_checked_at = time.monotonic()
        if self.token:
            self._api_token = self.token
            return True
        if not self.password:
            return False
        try:
            body = self._api_request(
                "/api2/auth-token/",
                data={"username": self.username, "password": self.password},
            )
            token = body.get("token") if isinstance(body, dict) else None
            if token:
                self._api_token = token
                return True
        except Exception as exc:
            logger.warning("Could not obtain Seafile API token for verification: %s", exc)
        return False

    def _target_for_library_name(self, name: str) -> Path:
        return self.target if name == "_" else self.target / name

    def _read_int_file(self, path: Path) -> int | None:
        try:
            return int(path.read_text().strip())
        except Exception:
            return None

    def _local_repo_head(self, repo: Any) -> str | None:
        for attr in ("head_cmmt_id", "head_commit_id", "last_commit_id", "commit_id", "head"):
            value = getattr(repo, attr, None)
            if value:
                return str(value)
        return None

    def _server_repo_head(self, repo_id: str) -> str | None:
        if not self._ensure_api_token():
            raise RuntimeError("Seafile API token unavailable")
        data = self._api_request(f"/api2/repos/{repo_id}/")
        if not isinstance(data, dict):
            raise RuntimeError("unexpected server repo response")
        for key in ("head_cmmt_id", "head_commit_id", "last_commit_id", "commit_id", "head"):
            value = data.get(key)
            if value:
                return str(value)
        return None

    def _scan_log_watch_errors(self) -> dict:
        cache = self._load_health_cache()
        log_state = cache.get("_seafile_log", {}) if isinstance(cache.get("_seafile_log"), dict) else {}
        try:
            st = self.log.stat()
        except OSError:
            return {"new_watch_errors": 0, "error": "seafile.log unavailable"}

        inode = f"{st.st_dev}:{st.st_ino}"
        offset = int(log_state.get("offset") or 0) if log_state.get("inode") == inode else 0
        if st.st_size < offset:
            offset = 0

        new_watch_errors = 0
        bytes_read = 0
        try:
            with self.log.open("r", errors="replace") as fh:
                fh.seek(offset)
                for line in fh:
                    bytes_read += len(line.encode(errors="replace"))
                    if "fail to add watch" in line or "No space left on device" in line:
                        new_watch_errors += 1
                new_offset = fh.tell()
        except Exception as exc:
            return {"new_watch_errors": 0, "error": str(exc)}

        cache["_seafile_log"] = {"inode": inode, "offset": new_offset}
        self._save_health_cache(cache)
        return {
            "new_watch_errors": new_watch_errors,
            "bytes_read": bytes_read,
            "log_size": st.st_size,
        }

    def _inotify_usage(self, pid: int | None) -> dict:
        max_watches = self._read_int_file(Path("/proc/sys/fs/inotify/max_user_watches"))
        max_instances = self._read_int_file(Path("/proc/sys/fs/inotify/max_user_instances"))
        watches = 0
        instances = 0
        errors = 0

        fdinfo_root = Path(f"/proc/{pid}/fdinfo") if pid else None
        if fdinfo_root and fdinfo_root.exists():
            for fdinfo in fdinfo_root.iterdir():
                try:
                    count = sum(1 for line in fdinfo.read_text(errors="replace").splitlines()
                                if line.startswith("inotify "))
                    if count:
                        instances += 1
                        watches += count
                except OSError:
                    errors += 1
        else:
            errors += 1

        usage = (watches / max_watches) if max_watches else None
        return {
            "watches_in_use": watches,
            "instances_in_use": instances,
            "max_user_watches": max_watches,
            "max_user_instances": max_instances,
            "usage": usage,
            "errors": errors,
        }

    def _daemon_health(self, pid: int | None) -> dict:
        log_health = self._scan_log_watch_errors()
        inotify = self._inotify_usage(pid)
        issues = []
        if (inotify.get("max_user_watches") or 0) < MIN_INOTIFY_WATCHES:
            issues.append(
                f"fs.inotify.max_user_watches below minimum "
                f"({inotify.get('max_user_watches')} < {MIN_INOTIFY_WATCHES})"
            )
        if inotify.get("usage") is not None and inotify["usage"] >= INOTIFY_WARN_USAGE:
            issues.append(
                f"inotify watch usage high "
                f"({inotify['watches_in_use']}/{inotify['max_user_watches']})"
            )
        if log_health.get("new_watch_errors", 0) > 0:
            issues.append(
                f"seaf-daemon logged {log_health['new_watch_errors']} new inotify watch errors"
            )
        return {
            "status": "anomaly" if issues else "healthy",
            "issues": issues,
            "inotify": inotify,
            "log": log_health,
            "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        }

    def _canary_status(self, repo_id: str, root: Path) -> dict:
        now = time.monotonic()
        canary = root / CANARY_FILENAME
        if now - self._last_canary_at.get(repo_id, 0) >= CANARY_INTERVAL_SECONDS:
            payload = {
                "repo_id": repo_id,
                "container_id": os.environ.get("HOSTNAME", "unknown"),
                "written_at": datetime.datetime.utcnow().isoformat() + "Z",
            }
            canary.write_text(json.dumps(payload, sort_keys=True) + "\n")
            self._last_canary_at[repo_id] = now
        try:
            local_stat = canary.stat()
        except OSError:
            return {"ok": False, "error": "local canary file missing"}
        local_age = time.time() - local_stat.st_mtime
        try:
            if not self._ensure_api_token():
                return {"ok": None, "error": "Seafile API token unavailable"}
            data = self._api_request(
                f"/api2/repos/{repo_id}/file/detail/?p=/{urllib.parse.quote(CANARY_FILENAME)}"
            )
            server_size = int(data.get("size") or 0) if isinstance(data, dict) else 0
            server_mtime = int(data.get("mtime") or 0) if isinstance(data, dict) else 0
            size_matches = server_size == local_stat.st_size
            mtime_matches = not server_mtime or server_mtime + 2 >= int(local_stat.st_mtime)
            if (not size_matches or not mtime_matches) and local_age < CANARY_GRACE_SECONDS:
                return {
                    "ok": None,
                    "error": "canary upload pending",
                    "local_size": local_stat.st_size,
                    "server_size": server_size,
                    "local_mtime": int(local_stat.st_mtime),
                    "server_mtime": server_mtime,
                    "age_seconds": int(local_age),
                }
            return {
                "ok": size_matches and mtime_matches,
                "local_size": local_stat.st_size,
                "server_size": server_size,
                "local_mtime": int(local_stat.st_mtime),
                "server_mtime": server_mtime,
                "age_seconds": int(local_age),
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                if local_age < CANARY_GRACE_SECONDS:
                    return {
                        "ok": None,
                        "error": "canary upload pending",
                        "age_seconds": int(local_age),
                    }
                return {"ok": False, "error": "server canary file missing"}
            return {"ok": None, "error": f"server canary check failed: HTTP {exc.code}"}
        except Exception as exc:
            return {"ok": None, "error": str(exc)}

    def _alert_anomaly(self, repo_id: str, result: dict) -> dict:
        if not self.alert_webhook_url:
            return {"sent": False, "reason": "SEAF_ALERT_WEBHOOK_URL not configured"}

        cache = self._load_health_cache()
        alerts = cache.setdefault("_alerts", {})
        key = f"{repo_id}:{result.get('status')}:{result.get('reason')}"
        now = time.time()
        if now - float(alerts.get(key, 0) or 0) < ALERT_COOLDOWN_SECONDS:
            return {"sent": False, "reason": "alert cooldown active"}

        payload = json.dumps({
            "text": f"Seafile NAS sync anomaly for {repo_id}: {result.get('reason')}",
            "repo_id": repo_id,
            "status": result,
        }).encode()
        try:
            req = urllib.request.Request(
                self.alert_webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            alerts[key] = now
            self._save_health_cache(cache)
            return {"sent": True}
        except Exception as exc:
            logger.warning("Failed to send sync anomaly alert for %s: %s", repo_id, exc)
            return {"sent": False, "reason": str(exc)}

    def _verify_library(self, name: str, repo: Any, repo_state: str | None, daemon_health: dict | None = None) -> dict:
        repo_id = repo.id
        root = self._target_for_library_name(name)
        started_at = datetime.datetime.utcnow()
        result = {
            "checked_at": started_at.isoformat() + "Z",
            "status": "unknown",
            "reason": None,
            "client_head": None,
            "server_head": None,
            "daemon_health": daemon_health,
            "canary": None,
            "diagnostics": {},
            "alert": None,
        }
        issues = []
        try:
            client_head = self._local_repo_head(repo)
            server_head = self._server_repo_head(repo_id)
            result["client_head"] = client_head
            result["server_head"] = server_head
            if client_head and server_head and client_head != server_head and repo_state == "synchronized":
                issues.append("client synced commit differs from server head while repo reports synchronized")
            elif client_head is None or server_head is None:
                result["diagnostics"]["head_check"] = "commit head unavailable"

            if daemon_health and daemon_health.get("status") == "anomaly":
                issues.extend(daemon_health.get("issues") or ["daemon health anomaly"])

            result["canary"] = self._canary_status(repo_id, root)
            if result["canary"] and result["canary"].get("ok") is False:
                issues.append(result["canary"].get("error") or "canary did not round trip")

            if issues:
                result["status"] = "anomaly"
                result["reason"] = "; ".join(dict.fromkeys(issues))
                result["alert"] = self._alert_anomaly(repo_id, result)
            else:
                result["status"] = "healthy"
                result["reason"] = "commit head, inotify health, and canary checks passed"
        except Exception as exc:
            result["status"] = "unknown"
            result["reason"] = str(exc)
        cache = self._load_health_cache()
        cache[repo_id] = result
        self._save_health_cache(cache)
        self._verification_cache[repo_id] = result
        return result

    def _save_folder_size_cache(self, cache: dict) -> None:
        self.folder_size_cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.folder_size_cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, indent=2, sort_keys=True))
        tmp.replace(self.folder_size_cache_path)

    def _scan_tree_size(self, root: Path) -> dict:
        total_bytes = 0
        file_count = 0
        folder_count = 0
        errors = 0
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                folder_count += 1
                                stack.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                file_count += 1
                                total_bytes += entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            errors += 1
            except OSError:
                errors += 1
        return {
            "bytes": total_bytes,
            "files": file_count,
            "folders": folder_count,
            "errors": errors,
        }

    def _build_folder_size_cache(self) -> dict:
        source = self.source
        started_at = datetime.datetime.utcnow()
        cache = {
            "source_path": str(source),
            "source_label": os.environ.get("SEAF_SOURCE_PATH", str(source)),
            "started_at": started_at.isoformat() + "Z",
            "finished_at": None,
            "status": "running",
            "root": {"bytes": 0, "files": 0, "folders": 0, "errors": 0},
            "children": [],
        }
        self._save_folder_size_cache(cache)

        children = []
        if source.exists():
            entries = []
            try:
                with os.scandir(source) as scan:
                    for entry in scan:
                        try:
                            entries.append({
                                "name": entry.name,
                                "path": entry.path,
                                "is_dir": entry.is_dir(follow_symlinks=False),
                                "is_file": entry.is_file(follow_symlinks=False),
                                "size": entry.stat(follow_symlinks=False).st_size
                                if entry.is_file(follow_symlinks=False) else 0,
                            })
                        except OSError:
                            entries.append({
                                "name": entry.name,
                                "path": entry.path,
                                "is_dir": False,
                                "is_file": False,
                                "size": 0,
                                "errors": 1,
                            })
                entries.sort(key=lambda e: e["name"].lower())
            except OSError:
                entries = []
            for entry in entries:
                item = {
                    "name": entry["name"],
                    "path": entry["path"],
                    "type": "folder",
                    "bytes": 0,
                    "files": 0,
                    "folders": 0,
                    "errors": entry.get("errors", 0),
                }
                try:
                    if entry["is_dir"]:
                        item.update(self._scan_tree_size(Path(entry["path"])))
                        item["type"] = "folder"
                        item["folders"] += 1
                    elif entry["is_file"]:
                        item.update({"type": "file", "bytes": entry["size"], "files": 1})
                    else:
                        continue
                except OSError:
                    item["errors"] = 1
                children.append(item)
                for key in ("bytes", "files", "folders", "errors"):
                    cache["root"][key] += item.get(key, 0)
                cache["children"] = children
                cache["updated_child"] = entry["name"]
                self._save_folder_size_cache(cache)

        cache["children"] = sorted(children, key=lambda x: (-x.get("bytes", 0), x.get("name", "").lower()))
        cache["finished_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        cache["status"] = "complete"
        cache.pop("updated_child", None)
        self._save_folder_size_cache(cache)
        return cache

    def _refresh_folder_size_cache_async(self, force: bool = False) -> None:
        if self._folder_size_scan_running:
            return

        def _worker() -> None:
            with self._folder_size_scan_lock:
                self._folder_size_scan_running = True
                try:
                    logger.info("Scanning cached folder sizes for %s", self.source)
                    self._build_folder_size_cache()
                    logger.info("Folder-size cache scan complete")
                except Exception:
                    logger.exception("Folder-size cache scan failed")
                finally:
                    self._folder_size_scan_running = False

        cache = self._load_folder_size_cache()
        if not force and cache and cache.get("status") == "complete":
            return
        self._folder_size_scan_running = True
        threading.Thread(target=_worker, daemon=True, name="folder-size-scan").start()

    def _start_folder_size_scheduler(self) -> None:
        """Refresh recursive folder sizes once per night without blocking sync."""
        def _local_now() -> datetime.datetime:
            tz = datetime.timezone.utc
            if ZoneInfo is not None:
                try:
                    tz = ZoneInfo(FOLDER_SIZE_SCAN_TZ)
                except Exception:
                    pass
            return datetime.datetime.now(tz)

        def _loop() -> None:
            last_scan_date = None
            cache = self._load_folder_size_cache()
            finished_at = cache.get("finished_at") if cache else None
            if finished_at:
                try:
                    last_scan_date = datetime.datetime.fromisoformat(
                        finished_at.rstrip("Z")
                    ).date()
                except Exception:
                    pass
            while True:
                now = _local_now()
                if now.hour >= FOLDER_SIZE_SCAN_HOUR and last_scan_date != now.date():
                    self._refresh_folder_size_cache_async(force=True)
                    last_scan_date = now.date()
                time.sleep(300)

        threading.Thread(target=_loop, daemon=True, name="folder-size-scheduler").start()
        logger.info("Folder-size scheduler started: daily after %02d:00 %s",
                    FOLDER_SIZE_SCAN_HOUR, FOLDER_SIZE_SCAN_TZ)

    def _schedule_allows_sync(self, schedule: dict | None) -> bool:
        if not schedule or not schedule.get("enabled"):
            return True

        tz = datetime.timezone.utc
        if ZoneInfo is not None:
            try:
                tz = ZoneInfo(schedule.get("timezone") or "UTC")
            except Exception:
                pass
        now = datetime.datetime.now(tz)

        def minutes(value: str, fallback: str) -> int:
            try:
                hour, minute = value.split(":", 1)
                return int(hour) * 60 + int(minute)
            except Exception:
                hour, minute = fallback.split(":", 1)
                return int(hour) * 60 + int(minute)

        current = now.hour * 60 + now.minute
        today = now.weekday()
        yesterday = (today - 1) % 7

        def window_allows(window: dict) -> bool:
            if window.get("enabled") is False:
                return False
            days = set(window.get("days") or [])
            if not days:
                return False
            start = minutes(window.get("start", "00:00"), "00:00")
            end = minutes(window.get("end", "23:59"), "23:59")
            if start == end:
                return today in days
            if start < end:
                return today in days and start <= current < end
            return (today in days and current >= start) or (yesterday in days and current < end)

        windows = schedule.get("windows")
        if isinstance(windows, dict):
            return any(
                window_allows(window)
                for window in windows.values()
                if isinstance(window, dict)
            )

        # Backward compatibility for schedules saved before weekday/weekend
        # windows were split.
        return window_allows({
            "enabled": True,
            "days": schedule.get("days") or [],
            "start": schedule.get("start", "00:00"),
            "end": schedule.get("end", "23:59"),
        })

    def _apply_schedule(self, schedule: dict | None, library_uuid: str | None = None) -> None:
        if not hasattr(self, "rpc"):
            return
        value = "true" if self._schedule_allows_sync(schedule) else "false"
        for repo in self._repos_for_library(library_uuid):
            if str(repo.auto_sync).lower() != value:
                self.rpc.set_repo_property(repo.id, "auto-sync", value)

    def _dispatch_command(self, command: dict) -> dict:
        """Execute one queued seaf-cli command and return a result record.

        Never raises — the status reporter must keep running no matter what.
        """
        verb = command.get("verb", "")
        args = command.get("args") or {}
        result = {"id": command.get("id"), "verb": verb,
                  "ok": False, "output": "", "error": "",
                  "finished_at": datetime.datetime.utcnow().isoformat() + "Z"}
        try:
            if verb in ("pause", "resume"):
                # This client's RpcClient has no global enable/disable_auto_sync;
                # pausing is per-repo via the "auto-sync" property ("false"/"true").
                if not hasattr(self, "rpc"):
                    raise RuntimeError("daemon not running")
                value = "false" if verb == "pause" else "true"
                repos = self._repos_for_library(command.get("library_uuid"))
                if not repos:
                    raise RuntimeError("no synced library yet")
                for repo in repos:
                    self.rpc.set_repo_property(repo.id, "auto-sync", value)
                result.update(
                    ok=True,
                    output=("paused" if verb == "pause" else "resumed")
                    + f" {len(repos)} repo(s)",
                )

            elif verb in ("restart", "stop"):
                # Stop the daemon. watch() then exits and the container's
                # restart policy relaunches it (a lasting stop = stop the
                # container itself; see the panel's guidance).
                self._run_seaf(["stop"], timeout=30)
                result.update(ok=True,
                              output="daemon stopped; container will relaunch it")

            elif verb == "reinit":
                # Force a fresh client init on next start: drop the .ini/socket/pid
                # (synced data volume is untouched) then stop so the container
                # restarts and re-initializes. Libraries are re-cloned.
                for stale in (self.ini, self.socket,
                              self.seafile / "seafile-data" / "seafile.pid"):
                    try:
                        stale.unlink()
                    except OSError:
                        pass
                self._run_seaf(["stop"], timeout=30)
                result.update(ok=True,
                              output="re-initializing; libraries will be re-cloned")

            elif verb == "config_get":
                key = args.get("key", "")
                if not key:
                    raise ValueError("missing config key")
                ok, out = self._run_seaf(["config", "-k", key], timeout=10)
                result.update(ok=ok, output=out)

            elif verb == "config_set":
                key = args.get("key", "")
                value = str(args.get("value", ""))
                if not key:
                    raise ValueError("missing config key")
                ok, out = self._run_seaf(["config", "-k", key, "-v", value], timeout=10)
                self._refresh_config_cache()
                result.update(ok=ok, output=out or f"{key} = {value}")

            elif verb == "list":
                ok, out = self._run_seaf(["list"], timeout=30)
                result.update(ok=ok, output=out)

            elif verb == "list_remote":
                ok, out = self._run_seaf(
                    ["list-remote", *self._get_credential_args()], timeout=60)
                result.update(ok=ok, output=out)

            elif verb == "refresh_folder_sizes":
                self._refresh_folder_size_cache_async(force=True)
                result.update(ok=True, output="folder-size refresh started")

            elif verb in ("verify_now", "write_canary"):
                repos = self._repos_for_library(command.get("library_uuid"))
                if not repos:
                    raise RuntimeError("no synced library yet")
                messages = []
                daemon_health = self._daemon_health(self._daemon_pid())
                for repo in repos:
                    name = self._name_for_library_uuid(repo.id)
                    if verb == "write_canary":
                        self._last_canary_at[repo.id] = 0
                    state = None
                    task = self.rpc.get_repo_sync_task(repo.id) if hasattr(self, "rpc") else None
                    if task is not None:
                        state = getattr(task, "state", None)
                    verification = self._verify_library(name, repo, state, daemon_health)
                    messages.append(
                        f"{repo.name}: {verification.get('status')} - "
                        f"{verification.get('reason') or 'checked'}"
                    )
                result.update(ok=True, output="\n".join(messages))

            elif verb == "desync":
                worktree = args.get("worktree", "")
                if not worktree:
                    raise ValueError("missing worktree path")
                ok, out = self._run_seaf(["desync", "-d", worktree], timeout=30)
                result.update(ok=ok, output=out or f"desynced {worktree}")

            elif verb == "create":
                name = args.get("name", "")
                if not name:
                    raise ValueError("missing library name")
                desc = args.get("desc") or name
                cmd = ["create", *self._get_credential_args(), "-n", name, "-t", desc]
                if args.get("enc_password"):
                    cmd += ["-e", args["enc_password"]]
                ok, out = self._run_seaf(cmd, timeout=60)
                result.update(ok=ok, output=out)

            else:
                result["error"] = f"unknown verb: {verb}"
        except Exception as exc:
            result["error"] = str(exc)

        if not result["ok"] and not result["error"]:
            result["error"] = result.get("output") or "command failed"
        return result

    def _start_status_reporter(self, settings_url: str, token: str | None) -> None:
        """Start a daemon thread that POSTs sync status every 30 s, carries back
        any command results, and executes the next queued command."""
        status_url = settings_url.rstrip("/").rsplit("/api/settings", 1)[0] + "/api/status"
        self._pending_results: dict[str, list[dict]] = {}
        self._config_cache = None

        def _loop() -> None:
            while True:
                for _name, uuid in self._library_targets():
                    try:
                        payload_obj = self._collect_status(uuid)
                        pending = self._pending_results.get(uuid, [])
                        if pending:
                            payload_obj["command_results"] = pending
                        payload = json.dumps(payload_obj).encode()
                        headers = {"Content-Type": "application/json"}
                        if token:
                            headers["X-Status-Token"] = token
                        req = urllib.request.Request(
                            status_url, data=payload, headers=headers, method="POST"
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            body = json.loads(resp.read().decode())
                        # Results were delivered with this POST — clear them.
                        self._pending_results[uuid] = []
                        command = body.get("command")
                        if command:
                            logger.info("Executing queued command for %s: %s",
                                        uuid, command.get("verb"))
                            command["library_uuid"] = uuid
                            self._pending_results.setdefault(uuid, []).append(
                                self._dispatch_command(command)
                            )
                        elif "schedule" in body:
                            self._apply_schedule(body.get("schedule"), uuid)
                    except Exception:
                        pass  # best-effort; never crash the container
                time.sleep(STATUS_REPORT_INTERVAL_SECONDS)

        threading.Thread(target=_loop, daemon=True, name="status-reporter").start()
        logger.info("Status reporter started → %s", status_url)

    def healthcheck(self) -> int:
        tasks = self.rpc.get_clone_tasks()
        healthy = True
        for task in tasks:
            name = task.repo_name
            state = task.state

            if state == 'done':
                continue
            elif state == "fetch":
                tx_task = self.rpc.find_transfer_task(task.repo_id)
                percentage = 0 if tx_task.block_done == 0 else tx_task.block_done / tx_task.block_total * 100
                rate = 0 if tx_task.rate == 0 else tx_task.rate / 1024.0
                print(f"{name:<50s}\t{state:<20s}\t{percentage:<.1f}%, {rate:<.1f}KB/s")
            elif state == "error":
                healthy = False
                error = self.rpc.sync_error_id_to_str(task.error)
                print(f"{name:<50s}\t{state:<20s}\t{error}")
            else:
                print(f"{name:<50s}\t{state:<20s}")

        repos = self.rpc.get_repo_list(-1, -1)
        auto_sync_enabled = self.rpc.is_auto_sync_enabled()
        for repo in repos:
            name = repo.name

            if not auto_sync_enabled or not repo.auto_sync:
                print(f"{name:<50s}\t{'auto sync disabled':<20s}")
                continue

            task = self.rpc.get_repo_sync_task(repo.id)
            if task is None:
                print(f"{name:<50s}\t{'waiting for sync':<20s}")
                continue

            state = task.state
            if state in ['uploading', 'downloading']:
                tx_task = self.rpc.find_transfer_task(repo.id)
                if tx_task.rt_state == "data":
                    state += " files"
                    percentage = 0 if tx_task.block_done == 0 else tx_task.block_done / tx_task.block_total * 100
                    rate = 0 if tx_task.rate == 0 else tx_task.rate / 1024.0
                    print(f"{name:<50s}\t{state:<20s}\t{percentage:<.1f}%, {rate:<.1f}KB/s")
                elif tx_task.rt_state == "fs":
                    state += " files list"
                    percentage = 0 if tx_task.fs_objects_done == 0 else tx_task.fs_objects_done / tx_task.fs_objects_total * 100
                    print(f"{name:<50s}\t{state:<20s}\t{percentage:<.1f}%")
            elif state == 'error':
                healthy = False
                error = self.rpc.sync_error_id_to_str(task.error)
                print(f"{name:<50s}\t{state:<20s}\t{error}")
            else:
                print(f"{name:<50s}\t{state:<20s}")

        return 0 if healthy else 1


debug = get_configuration("DEBUG", False)
level = logging.INFO
fmt = "%(asctime)s - %(levelname)s - %(message)s"
if debug:
    level = logging.DEBUG
    fmt = "%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s"
logging.basicConfig(format=fmt, level=level)
logger = logging.getLogger()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="", description="", epilog="")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()

    if args.healthcheck:
        logger.disabled = True

    try:
        client = Client()
    except BadConfiguration as e:
        logger.error(f"Bad configuration: {e}")
        sys.exit(1)

    if args.healthcheck:
        if not hasattr(client, "rpc"):
            print("seaf-daemon socket not found — daemon is not running")
            sys.exit(1)
        sys.exit(client.healthcheck())

    def _handle_stop(signum, frame):
        logger.info("Received signal — stopping seaf-daemon cleanly")
        subprocess.run(["seaf-cli", "stop"], timeout=30)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    client.initialize()
    client.configure()
    client.synchronize()

    settings_url = get_configuration("SEAF_SETTINGS_URL", None)
    status_token = get_configuration("SEAF_STATUS_TOKEN", None)
    if settings_url:
        client._start_status_reporter(settings_url, status_token)
    client._start_folder_size_scheduler()

    client.watch()
