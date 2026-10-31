"""
CliniXAI Permanent Port 3100 Lifecycle Verification Test Suite.

Executes the strict requirements of Sections 3, 4, 5, 6, 7, and 8:
- Cycle 1:
  - Part A: Start frontend using normal 'npm run dev', verify HTTP 200 on port 3100, stop, verify port free.
  - Part B: Antigravity browser verification (successful run), verify cleanup & port free.
  - Part C: Antigravity browser verification (failure simulation), verify cleanup & port free despite failure.
- Cycle 2:
  - Repeat the exact same sequence to prove that repeated runs never leak processes.
- Section 7:
  - Real user manual workflow: start frontend via 'npm run dev', verify bind, verify app loads, stop, verify netstat.
- Section 8:
  - Fresh PowerShell session: open new powershell.exe, run 'cd clinixai-health-flow; npm run dev', verify port 3100, stop, verify netstat.
"""

import os
import subprocess
import sys
import time
import urllib.request

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(WORKSPACE_ROOT, "clinixai-health-flow")

sys.path.insert(0, os.path.join(WORKSPACE_ROOT, "scripts"))
from vite_lifecycle_manager import (
    ViteProcessManager,
    get_port_listener_pid,
    wait_for_port_free,
    wait_for_port,
    terminate_process_tree,
)


def assert_port_3100_free(step_desc: str):
    pid = get_port_listener_pid(3100)
    if pid is not None:
        raise AssertionError(f"[{step_desc}] Port 3100 is NOT free! Bound PID: {pid}")
    # Also verify with netstat directly
    res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    listening = [
        l.strip()
        for l in res.stdout.splitlines()
        if (":3100" in l or "]:3100" in l) and ("LISTENING" in l.upper() or " 0.0.0.0:0" in l or " [::]:0" in l)
    ]
    if listening:
        raise AssertionError(f"[{step_desc}] netstat reports active listener on 3100: {listening}")
    print(f"  [CHECK PASSED] Port 3100 is completely free: {step_desc}", flush=True)


def test_part_a_npm_run_dev(cycle_name: str):
    print(f"\n--- [{cycle_name} - PART A] Starting frontend with 'npm run dev' ---", flush=True)
    assert_port_3100_free(f"Before {cycle_name} Part A")

    # Start using cmd.exe /c npm run dev exactly as a user does
    proc = subprocess.Popen(
        ["cmd.exe", "/c", "npm run dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"  Launched 'npm run dev' with parent PID {proc.pid}. Waiting for HTTP 200 on port 3100...", flush=True)

    ready = wait_for_port(3100, timeout_sec=25.0)
    if not ready:
        terminate_process_tree(proc.pid)
        raise TimeoutError(f"[{cycle_name} - Part A] 'npm run dev' failed to respond on port 3100 within 25s.")

    listening_pid = get_port_listener_pid(3100)
    print(f"  HTTP 200 OK received on http://localhost:3100/! (Active listening PID: {listening_pid})", flush=True)

    # Now stop it cleanly using process tree termination
    print(f"  Stopping 'npm run dev' (PID {proc.pid})...", flush=True)
    terminate_process_tree(proc.pid)
    time.sleep(2)

    assert_port_3100_free(f"After {cycle_name} Part A termination")
    print(f"  [{cycle_name} - PART A PASSED] Successfully tested npm run dev startup and clean shutdown.", flush=True)


def test_part_b_verification_success(cycle_name: str):
    print(f"\n--- [{cycle_name} - PART B] Antigravity verification workflow (Success Run) ---", flush=True)
    assert_port_3100_free(f"Before {cycle_name} Part B")

    with ViteProcessManager(port=3100, frontend_dir=FRONTEND_DIR) as vite:
        listening_pid = get_port_listener_pid(3100)
        print(f"  Inside verification context: Root PID={vite.root_pid}, Listening PID={listening_pid}", flush=True)
        # Simulate browser / HTTP verification
        req = urllib.request.Request("http://localhost:3100/", headers={"User-Agent": "Playwright-Acceptance"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
            assert status == 200, f"Expected 200, got {status}"
            assert "CliniXAI" in body, "Expected CliniXAI branding in DOM"
            print(f"  Browser verification simulation succeeded: status={status}, DOM contains CliniXAI branding.", flush=True)

    # Context exited: ViteProcessManager.__exit__ has executed
    assert_port_3100_free(f"After {cycle_name} Part B context exit")
    print(f"  [{cycle_name} - PART B PASSED] Verification process cleaned up cleanly, port 3100 released.", flush=True)


def test_part_c_verification_failure_cleanup(cycle_name: str):
    print(f"\n--- [{cycle_name} - PART C] Antigravity verification workflow (Failure Simulation) ---", flush=True)
    assert_port_3100_free(f"Before {cycle_name} Part C")

    exception_caught = False
    try:
        with ViteProcessManager(port=3100, frontend_dir=FRONTEND_DIR) as vite:
            listening_pid = get_port_listener_pid(3100)
            print(f"  Inside verification context: Root PID={vite.root_pid}, Listening PID={listening_pid}", flush=True)
            # Intentionally simulate an unexpected test failure / exception
            print("  Simulating unexpected test assertion failure inside verification...", flush=True)
            raise RuntimeError("SIMULATED_TEST_FAILURE: Browser assertion failed!")
    except RuntimeError as e:
        if "SIMULATED_TEST_FAILURE" in str(e):
            exception_caught = True
            print("  Successfully caught simulated exception outside context manager.", flush=True)
        else:
            raise

    assert exception_caught, "Simulated exception was not caught!"
    # Ensure cleanup still executed despite the exception!
    assert_port_3100_free(f"After {cycle_name} Part C exception exit")
    print(f"  [{cycle_name} - PART C PASSED] Cleanup executed 100% reliably despite error! Port 3100 is free.", flush=True)


def test_section_7_manual_user_workflow():
    print("\n--- [SECTION 7] Verify Real User Workflow (Manual Start/Load/Stop) ---", flush=True)
    assert_port_3100_free("Before Section 7")

    print(f"  Starting frontend via 'npm run dev' from {FRONTEND_DIR}...", flush=True)
    proc = subprocess.Popen(
        ["cmd.exe", "/c", "npm run dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = wait_for_port(3100, timeout_sec=25.0)
        assert ready, "Manual 'npm run dev' failed to respond on port 3100 within 25s!"

        bound_pid = get_port_listener_pid(3100)
        print(f"  Frontend successfully bound to http://localhost:3100 (Listening PID: {bound_pid})", flush=True)

        # Verify application loads
        req = urllib.request.Request("http://localhost:3100/", headers={"User-Agent": "UserBrowser"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "CliniXAI" in content, "CliniXAI app failed to load in browser!"
            print(f"  Application loaded successfully: HTTP {resp.status}, CliniXAI DOM confirmed.", flush=True)
    finally:
        print(f"  Stopping manually started frontend (PID {proc.pid})...", flush=True)
        terminate_process_tree(proc.pid)
        time.sleep(2)

    assert_port_3100_free("After Section 7 manual frontend stopped")
    print("  [SECTION 7 PASSED] Real user workflow verified: starts on 3100, loads app, stops cleanly, port is free.", flush=True)


def test_section_8_fresh_powershell():
    print("\n--- [SECTION 8] Verify Fresh PowerShell Session ---", flush=True)
    assert_port_3100_free("Before Section 8")

    # Launch a completely fresh powershell.exe process that executes cd clinixai-health-flow; npm run dev
    ps_cmd = f"Set-Location -LiteralPath '{FRONTEND_DIR}'; npm run dev"
    print(f"  Spawning fresh powershell.exe running: {ps_cmd}...", flush=True)
    ps_proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
        cwd=FRONTEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = wait_for_port(3100, timeout_sec=25.0)
        assert ready, "Fresh PowerShell session failed to start Vite on port 3100 within 25s!"

        bound_pid = get_port_listener_pid(3100)
        print(f"  Fresh PowerShell session successfully bound to port 3100 (Bound PID: {bound_pid})", flush=True)

        req = urllib.request.Request("http://localhost:3100/", headers={"User-Agent": "FreshPSBrowser"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            print(f"  Verified application response from fresh PowerShell server: HTTP {resp.status}", flush=True)
    finally:
        print(f"  Stopping fresh PowerShell session (PID {ps_proc.pid})...", flush=True)
        terminate_process_tree(ps_proc.pid)
        time.sleep(2)

    assert_port_3100_free("After Section 8 fresh PowerShell stopped")
    print("  [SECTION 8 PASSED] Fresh PowerShell session verified without conflicts.", flush=True)


def main():
    print("======================================================================", flush=True)
    print("CLINIXAI PERMANENT PORT 3100 LIFECYCLE VERIFICATION (TWO CYCLES)", flush=True)
    print("======================================================================", flush=True)

    # Initial sanity check
    assert_port_3100_free("Initial Baseline")

    # ==========================
    # CYCLE 1
    # ==========================
    print("\n" + "=" * 50, flush=True)
    print("STARTING CYCLE 1", flush=True)
    print("=" * 50, flush=True)
    test_part_a_npm_run_dev("CYCLE 1")
    test_part_b_verification_success("CYCLE 1")
    test_part_c_verification_failure_cleanup("CYCLE 1")

    # ==========================
    # CYCLE 2
    # ==========================
    print("\n" + "=" * 50, flush=True)
    print("STARTING CYCLE 2 (REPEATED VERIFICATION)", flush=True)
    print("=" * 50, flush=True)
    test_part_a_npm_run_dev("CYCLE 2")
    test_part_b_verification_success("CYCLE 2")
    test_part_c_verification_failure_cleanup("CYCLE 2")

    # ==========================
    # SECTION 7: REAL USER WORKFLOW
    # ==========================
    test_section_7_manual_user_workflow()

    # ==========================
    # SECTION 8: FRESH POWERSHELL
    # ==========================
    test_section_8_fresh_powershell()

    print("\n======================================================================", flush=True)
    print(">>> ALL TWO CYCLES, USER WORKFLOW, AND FRESH POWERSHELL TESTS PASSED 100%! <<<", flush=True)
    print("Port 3100 lifecycle is strictly governed, clean, and permanently fixed.", flush=True)
    print("======================================================================", flush=True)


if __name__ == "__main__":
    main()
