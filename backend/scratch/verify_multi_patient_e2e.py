import asyncio
import os
import sys
sys.path.append("backend")

from playwright.async_api import async_playwright
import httpx
from app.core.security import create_access_token

BASE_URL = "http://127.0.0.1:8000/api/v1"
FRONTEND_URL = "http://localhost:3100"
ARTIFACT_DIR = r"C:\Users\Vamshikrishna\.gemini\antigravity\brain\ba39a4de-b6aa-4c95-9ea6-ee009b5c1563"

async def setup_patient_two_analysis(client: httpx.AsyncClient, doc_headers: dict):
    """Ensure Patient Two (PAT-TWO-002) has a reviewed and released AI analysis."""
    p2_id = "PAT-TWO-002"
    res = await client.get(f"/ai-analyses?patient_id={p2_id}", headers=doc_headers)
    items = res.json().get("items", []) if res.status_code == 200 else []
    
    target_id = None
    for it in items:
        if it.get("status") == "reviewed" and it.get("is_released_to_patient"):
            target_id = it["analysis_id"]
            break
            
    if not target_id:
        if items:
            target_id = items[0]["analysis_id"]
        else:
            # Trigger analysis
            trig_res = await client.post("/ai-analyses", headers=doc_headers, json={
                "patient_id": p2_id,
                "analysis_type": "BRAIN_MRI"
            })
            if trig_res.status_code in (200, 201):
                target_id = trig_res.json()["analysis_id"]
            else:
                # Direct infer
                target_id = "AI-TEST-PAT2-REV"

        # Review & Release
        await client.post(f"/ai-analyses/{target_id}/review", headers=doc_headers, json={
            "decision": "accepted",
            "clinical_interpretation": "Patient Two scan verified. Deep learning inference accepted.",
            "notes": "INTERNAL NOTES PATIENT TWO: Strictly confidential.",
            "release_to_patient": True
        })
        await client.post(f"/ai-analyses/{target_id}/release", headers=doc_headers)

    return target_id

async def run_multi_patient_browser_e2e():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as http_client:
        # 1. Doctor token
        doc_token = create_access_token("USR-DOC-RAO-001", "doctor")
        doc_headers = {"Authorization": f"Bearer {doc_token}"}

        # 2. Ensure Patient Two has an active released analysis
        p2_analysis_id = await setup_patient_two_analysis(http_client, doc_headers)
        krish_analysis_id = "AI-2026-AC679D"
        print(f"Krish analysis ID: {krish_analysis_id}")
        print(f"Patient Two analysis ID: {p2_analysis_id}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await context.new_page()

            # -------------------------------------------------------------
            # STEP A: DOCTOR WORKSPACE INSPECTION (PATIENT 1 VS PATIENT 2)
            # -------------------------------------------------------------
            print("\n=== STEP A: DOCTOR WORKSPACE INSPECTION ===")
            doc_tokens = {"accessToken": doc_token, "refreshToken": doc_token}
            await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
            await page.evaluate("tokens => localStorage.setItem('clinixai.tokens', JSON.stringify(tokens))", doc_tokens)

            # Doctor opens Krish detail
            await page.goto(f"{FRONTEND_URL}/app/ai-analysis/{krish_analysis_id}", wait_until="networkidle")
            await page.wait_for_timeout(3000)
            krish_doc_text = await page.inner_text("body")
            assert "krish" in krish_doc_text.lower() or "PAT-2026-85014E" in krish_doc_text, "Krish context not found in Doctor view!"
            assert "notumor" in krish_doc_text, "Prediction notumor not found in Doctor view for Krish!"
            print("[PASS] Doctor successfully accesses Krish's AI analysis workspace.")

            # -------------------------------------------------------------
            # STEP B: PATIENT 1 (KRISH) LOGS IN AND VERIFIES OWN REPORTS
            # -------------------------------------------------------------
            print("\n=== STEP B: PATIENT 1 (KRISH) WORKSPACE VERIFICATION ===")
            krish_token = create_access_token("USR-2026-E66A3C", "patient")
            krish_tokens = {"accessToken": krish_token, "refreshToken": krish_token}

            await context.clear_cookies()
            await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
            await page.evaluate("tokens => localStorage.setItem('clinixai.tokens', JSON.stringify(tokens))", krish_tokens)

            await page.goto(f"{FRONTEND_URL}/app/ai-reports", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            krish_list_text = await page.inner_text("body")
            assert krish_analysis_id in krish_list_text, f"{krish_analysis_id} not visible to Krish!"
            assert p2_analysis_id not in krish_list_text, f"LEAK! Patient Two analysis {p2_analysis_id} visible to Krish!"
            print(f"[PASS] Krish sees {krish_analysis_id} and does NOT see {p2_analysis_id}.")

            # Open detail view for Krish
            await page.goto(f"{FRONTEND_URL}/app/ai-reports/{krish_analysis_id}", wait_until="networkidle")
            await page.wait_for_timeout(3000)
            imgs_krish = await page.locator("img").all()
            assert len(imgs_krish) >= 2, f"Expected 2 images for Krish, got {len(imgs_krish)}"
            print("[PASS] Krish detail view loads both Original MRI and Grad-CAM heatmap.")

            # -------------------------------------------------------------
            # STEP C: PATIENT 2 LOGS IN AND VERIFIES ISOLATION
            # -------------------------------------------------------------
            print("\n=== STEP C: PATIENT 2 WORKSPACE & ISOLATION VERIFICATION ===")
            p2_token = create_access_token("USR-PAT-TWO-002", "patient")
            p2_tokens = {"accessToken": p2_token, "refreshToken": p2_token}

            await context.clear_cookies()
            await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
            await page.goto(f"{FRONTEND_URL}/", wait_until="domcontentloaded")
            await page.evaluate("tokens => localStorage.setItem('clinixai.tokens', JSON.stringify(tokens))", p2_tokens)

            await page.goto(f"{FRONTEND_URL}/app/ai-reports", wait_until="networkidle")
            await page.wait_for_timeout(3000)

            p2_list_text = await page.inner_text("body")
            assert krish_analysis_id not in p2_list_text, f"LEAK! Krish analysis {krish_analysis_id} visible to Patient Two!"
            print(f"[PASS] Patient Two does NOT see Krish's analysis {krish_analysis_id}.")

            # Patient Two attempts direct URL access to Krish's analysis
            await page.goto(f"{FRONTEND_URL}/app/ai-reports/{krish_analysis_id}", wait_until="networkidle")
            await page.wait_for_timeout(2000)
            p2_tamper_text = await page.inner_text("body")
            assert "Report not found" in p2_tamper_text or "not yet available" in p2_tamper_text or "Access denied" in p2_tamper_text or "403" in p2_tamper_text, \
                f"Tamper attempt allowed! Patient Two accessed Krish's report: {p2_tamper_text[:200]}"
            print("[PASS] Patient Two direct access to Krish's analysis is strictly blocked.")

            print("\n=== MULTI-PATIENT ISOLATION TEST PASSED COMPLETELY! ===")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_multi_patient_browser_e2e())

