import asyncio
import os
import sys
import json
sys.path.append("backend")

from playwright.async_api import async_playwright
import httpx
from app.core.security import create_access_token

FRONTEND_URL = "http://localhost:3100"
BACKEND_URL = "http://127.0.0.1:8000/api/v1"
ARTIFACT_DIR = r"C:\Users\Vamshikrishna\.gemini\antigravity\brain\ba39a4de-b6aa-4c95-9ea6-ee009b5c1563"

async def test_complete_production_workflow():
    print("\n" + "="*80)
    print("CLINIXAI — FULL PRODUCTION WORKFLOW E2E VERIFICATION")
    print("="*80)

    # Doctor and Patient tokens
    doc_token = create_access_token("USR-DOC-RAO-001", "doctor")
    krish_token = create_access_token("USR-2026-E66A3C", "patient")

    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    krish_headers = {"Authorization": f"Bearer {krish_token}"}

    network_requests = []
    console_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        page.on("request", lambda req: network_requests.append({
            "method": req.method,
            "url": req.url,
        }))
        page.on("response", lambda res: network_requests.append({
            "status": res.status,
            "url": res.url,
        }))
        page.on("console", lambda m: console_errors.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: console_errors.append(f"[PAGE ERROR] {e}"))

        # ---------------------------------------------------------------------
        # 1. DOCTOR WORKSPACE: FIND KRISH AND OPEN ANALYSIS
        # ---------------------------------------------------------------------
        print("\n[STEP 1] Doctor Login & Workspace Selection")
        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""t => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(t));
        }""", {"accessToken": doc_token, "refreshToken": doc_token})

        target_analysis_id = "AI-2026-AC679D"
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis/{target_analysis_id}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Check Doctor Page Content
        body_text = await page.inner_text("body")
        assert "krish" in body_text.lower() or "PAT-2026-85014E" in body_text, "Krish context missing in Doctor view!"
        assert "Brain MRI Tumor Classification" in body_text, "Model name missing!"
        assert "ResNet50" in body_text, "ResNet50 architecture missing!"
        assert "notumor" in body_text, "Prediction notumor missing!"
        print("[PASS] Doctor view displays correct patient context, ResNet50 model, and notumor prediction.")

        # Check Images in Doctor View
        imgs = await page.locator("img").all()
        assert len(imgs) >= 2, f"Expected 2 images on doctor analysis page, got {len(imgs)}"
        doc_img_srcs = [await img.get_attribute("src") for img in imgs]
        blob_urls = [s for s in doc_img_srcs if s and s.startswith("blob:")]
        assert len(blob_urls) >= 2, f"Expected 2 blob URLs for Original & Grad-CAM, got {len(blob_urls)}"
        print(f"[PASS] Doctor view displays Original MRI and Grad-CAM: {blob_urls}")

        doc_screenshot = os.path.join(ARTIFACT_DIR, "production_doc_analysis_view.png")
        await page.screenshot(path=doc_screenshot, full_page=True)

        # ---------------------------------------------------------------------
        # 2. DOCTOR REVIEWS & EXPLICITLY RELEASES TO PATIENT
        # ---------------------------------------------------------------------
        print("\n[STEP 2] Doctor Review & Release Persistence Check")
        # Save review via API
        async with httpx.AsyncClient(base_url=BACKEND_URL) as http_client:
            rev_res = await http_client.post(f"/ai-analyses/{target_analysis_id}/review", headers=doc_headers, json={
                "decision": "accepted",
                "clinical_interpretation": "Axial Brain MRI reviewed. Sided lesion verified with deep learning ResNet50 model. No tumor detected.",
                "notes": "CONFIDENTIAL CLINICAL NOTE: Re-scan in 6 months if symptoms re-occur.",
                "release_to_patient": True
            })
            assert rev_res.status_code == 200, f"Doctor review failed: {rev_res.text}"
            
            # Explicit Release API
            rel_res = await http_client.post(f"/ai-analyses/{target_analysis_id}/release", headers=doc_headers)
            assert rel_res.status_code == 200, f"Release failed: {rel_res.text}"
            rel_data = rel_res.json()
            assert rel_data.get("is_released_to_patient") is True, "is_released_to_patient is not True!"
            assert rel_data.get("status") == "reviewed", "status is not reviewed!"
            print("[PASS] MongoDB persistence confirmed: status=reviewed, is_released_to_patient=true.")

        # ---------------------------------------------------------------------
        # 3. DOCTOR LOGOUT -> PATIENT LOGIN
        # ---------------------------------------------------------------------
        print("\n[STEP 3] Doctor Logout -> Patient Krish Login")
        await context.clear_cookies()
        await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")

        await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
        await page.evaluate("""t => {
            localStorage.setItem('clinixai.tokens', JSON.stringify(t));
        }""", {"accessToken": krish_token, "refreshToken": krish_token})

        # ---------------------------------------------------------------------
        # 4. PATIENT OPENS /app/ai-reports
        # ---------------------------------------------------------------------
        print("\n[STEP 4] Patient Visits /app/ai-reports")
        await page.goto(f"{FRONTEND_URL}/app/ai-reports", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        pat_list_text = await page.inner_text("body")
        assert "Access denied" not in pat_list_text, "Hit Access Denied on patient /app/ai-reports!"
        assert target_analysis_id in pat_list_text, f"{target_analysis_id} not visible in patient report list!"
        assert "Doctor Reviewed" in pat_list_text, "Doctor Reviewed badge not visible!"
        assert "notumor" in pat_list_text, "Prediction notumor not visible in list!"
        print("[PASS] Patient Krish sees released analysis in AI Reports list.")

        pat_list_screenshot = os.path.join(ARTIFACT_DIR, "production_patient_reports_list.png")
        await page.screenshot(path=pat_list_screenshot, full_page=True)

        # ---------------------------------------------------------------------
        # 5. PATIENT OPENS DETAIL VIEW /app/ai-reports/AI-2026-AC679D
        # ---------------------------------------------------------------------
        print("\n[STEP 5] Patient Views Report Detail")
        await page.goto(f"{FRONTEND_URL}/app/ai-reports/{target_analysis_id}", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        pat_detail_text = await page.inner_text("body")
        assert target_analysis_id in pat_detail_text, "Analysis ID missing on detail page!"
        assert "AI results are advisory" in pat_detail_text, "Advisory safety disclaimer missing!"
        assert "Axial Brain MRI reviewed" in pat_detail_text, "Doctor clinical interpretation missing!"
        assert "CONFIDENTIAL CLINICAL NOTE" not in pat_detail_text, "DOCTOR PRIVATE NOTE LEAKED TO PATIENT!"

        pat_imgs = await page.locator("img").all()
        assert len(pat_imgs) >= 2, f"Expected at least 2 images for patient, got {len(pat_imgs)}"
        pat_img_srcs = [await img.get_attribute("src") for img in pat_imgs]
        pat_blobs = [s for s in pat_img_srcs if s and s.startswith("blob:")]
        assert len(pat_blobs) >= 2, f"Expected 2 blob URLs for Original & Grad-CAM in patient view, got {len(pat_blobs)}"
        print(f"[PASS] Patient detail view displays Original MRI and Grad-CAM: {pat_blobs}")

        pat_detail_screenshot = os.path.join(ARTIFACT_DIR, "production_patient_report_detail.png")
        await page.screenshot(path=pat_detail_screenshot, full_page=True)

        # ---------------------------------------------------------------------
        # 6. PATIENT BROWSER REFRESH
        # ---------------------------------------------------------------------
        print("\n[STEP 6] Patient Refreshes Browser Page")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(3000)

        reload_text = await page.inner_text("body")
        assert target_analysis_id in reload_text, "Analysis ID lost after browser refresh!"
        reload_imgs = await page.locator("img").all()
        assert len(reload_imgs) >= 2, f"Expected 2 images after refresh, got {len(reload_imgs)}"
        print("[PASS] Report and images persist across full browser refresh.")

        # ---------------------------------------------------------------------
        # 7. DIRECT ROUTE TO /app/ai-analysis REDIRECTION TEST
        # ---------------------------------------------------------------------
        print("\n[STEP 7] Patient Direct Navigation to /app/ai-analysis")
        await page.goto(f"{FRONTEND_URL}/app/ai-analysis", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        assert "/app/ai-reports" in page.url, f"Expected redirect to /app/ai-reports, got {page.url}"
        assert "Access denied" not in await page.inner_text("body"), "Hit Access Denied on redirect!"
        print("[PASS] Smooth client-side redirect from /app/ai-analysis to /app/ai-reports without 'Access denied'.")

        await browser.close()

    print("\n" + "="*80)
    print("ALL PRODUCTION E2E VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_complete_production_workflow())

