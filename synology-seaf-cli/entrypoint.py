#!/usr/bin/env python3

from pathlib import Path
from typing import Any
import argparse
import logging
import os
import signal
import subprocess
import sys
import time

import seafile


DAEMON_START_TIMEOUT = 60  # seconds to wait for socket after seaf-cli start
INIT_TIMEOUT = 30          # seconds to wait for .ini after seaf-cli init


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

    def synchronize(self):
        core = [*self.binary, "sync", *self._get_credential_args()]
        for name, configuration in self.libraries.items():
            uuid = configuration["uuid"]

            repository = self.rpc.get_repo(uuid)
            if repository is not None:
                logger.info(f"Library {name} is already synced.")
                continue

            command = core + ["-l", uuid]

            if "password" in configuration:
                command += ["-e", configuration["password"]]

            target = self.target if name == "_" else self.target.joinpath(name)
            target.mkdir(parents=True, exist_ok=True)
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

            result = subprocess.run(command)
            if result.returncode != 0:
                logger.error(f"`seaf-cli sync` for library {name!r} failed (exit {result.returncode})")

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
            time.sleep(10)

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
    client.watch()
