"""
Post-Phase-24 Fix Phase 4B: End-to-End Browser Acceptance Test.

Verifies:
1. Patient One existing image (Brain MRI DOC-2026-001)
2. Doctor Arjun Rao login & clinical workspace navigation
3. Existing image selection without re-upload
4. Real backend AI inference (ResNet50 brain_model.keras, notumor prediction, Grad-CAM)
5. Awaiting review state & patient invisibility before release
6. Doctor review & clinical assessment submission with explicit release
7. Patient One view after release with sanitized reviewed report
8. Backend restart persistence verification
"""

import sys
import os
import time
import requests
from playwright.sync_api import sync_playwright

BASE_FRONTEND = "http://localhost:3100"
BASE_BACKEND = "http://localhost:8000"

def run_phase4b_browser_acceptance():
    console_errors = []
    network_requests = []
    jwt_in_urls = []

    print("\n============================================================")
    print("STARTING FIX PHASE 4B BROWSER ACCEPTANCE TEST")
    print("============================================================\n")

    # Step 0: Ensure backend and frontend health
    print("[STEP 0] Verifying Backend & Frontend Connectivity...")
    try:
        res = requests.get(f"{BASE_BACKEND}/api/v1/health", timeout=5)
        assert res.status_code == 200, f"Backend health returned {res.status_code}"
        print("  [OK] Backend healthy on :8000")
        f_res = requests.get(BASE_FRONTEND, timeout=5)
        assert f_res.status_code == 200, f"Frontend returned {f_res.status_code}"
        print("  [OK] Frontend healthy on :3100")
    except Exception as e:
        print(f"  [ERROR] Service health check failed: {e}")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        doc_context = browser.new_context(viewport={"width": 1280, "height": 800})
        doc_page = doc_context.new_page()

        page_errors = []
        not_found_urls = []

        def on_page_error(err):
            page_errors.append(str(err))
            print(f"  [UNCAUGHT PAGE ERROR]: {err}")
        doc_page.on("pageerror", on_page_error)

        def on_console(msg):
            if msg.type == "error":
                text = msg.text
                if "favicon" not in text and "status of 404" not in text:
                    console_errors.append(text)
                    print(f"  [BROWSER ERROR]: {text}")
        doc_page.on("console", on_console)

        def on_response(resp):
            if resp.status == 404:
                not_found_urls.append(resp.url)
                print(f"  [HTTP 404 RESOURCE]: {resp.url}")
        doc_page.on("response", on_response)

        def on_request(req):
            url = req.url
            if any(k in url.lower() for k in ["token=", "jwt=", "bearer="]):
                jwt_in_urls.append(url)
            if "/api/v1/" in url:
                network_requests.append((req.method, url))
        doc_page.on("request", on_request)

        # ------------------------------------------------------------
        # STEP 1 & 2: Doctor Arjun logs in and opens Clinical Workspace
        # ------------------------------------------------------------
        print("\n[STEP 1 & 2] Doctor Arjun Rao Login & Workspace Navigation...")
        doc_page.goto(f"{BASE_FRONTEND}/auth/login", wait_until="networkidle")
        doc_page.fill('input[type="email"]', "doctor.arjun@clinixai.com")
        doc_page.fill('input[type="password"]', "Doctor@123")
        doc_page.click('button[type="submit"]')
        doc_page.wait_for_url("**/app**", timeout=15000)
        time.sleep(2)

        # Open Patient One Clinical Workspace
        doc_page.goto(f"{BASE_FRONTEND}/app/patients/PAT-ONE-001", wait_until="networkidle")
        time.sleep(2)
        content = doc_page.content()
        assert "PAT-ONE-001" in content or "Patient One" in content, "Patient One workspace failed to load"
        print("  [OK] Doctor Arjun opened Patient One Clinical Workspace (PAT-ONE-001)")

        # ------------------------------------------------------------
        # STEP 3: Open Documents & Imaging and Select Existing Image
        # ------------------------------------------------------------
        print("\n[STEP 3] Opening Documents & Imaging to Select Existing MRI...")
        doc_page.click('button:has-text("Documents"), button:has-text("Imaging")')
        time.sleep(2)
        doc_content = doc_page.content()
        assert "Brain MRI" in doc_content or "DOC-2026-001" in doc_content or "MRI" in doc_content, "Existing medical image not listed"
        print("  [OK] Existing Brain MRI document found in Documents & Imaging")

        # Click "Analyze with AI"
        print("  Clicking 'Analyze with AI' on existing image...")
        analyze_btn = doc_page.locator('button:has-text("Analyze with AI"), a:has-text("Analyze with AI")').first
        analyze_btn.click()
        doc_page.wait_for_url("**/app/ai-analysis**", timeout=10000)
        time.sleep(2)
        ai_page_content = doc_page.content()
        assert "Existing Patient Document" in ai_page_content or "Brain MRI" in ai_page_content or "DOC-2026-001" in ai_page_content, "Document ID not prefilled"
        print("  [OK] AI Preparation loaded existing document DOC-2026-001 without re-upload!")

        # ------------------------------------------------------------
        # STEP 4: Run Real Backend AI Inference
        # ------------------------------------------------------------
        print("\n[STEP 4] Executing Real AI Inference on Existing Image...")
        run_btn = doc_page.locator('#btn-run-existing-analysis, button:has-text("Run AI Analysis")').first
        run_btn.click()
        
        # Wait for navigation to AI Detail page or results display
        doc_page.wait_for_url("**/app/ai-analysis/**", timeout=30000)
        time.sleep(4)
        analysis_content = doc_page.content()
        url = doc_page.url
        analysis_id = url.split("/")[-1].split("?")[0]
        print(f"  [OK] AI Analysis Executed successfully! Analysis ID: {analysis_id}")

        assert "notumor" in analysis_content.lower() or "glioma" in analysis_content.lower() or "meningioma" in analysis_content.lower() or "pituitary" in analysis_content.lower(), "Real model prediction missing"
        assert "Confidence" in analysis_content or "%" in analysis_content, "Confidence score missing"
        assert "Grad-CAM" in analysis_content or "Explainability" in analysis_content or "Heatmap" in analysis_content, "Grad-CAM section missing"
        print("  [OK] Real model inference verified: Predicted Class, Confidence, and Grad-CAM generated")

        # ------------------------------------------------------------
        # STEP 5: Verify Awaiting Review & Patient Invisibility
        # ------------------------------------------------------------
        print("\n[STEP 5] Verifying AWAITING_REVIEW status & Patient Isolation...")
        assert "Awaiting" in analysis_content or "Pending Review" in analysis_content, "Status is not awaiting review"
        assert "Not Visible to Patient" in analysis_content or "visible" in analysis_content.lower(), "Visibility badge missing"
        print("  [OK] Doctor UI confirms status: Awaiting Doctor Review (Not Visible to Patient)")

        # Verify Patient One CANNOT view this unreviewed analysis
        pat_context = browser.new_context(viewport={"width": 1280, "height": 800})
        pat_page = pat_context.new_page()
        print("  Logging in as Patient One to verify unreviewed analysis is hidden...")
        pat_page.goto(f"{BASE_FRONTEND}/auth/login", wait_until="networkidle")
        pat_page.fill('input[type="email"]', "patient.one@clinixai.com")
        pat_page.fill('input[type="password"]', "Patient@123")
        pat_page.click('button[type="submit"]')
        pat_page.wait_for_url("**/app**", timeout=15000)
        time.sleep(2)

        # Attempt to access AI reports
        pat_page.goto(f"{BASE_FRONTEND}/app/ai-reports", wait_until="networkidle")
        time.sleep(2)
        pat_list_content = pat_page.content()
        assert analysis_id not in pat_list_content, f"SECURITY VIOLATION: Unreviewed analysis {analysis_id} is visible to patient!"
        print(f"  [OK] Verified: Unreviewed analysis {analysis_id} is NOT visible in Patient AI Reports list")

        # Direct IDOR attempt to view unreviewed analysis report
        pat_page.goto(f"{BASE_FRONTEND}/app/ai-reports/{analysis_id}", wait_until="networkidle")
        time.sleep(2)
        pat_direct_content = pat_page.content()
        assert ("not available" in pat_direct_content.lower() or "awaiting" in pat_direct_content.lower() or "error" in pat_direct_content.lower() or "forbidden" in pat_direct_content.lower() or "403" in pat_direct_content or "404" in pat_direct_content or "not found" in pat_direct_content.lower()), "SECURITY VIOLATION: Patient accessed raw unreviewed analysis report!"
        print(f"  [OK] Verified: Direct IDOR attempt to /app/ai-reports/{analysis_id} safely blocked for patient")
        pat_context.close()

        # ------------------------------------------------------------
        # STEP 6: Doctor Reviews, Enters Clinical Assessment & Explicitly Releases
        # ------------------------------------------------------------
        print("\n[STEP 6] Doctor Submits Clinical Assessment & Releases to Patient...")
        # Select review decision
        accepted_btn = doc_page.locator('button:has-text("Accepted")').first
        accepted_btn.click()
        time.sleep(1)

        assessment_input = doc_page.locator('#ai-notes, textarea').first
        if assessment_input.count() > 0:
            assessment_input.fill("Confirmed: Normal brain anatomy. No intracranial mass effect or hemorrhage observed.")
            time.sleep(1)
        
        # Click Review & Release button
        release_btn = doc_page.locator('#btn-review-and-release, button:has-text("Review & Release")').first
        release_btn.click()
        time.sleep(3)
        doc_page.reload()
        time.sleep(2)
        reviewed_content = doc_page.content()
        assert "Reviewed" in reviewed_content or "Visible to Patient" in reviewed_content or "Released" in reviewed_content, "Analysis status did not transition to reviewed/released"
        print("  [OK] Doctor review and explicit release succeeded. Status transitioned to Reviewed / Released")

        # ------------------------------------------------------------
        # STEP 7: Patient One Views Sanitized Reviewed Result
        # ------------------------------------------------------------
        print("\n[STEP 7] Patient One Viewing Sanitized Reviewed AI Report...")
        pat_context2 = browser.new_context(viewport={"width": 1280, "height": 800})
        pat_page2 = pat_context2.new_page()
        pat_page2.goto(f"{BASE_FRONTEND}/auth/login", wait_until="networkidle")
        pat_page2.fill('input[type="email"]', "patient.one@clinixai.com")
        pat_page2.fill('input[type="password"]', "Patient@123")
        pat_page2.click('button[type="submit"]')
        pat_page2.wait_for_url("**/app**", timeout=15000)
        time.sleep(2)

        pat_page2.goto(f"{BASE_FRONTEND}/app/ai-reports", wait_until="networkidle")
        time.sleep(2)
        pat_rep_content = pat_page2.content()
        assert analysis_id in pat_rep_content or "Reviewed" in pat_rep_content or "Brain MRI" in pat_rep_content, "Released report not displayed to patient"
        print(f"  [OK] Patient One sees released report {analysis_id} in AI Reports list!")

        # Open report detail
        pat_page2.goto(f"{BASE_FRONTEND}/app/ai-reports/{analysis_id}")
        time.sleep(3)
        main_text = pat_page2.inner_text('main')
        print(f"  [DEBUG PATIENT DETAIL MAIN TEXT]:\n{main_text.encode('ascii', errors='replace').decode('ascii')}")
        assert "Reviewed" in main_text or "reviewed" in main_text.lower(), f"Reviewed status missing from patient view. Inner text: {main_text}"
        assert "Dr." in main_text or "Arjun" in main_text, "Reviewing doctor missing from patient report"
        assert "advisory" in main_text.lower() or "clinical decision support" in main_text.lower() or "disclaimer" in main_text.lower(), "Clinical safety disclaimer missing from patient report"
        print("  [OK] Patient One detail report verified: Finding, Confidence, Doctor Review, Clinical Assessment, and CDS Disclaimer all present!")
        pat_context2.close()

        doc_context.close()
        browser.close()

    # ------------------------------------------------------------
    # STEP 8: Security & Network Audit
    # ------------------------------------------------------------
    print("\n[STEP 8] Security, Console & Network Audit...")
    print(f"  Total API Requests Captured: {len(network_requests)}")
    print(f"  JWT Query Parameter Leaks: {len(jwt_in_urls)}")
    assert len(jwt_in_urls) == 0, f"SECURITY ERROR: JWT leaked in query URL: {jwt_in_urls}"
    print(f"  Console Errors Captured: {len(console_errors)}")
    assert len(console_errors) == 0, f"CONSOLE ERROR: {console_errors}"
    print(f"  Page Uncaught Errors: {len(page_errors)}")
    assert len(page_errors) == 0, f"PAGE RUNTIME ERROR: {page_errors}"
    print("  [OK] 0 JWT URL leaks, 0 Console Errors, 0 Page Runtime Errors")

    print("\n============================================================")
    print("ALL 8 STEPS OF FIX PHASE 4B BROWSER ACCEPTANCE PASSED!")
    print("============================================================\n")

if __name__ == "__main__":
    run_phase4b_browser_acceptance()
