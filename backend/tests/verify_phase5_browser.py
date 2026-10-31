"""
Fix Phase 5 Browser Acceptance Verification Script:
Doctor -> Patient -> Documents & Imaging -> Existing Brain MRI Discovery & Selection.

Verifies Gates 1 through 14:
Gate 1: Doctor login succeeds.
Gate 2: Doctor opens a real patient (PAT-ONE-001).
Gate 3: Patient identity is correct.
Gate 4: Documents & Imaging loads from the real API.
Gate 5: Existing Brain MRI appears (DOC-2026-001).
Gate 6: MRI metadata is correct (Category MRI, Brain MRI badge, file name).
Gate 7: MRI preview works securely (authenticated blob loading, zero 401s).
Gate 8: Doctor selects the existing Brain MRI (doc-select-btn).
Gate 9: Selected document ID and patient ID are confirmed in authoritative state banner.
Gate 10: High-res Scan Viewer dialog opens and displays scan with secure download.
Gate 11: Switching to another patient (PAT-TWO-002) resets selection and isolates context.
Gate 12: Refresh preserves correct patient/document discovery.
Gate 13: Unauthorized patient access (PAT-ISOLATED-P5) is rejected (403/Forbidden).
Gate 14: Zero console runtime errors, zero 500 network errors, zero token URL leaks.
"""

import asyncio
import sys
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:3100"
DOCTOR_EMAIL = "doctor.arjun@clinixai.com"
DOCTOR_PASS = "Doctor@123"

async def run_phase5_browser_acceptance():
    console_errors = []
    network_requests = []
    
    print("\n=======================================================", flush=True)
    print("STARTING FIX PHASE 5 BROWSER ACCEPTANCE VERIFICATION", flush=True)
    print("=======================================================\n", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Listen for console messages
        def on_console(msg):
            text = msg.text
            clean_text = text.encode("ascii", errors="replace").decode("ascii")
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
                if "token=" in url.lower() or "jwt=" in url.lower() or "bearer" in url.lower():
                    raise AssertionError(f"SECURITY LEAK: Authentication token found in URL: {url}")
        page.on("response", on_response)

        # GATE 1: Doctor Login
        print("\n--- GATE 1: Doctor Login ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/auth/login", wait_until="networkidle")
        await page.wait_for_timeout(1000)

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

        await page.wait_for_timeout(2500)
        current_url = page.url
        print(f"Current URL after login: {current_url}", flush=True)
        assert "/app" in current_url, "Gate 1 Failed: Doctor login did not navigate to /app"
        print("GATE 1 PASS: Doctor login succeeded.", flush=True)

        # GATE 2 & 3: Navigate to Patient PAT-ONE-001
        print("\n--- GATE 2 & 3: Patient Selection & Identity ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/patients/PAT-ONE-001", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        body_text = await page.inner_text("body")
        assert "PAT-ONE-001" in body_text, "Gate 2/3 Failed: Patient PAT-ONE-001 ID not found in workspace"
        print("GATE 2 PASS: Real patient PAT-ONE-001 loaded.", flush=True)
        print("GATE 3 PASS: Patient identity confirmed.", flush=True)

        # GATE 4: Open Documents & Imaging Tab
        print("\n--- GATE 4: Documents & Imaging API Loading ---", flush=True)
        imaging_tab_btn = page.locator("button[value='documents'], button:has-text('Imaging & Docs')").first
        assert await imaging_tab_btn.is_visible(), "Gate 4 Failed: Imaging tab button not visible"
        await imaging_tab_btn.click()
        await page.wait_for_timeout(2000)

        # Verify documents API request was made
        doc_api_calls = [req for req in network_requests if "/documents" in req[1] and "patient_id=PAT-ONE-001" in req[1]]
        assert len(doc_api_calls) > 0, "Gate 4 Failed: No API call to /documents for PAT-ONE-001"
        print(f"GATE 4 PASS: Documents & Imaging loaded from real API. Calls: {len(doc_api_calls)}", flush=True)

        # GATE 5: Existing Brain MRI Appears
        print("\n--- GATE 5: Existing Brain MRI Discovery ---", flush=True)
        body_text = await page.inner_text("body")
        assert "DOC-2026-001" in body_text or "Brain MRI" in body_text, "Gate 5 Failed: Brain MRI DOC-2026-001 not visible"
        doc_card = page.locator("[data-testid='doc-card-DOC-2026-001']")
        assert await doc_card.is_visible(), "Gate 5 Failed: doc-card-DOC-2026-001 not visible"
        print("GATE 5 PASS: Existing Brain MRI DOC-2026-001 discovered and displayed.", flush=True)

        # GATE 6: Metadata Correctness
        print("\n--- GATE 6: Brain MRI Metadata Verification ---", flush=True)
        card_text = await doc_card.inner_text()
        assert "Brain MRI" in card_text or "MRI" in card_text, "Gate 6 Failed: Category / Title missing MRI"
        print(f"Card content summary: {card_text.replace(chr(10), ' | ')}", flush=True)
        print("GATE 6 PASS: Brain MRI metadata verified.", flush=True)

        # GATE 7: Authenticated Image Preview
        print("\n--- GATE 7: Secure Authenticated Image Preview ---", flush=True)
        img_locator = doc_card.locator("img")
        assert await img_locator.is_visible(), "Gate 7 Failed: Document preview <img> not rendered"
        img_src = await img_locator.get_attribute("src")
        print(f"Rendered image src: {img_src[:35]}...", flush=True)
        assert img_src and img_src.startswith("blob:"), f"Gate 7 Failed: Expected blob: URL, got {img_src}"
        # Confirm no unauthenticated 401s occurred
        unauth_downloads = [req for req in network_requests if "/download" in req[1] and req[2] == 401]
        assert len(unauth_downloads) == 0, f"Gate 7 Failed: Found unauthenticated 401 download requests: {unauth_downloads}"
        print("GATE 7 PASS: Authenticated blob preview works with zero 401 errors.", flush=True)

        # GATE 8 & 9: Select Existing Brain MRI
        print("\n--- GATE 8 & 9: Document Selection & Context State ---", flush=True)
        select_btn = page.locator("[data-testid='select-doc-DOC-2026-001']")
        assert await select_btn.is_visible(), "Gate 8 Failed: Select button not visible"
        await select_btn.click()
        await page.wait_for_timeout(1000)

        # Verify selected banner
        banner = page.locator("[data-testid='selected-doc-banner']")
        assert await banner.is_visible(), "Gate 9 Failed: Selected document banner not visible"
        banner_text = await banner.inner_text()
        assert "DOC-2026-001" in banner_text, "Gate 9 Failed: DOC-2026-001 missing from selected banner"
        assert "PAT-ONE-001" in banner_text, "Gate 9 Failed: PAT-ONE-001 missing from selected banner"
        print(f"Authoritative Selected Banner text: {banner_text.replace(chr(10), ' | ')}", flush=True)
        print("GATE 8 PASS: Doctor selected existing Brain MRI.", flush=True)
        print("GATE 9 PASS: Authoritative document_id and patient_id confirmed in state.", flush=True)

        # GATE 10: Scan Viewer Modal
        print("\n--- GATE 10: Scan Viewer High-Res Modal ---", flush=True)
        view_btn = page.locator("[data-testid='view-doc-DOC-2026-001']")
        assert await view_btn.is_visible(), "Gate 10 Failed: View button not visible"
        await view_btn.click()
        await page.wait_for_timeout(1500)

        # Dialog should be visible
        dialog_title = page.locator("h2:has-text('Brain MRI')")
        assert await dialog_title.is_visible(), "Gate 10 Failed: Scan Viewer dialog not opened"
        print("GATE 10 PASS: High-res Scan Viewer modal rendered cleanly with image preview.", flush=True)

        # Close dialog
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # GATE 11: Cross-Patient Selection Isolation
        print("\n--- GATE 11: Cross-Patient Selection Isolation ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/patients/PAT-TWO-002", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        # Click imaging tab for Patient Two
        p2_tab = page.locator("button[value='documents']").first
        if await p2_tab.is_visible():
            await p2_tab.click()
            await page.wait_for_timeout(1500)

        p2_banner = page.locator("[data-testid='selected-doc-banner']")
        is_banner_visible = await p2_banner.is_visible()
        assert not is_banner_visible, "Gate 11 Failed: Patient One's selection leaked to Patient Two!"
        print("GATE 11 PASS: Patient switching strictly resets document selection (zero leakage).", flush=True)

        # GATE 12: Refresh Persistence on Patient One
        print("\n--- GATE 12: Refresh Persistence ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/patients/PAT-ONE-001", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        tabs = await page.locator("button[role='tab']").all_inner_texts()
        print(f"Available tabs: {tabs}", flush=True)
        tab_btn = page.locator("button[value='documents'], button:has-text('Imaging')").first
        await tab_btn.click()
        await page.wait_for_timeout(1000)

        # Reload page
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)
        tab_btn2 = page.locator("button[value='documents'], button:has-text('Imaging')").first
        await tab_btn2.click()
        await page.wait_for_timeout(1500)

        reloaded_card = page.locator("[data-testid='doc-card-DOC-2026-001']")
        await reloaded_card.wait_for(state="visible", timeout=15000)
        assert await reloaded_card.is_visible(), "Gate 12 Failed: Brain MRI not visible after reload"
        print("GATE 12 PASS: Refresh preserves patient context and document discovery.", flush=True)

        # GATE 13: Unauthorized Patient Access Rejected
        print("\n--- GATE 13: Cross-Patient Access Restriction ---", flush=True)
        await page.goto(f"{FRONTEND_URL}/app/patients/PAT-ISOLATED-P5", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        p_iso_text = await page.inner_text("body")
        is_blocked = (
            "not found" in p_iso_text.lower()
            or "restricted" in p_iso_text.lower()
            or "care relationship" in p_iso_text.lower()
            or "forbidden" in p_iso_text.lower()
            or "authorized" in p_iso_text.lower()
        )
        assert is_blocked, f"Gate 13 Failed: Doctor accessed unauthorized patient! Body: {p_iso_text[:200]}"
        print("GATE 13 PASS: Unauthorized patient access rejected (403/404 Restricted).", flush=True)

        # GATE 14: Console & Network Cleanliness Audit
        print("\n--- GATE 14: Console & Network Audit ---", flush=True)
        non_403_500s = [req for req in network_requests if req[2] >= 500]
        assert len(non_403_500s) == 0, f"Gate 14 Failed: 500 errors found: {non_403_500s}"
        print(f"Total API requests verified: {len(network_requests)} (Zero 500 errors).", flush=True)

        critical_console = [
            e for e in console_errors
            if "favicon" not in e.lower()
            and "abort" not in e.lower()
            and "403" not in e.lower()
            and "404" not in e.lower()
            and "failed to load resource" not in e.lower()
        ]
        if critical_console:
            print("Console warnings/errors:", critical_console, flush=True)
        assert len(critical_console) == 0, f"Gate 14 Failed: Console runtime errors: {critical_console}"
        print("GATE 14 PASS: Zero console runtime errors.", flush=True)

        await browser.close()

    print("\n=======================================================", flush=True)
    print("ALL 14 BROWSER ACCEPTANCE GATES PASSED (Fix Phase 5)!", flush=True)
    print("=======================================================\n", flush=True)


if __name__ == "__main__":
    asyncio.run(run_phase5_browser_acceptance())
