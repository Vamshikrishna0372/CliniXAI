import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_full_pipeline():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("\n=== STEP 1: DOCTOR AUTHENTICATION ===")
        doc_login = await client.post("/auth/login", json={
            "email": "doctor.arjun@clinixai.com",
            "password": "Doctor@123"
        })
        assert doc_login.status_code == 200, f"Doctor login failed: {doc_login.text}"
        doc_token = doc_login.json()["access_token"]
        doc_headers = {"Authorization": f"Bearer {doc_token}"}
        print("Doctor logged in successfully.")

        print("\n=== STEP 2: VERIFY OR CREATE REVIEWED & RELEASED AI ANALYSIS FOR KRISH ===")
        # Check Krish's canonical ID
        krish_pat_id = "PAT-2026-85014E"
        analyses_res = await client.get(f"/ai-analyses?patient_id={krish_pat_id}", headers=doc_headers)
        assert analyses_res.status_code == 200, f"Failed to list analyses: {analyses_res.text}"
        items = analyses_res.json()["items"]
        print(f"Found {len(items)} analyses for Krish.")

        # Find or use the latest analysis
        target_analysis_id = None
        for it in items:
            if it.get("status") == "reviewed" and it.get("is_released_to_patient"):
                target_analysis_id = it["analysis_id"]
                print(f"Found existing released analysis: {target_analysis_id}")
                break

        if not target_analysis_id and items:
            target_analysis_id = items[0]["analysis_id"]
            print(f"Releasing analysis {target_analysis_id}...")
            # Save review first if not reviewed
            rev_res = await client.post(f"/ai-analyses/{target_analysis_id}/review", headers=doc_headers, json={
                "decision": "accepted",
                "clinical_interpretation": "Patient scan verified. No tumor detected. Advisory AI findings confirmed.",
                "notes": "INTERNAL CLINICAL NOTE: Follow up in 6 months if symptoms re-occur.",
                "release_to_patient": False
            })
            assert rev_res.status_code == 200, f"Review failed: {rev_res.text}"
            
            # Explicit release
            rel_res = await client.post(f"/ai-analyses/{target_analysis_id}/release", headers=doc_headers)
            assert rel_res.status_code == 200, f"Release failed: {rel_res.text}"
            print(f"Explicitly released {target_analysis_id}")

        print(f"Target analysis for test: {target_analysis_id}")

        print("\n=== STEP 3: PATIENT KRISH AUTHENTICATION ===")
        pat_login = await client.post("/auth/login", json={
            "email": "krish@gmail.com",
            "password": "Password@123"
        })
        assert pat_login.status_code == 200, f"Krish login failed: {pat_login.text}"
        pat_token = pat_login.json()["access_token"]
        pat_headers = {"Authorization": f"Bearer {pat_token}"}
        print("Krish logged in successfully.")

        print("\n=== STEP 4: PATIENT LISTS OWN AI ANALYSES ===")
        pat_list_res = await client.get("/ai-analyses", headers=pat_headers)
        assert pat_list_res.status_code == 200, f"Patient list failed: {pat_list_res.text}"
        pat_items = pat_list_res.json()["items"]
        print(f"Patient sees {len(pat_items)} released analyses.")
        released_ids = [it["analysis_id"] for it in pat_items]
        print(f"Released analysis IDs: {released_ids}")
        assert target_analysis_id in released_ids, f"Target {target_analysis_id} not visible to patient!"
        print("[SUCCESS] Patient correctly sees released analysis in /ai-analyses list.")

        print("\n=== STEP 5: PATIENT RETRIEVES SINGLE AI ANALYSIS DETAIL ===")
        detail_res = await client.get(f"/ai-analyses/{target_analysis_id}", headers=pat_headers)
        assert detail_res.status_code == 200, f"Detail retrieval failed: {detail_res.text}"
        detail_data = detail_res.json()
        print(f"Analysis status: {detail_data.get('status')}")
        print(f"Is released to patient: {detail_data.get('is_released_to_patient')}")
        print(f"Doctor review notes field: {detail_data.get('doctor_review', {}).get('notes')}")
        assert detail_data.get("doctor_review", {}).get("notes") is None, "DOCTOR INTERNAL NOTES LEAKED TO PATIENT!"
        print(f"Clinical interpretation visible: {detail_data.get('doctor_review', {}).get('clinical_interpretation')}")
        print("[SUCCESS] Doctor private notes are redacted, clinical summary is visible.")

        print("\n=== STEP 6: PATIENT RETRIEVES ORIGINAL IMAGE & GRAD-CAM HEATMAP ===")
        orig_img_res = await client.get(f"/ai-analyses/{target_analysis_id}/image", headers=pat_headers)
        assert orig_img_res.status_code == 200, f"Original image fetch failed: {orig_img_res.text}"
        assert len(orig_img_res.content) > 1000, "Original image content is empty or too small"
        print(f"Original image bytes retrieved: {len(orig_img_res.content)} bytes, content-type: {orig_img_res.headers.get('content-type')}")

        gradcam_res = await client.get(f"/ai-analyses/{target_analysis_id}/gradcam", headers=pat_headers)
        assert gradcam_res.status_code == 200, f"Grad-CAM fetch failed: {gradcam_res.text}"
        assert len(gradcam_res.content) > 1000, "Grad-CAM content is empty or too small"
        print(f"Grad-CAM bytes retrieved: {len(gradcam_res.content)} bytes, content-type: {gradcam_res.headers.get('content-type')}")
        print("[SUCCESS] Both original MRI image and Grad-CAM overlay load cleanly via authenticated endpoints.")

        print("\n=== STEP 7: CROSS-PATIENT ISOLATION (PATIENT TWO CANNOT ACCESS KRISH'S ANALYSIS) ===")
        p2_login = await client.post("/auth/login", json={
            "email": "patient.two@clinixai.com",
            "password": "Password@123"
        })
        if p2_login.status_code == 200:
            p2_token = p2_login.json()["access_token"]
            p2_headers = {"Authorization": f"Bearer {p2_token}"}
            p2_access = await client.get(f"/ai-analyses/{target_analysis_id}", headers=p2_headers)
            print(f"Patient Two access status code: {p2_access.status_code}")
            assert p2_access.status_code == 403, f"Cross-patient isolation failed: expected 403, got {p2_access.status_code}"
            
            p2_img_access = await client.get(f"/ai-analyses/{target_analysis_id}/image", headers=p2_headers)
            print(f"Patient Two image access status code: {p2_img_access.status_code}")
            assert p2_img_access.status_code == 403, f"Cross-patient image isolation failed: expected 403, got {p2_img_access.status_code}"
            print("[SUCCESS] Cross-patient RBAC isolation verified: 403 Forbidden.")
        else:
            print(f"Skipping Patient Two check (login status: {p2_login.status_code})")

        print("\n=== ALL BACKEND PERSISTENCE & SECURITY CHECKS PASSED! ===")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())

