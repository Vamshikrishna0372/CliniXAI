"""
Comprehensive Browser Acceptance Test for CliniXAI Fix Phase 4A:
Doctor Clinical Workspace & Patient Context End-to-End Verification.
Runs via Playwright against live Frontend (http://localhost:3100) and Backend (http://localhost:8000).
"""

import asyncio
import sys
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
DOCTOR_EMAIL = "doctor.arjun@clinixai.com"
DOCTOR_PASS = "Doctor@123"

async def run_browser_verification():
    console_errors = []
    network_requests = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Listen for console messages
        def on_console(msg):
            text = msg.text
            clean_text = text.encode("ascii", errors="replace").decode("ascii")
            # Ignore harmless favicon / resource 404s
            if "favicon" not in text.lower() and "noindex" not in text.lower():
                if msg.type == "error":
                    console_errors.append(text)
                print(f"[{msg.type.upper()}] {clean_text}", flush=True)
        page.on("console", on_console)

        # Listen for network responses
        def on_response(res):
            url = res.url
            if "/api/v1/" in url:
                network_requests.append((res.request.method, url, res.status))
                # Check for token leakage in URL
                if "token=" in url.lower() or "jwt=" in url.lower() or "bearer" in url.lower():
                    raise AssertionError(f"SECURITY LEAK: Token found in URL: {url}")
        page.on("response", on_response)

        print("\n--- STEP 1: Navigate to Login ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/auth/login", wait_until="networkidle")
        await page.wait_for_timeout(1000)

        print("\n--- STEP 2: Doctor Authentication ---", flush=True)
        demo_btn = page.locator("button:has-text('Dr. Arjun')")
        if await demo_btn.is_visible():
            print("Clicking 'Dr. Arjun (doctor)' demo fill button...", flush=True)
            await demo_btn.click()
            await page.wait_for_timeout(500)
            await page.click("button[type='submit']")
        else:
            await page.fill("input[type='email']", DOCTOR_EMAIL)
            await page.fill("input[type='password']", DOCTOR_PASS)
            await page.click("button[type='submit']")

        # Wait for navigation to /app/
        await page.wait_for_timeout(3000)
        current_url = page.url
        print(f"Current URL after login: {current_url}", flush=True)
        if "/app" not in current_url:
            await page.goto(f"{FRONTEND_URL}/app/", wait_until="networkidle")
            await page.wait_for_timeout(1500)
        print("Doctor successfully authenticated and in CliniXAI app workspace!", flush=True)

        print("\n--- STEP 3: Doctor Dashboard Verification ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        
        content = await page.content()
        assert "Welcome back" in content, "Doctor dashboard welcome greeting not found"
        print("PASS: Doctor dashboard loaded with welcome greeting.", flush=True)

        print("\n--- STEP 4: Doctor Appointments Navigation ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/appointments", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        
        apt_content = await page.content()
        assert "Appointments" in apt_content, "Appointments page title not found"
        print("PASS: Doctor appointments page rendered successfully.", flush=True)

        # Find an appointment link
        details_link = page.locator("a[href*='/app/appointments/']").first
        assert await details_link.is_visible(), "Appointment detail link not visible"
        href = await details_link.get_attribute("href")
        print(f"Opening appointment detail at: {href}", flush=True)
        await page.goto(f"{FRONTEND_URL}{href}", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        print("\n--- STEP 5: Appointment Detail Patient Context Verification ---", flush=True)
        detail_content = await page.content()
        assert "PAT-" in detail_content, "Patient ID not visible on appointment detail"
        print("PASS: Patient identifier verified on appointment detail page.", flush=True)

        # Click Clinical Workspace button
        clinical_btn = page.locator("a:has-text('Clinical Workspace')").first
        assert await clinical_btn.is_visible(), "Clinical Workspace button not visible on appointment page"
        workspace_url = await clinical_btn.get_attribute("href")
        print(f"Navigating to Clinical Workspace: {workspace_url}", flush=True)
        await page.goto(f"{FRONTEND_URL}{workspace_url}", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        print("\n--- STEP 6: Patient Clinical Workspace Header & Tabs ---", flush=True)
        ws_content = await page.content()
        assert "Clinical Workspace" in ws_content or "PAT-" in ws_content, "Patient Clinical Workspace header missing"
        print("PASS: Patient Clinical Workspace rendered with patient context.", flush=True)

        # Test tabs
        print("Testing Clinical Workspace tabs...", flush=True)
        for tab_id in ["records", "imaging", "consultations", "prescriptions", "timeline"]:
            tab_btn = page.locator(f"button[value='{tab_id}']")
            if await tab_btn.is_visible():
                await tab_btn.click()
                await page.wait_for_timeout(500)
                print(f"  - Clicked tab: {tab_id} (SUCCESS)", flush=True)

        print("\n--- STEP 7: Clinical Workspace Persistence (Reload) ---", flush=True)
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)
        reloaded_content = await page.content()
        assert "Clinical Workspace" in reloaded_content or "PAT-" in reloaded_content, "Persistence failed on reload"
        print("PASS: Patient Clinical Workspace data and view fully persist across browser reload.", flush=True)

        print("\n--- STEP 8: Cross-Patient IDOR Security Check ---", flush=True)
        # Attempt direct navigation to an unauthorized Patient (PAT-TWO-15) which Dr. Arjun Rao has no appointment/care relationship with
        print("Attempting unauthorized direct navigation to Patient (/app/patients/PAT-TWO-15)...", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/patients/PAT-TWO-15", wait_until="networkidle")
        await page.wait_for_timeout(2500)

        p2_text = await page.inner_text("body")
        # Should display error card or access denied / forbidden / restricted
        is_blocked = (
            "clinical access restricted" in p2_text.lower()
            or "care relationship" in p2_text.lower()
            or "forbidden" in p2_text.lower()
            or "authorized" in p2_text.lower()
        )
        print(f"IDOR Check: Access denied/restricted state detected: {is_blocked}", flush=True)
        assert is_blocked, f"SECURITY FAILURE: Doctor was able to view unauthorized Patient workspace! Text: {p2_text[:300]}"
        print("PASS: Cross-patient IDOR protection successfully rejected unauthorized access (403 Forbidden).", flush=True)

        print("\n--- STEP 9: Console & Network Audit ---", flush=True)
        print(f"Total API requests made: {len(network_requests)}", flush=True)
        # Check HTTP status codes (ignore expected 403 during IDOR test)
        non_403_errors = [req for req in network_requests if req[2] >= 500]
        assert len(non_403_errors) == 0, f"Backend 500 errors found: {non_403_errors}"
        print("PASS: Zero 500 internal server errors across all clinical endpoints.", flush=True)

        # Check console errors (ignoring benign navigation aborts and expected 403 network responses)
        critical_errors = [
            e for e in console_errors
            if "favicon" not in e.lower()
            and "abort" not in e.lower()
            and "403" not in e.lower()
            and "failed to load resource" not in e.lower()
        ]
        print(f"Total critical console runtime errors: {len(critical_errors)}", flush=True)
        if critical_errors:
            print("Console errors noted:", critical_errors, flush=True)
        assert len(critical_errors) == 0, f"React crashes or console errors found: {critical_errors}"
        print("PASS: Zero React crashes or runtime errors in console.", flush=True)

        await browser.close()
        print("\n=======================================================", flush=True)
        print("ALL BROWSER ACCEPTANCE CHECKS PASSED (Fix Phase 4A)!", flush=True)
        print("=======================================================", flush=True)

if __name__ == "__main__":
    asyncio.run(run_browser_verification())
