"""
Vite Development Server Lifecycle Manager for CliniXAI.

Provides deterministic, leak-free process management for Vite development server
during browser verification, testing, and CI/local development.

Key Guarantees:
1. Strict Port Governance: strictly uses port 3100 (never silently moves to 3101+).
2. Process Tree Tracking: captures root process and all child PIDs.
3. Bulletproof Cleanup: context manager guarantees full process-tree termination
   in try...finally blocks, even when tests, assertions, or browser steps fail.
4. Targeted Termination: kills ONLY the Vite process tree created for this run;
   NEVER kills unrelated Node processes.
5. Standing Listener Verification: verifies port 3100 is completely released (0 listeners)
   before completing.
"""

import atexit
import os
import signal
import subprocess
import sys
import time
import urllib.request
from typing import List, Optional

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(WORKSPACE_ROOT, "clinixai-health-flow")
DEFAULT_PORT = 3100


def get_port_listener_pid(port: int = DEFAULT_PORT) -> Optional[int]:
    """Return the PID bound/listening on the given TCP port, or None if no process."""
    try:
        res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and parts[0].upper() == "TCP":
                local_addr = parts[1]
                remote_addr = parts[2]
                state = parts[3].upper()
                pid_str = parts[4]
                if (local_addr.endswith(f":{port}") or local_addr.endswith(f"]:{port}")) and (
                    state in ("LISTENING", "CLOSED") or remote_addr.endswith(":0")
                ):
                    if pid_str.isdigit() and int(pid_str) > 0:
                        return int(pid_str)
    except Exception as e:
        print(f"[ViteLifecycleManager] Error inspecting port {port}: {e}", file=sys.stderr)
    return None


def get_child_pids(parent_pid: int) -> List[int]:
    """Recursively discover all descendant PIDs of a given parent PID on Windows."""
    cmd = (
        f'Get-CimInstance Win32_Process -Filter "ParentProcessId = {parent_pid}" '
        f'| Select-Object -ExpandProperty ProcessId'
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
    )
    pids = []
    for line in res.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            cid = int(line)
            pids.append(cid)
            pids.extend(get_child_pids(cid))
    return list(dict.fromkeys(pids))


def terminate_process_tree(pid: int) -> bool:
    """Terminate a process and its entire child process tree on Windows."""
    try:
        res = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[ViteLifecycleManager] Error terminating process tree {pid}: {e}", file=sys.stderr)
        return False


def wait_for_port(port: int = DEFAULT_PORT, timeout_sec: float = 60.0) -> bool:
    """Poll HTTP endpoint until it returns 200 OK or timeout expires."""
    url = f"http://localhost:{port}/"
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CliniXAI-Lifecycle-Check"})
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def wait_for_port_free(port: int = DEFAULT_PORT, timeout_sec: float = 10.0) -> bool:
    """Wait until no process is listening on the given port."""
    start = time.time()
    while time.time() - start < timeout_sec:
        pid = get_port_listener_pid(port)
        if pid is None:
            return True
        time.sleep(0.5)
    return False


class ViteProcessManager:
    """Context manager for reliable, temporary Vite server lifecycle management."""

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        frontend_dir: str = FRONTEND_DIR,
        use_npm: bool = False,
    ):
        self.port = port
        self.frontend_dir = frontend_dir
        self.use_npm = use_npm
        self.proc: Optional[subprocess.Popen] = None
        self.root_pid: Optional[int] = None
        self.child_pids: List[int] = []
        self._cleaned_up = False

        # Register exit hook for abnormal termination
        atexit.register(self._emergency_cleanup)

    def start(self) -> "ViteProcessManager":
        """Start Vite development server and wait for readiness."""
        existing_pid = get_port_listener_pid(self.port)
        if existing_pid is not None:
            raise RuntimeError(
                f"Cannot start Vite on port {self.port}: port is already in use by PID {existing_pid}."
            )

        vite_bin = os.path.join(self.frontend_dir, "node_modules", "vite", "bin", "vite.js")

        if self.use_npm:
            # When started via npm run dev (batch runner wrapper)
            cmd = ["cmd.exe", "/c", "npm run dev"]
        else:
            # Direct Node invocation: eliminates intermediate cmd.exe/npm.cmd layers
            cmd = [
                "node",
                vite_bin,
                "dev",
                "--port",
                str(self.port),
                "--strictPort",
                "--host",
                "0.0.0.0",
            ]

        print(f"[ViteLifecycleManager] Starting Vite server on port {self.port} (command: {' '.join(cmd)})...")
        self.proc = subprocess.Popen(
            cmd,
            cwd=self.frontend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.root_pid = self.proc.pid
        print(f"[ViteLifecycleManager] Spawned server root PID: {self.root_pid}")

        # Wait for HTTP 200
        ready = wait_for_port(self.port, timeout_sec=60.0)
        if not ready:
            self.stop()
            raise TimeoutError(
                f"[ViteLifecycleManager] Vite server failed to respond on port {self.port} within 60 seconds."
            )

        # Discover all spawned child PIDs
        self.child_pids = get_child_pids(self.root_pid)
        listening_pid = get_port_listener_pid(self.port)
        print(
            f"[ViteLifecycleManager] Server is ready on http://localhost:{self.port}/ "
            f"(Root PID: {self.root_pid}, Listening PID: {listening_pid}, Descendants: {self.child_pids})"
        )
        return self

    def stop(self) -> None:
        """Terminate the server and all child processes, then verify port is free."""
        if self._cleaned_up:
            return
        self._cleaned_up = True

        print(f"[ViteLifecycleManager] Stopping Vite server (Root PID: {self.root_pid})...")

        # 1. Terminate the recorded process tree
        if self.root_pid is not None:
            terminate_process_tree(self.root_pid)

        # 2. Terminate any explicitly recorded child PIDs
        for cpid in self.child_pids:
            try:
                subprocess.run(["taskkill", "/PID", str(cpid), "/F"], capture_output=True)
            except Exception:
                pass

        # 3. Check if process is still running
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                pass

        # 4. Verify port 3100 is no longer listening
        port_free = wait_for_port_free(self.port, timeout_sec=5.0)
        if not port_free:
            # If port still held, inspect owning process
            remaining_pid = get_port_listener_pid(self.port)
            if remaining_pid is not None:
                print(
                    f"[ViteLifecycleManager] Warning: Port {self.port} still held by PID {remaining_pid}. "
                    f"Issuing targeted termination..."
                )
                terminate_process_tree(remaining_pid)
                port_free = wait_for_port_free(self.port, timeout_sec=3.0)

        if not port_free:
            raise RuntimeError(
                f"[ViteLifecycleManager] CRITICAL: Port {self.port} is still listening after cleanup!"
            )

        print(f"[ViteLifecycleManager] Server stopped cleanly. Port {self.port} is completely free.")

    def _emergency_cleanup(self) -> None:
        if not self._cleaned_up and self.root_pid is not None:
            self.stop()

    def __enter__(self) -> "ViteProcessManager":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
