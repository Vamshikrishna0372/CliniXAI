import asyncio
import httpx
import json
import sys
sys.path.append("backend")
from app.core.security import create_access_token

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_provenance_and_ai():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login as Dr. Rao
        login_resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}
        )
        assert login_resp.status_code == 200, f"Dr Rao login failed: {login_resp.text}"
        doc_token = login_resp.json()["access_token"]
        doc_headers = {"Authorization": f"Bearer {doc_token}"}
        print("1. Dr. Rao logged in successfully.")

        # 2. Check documents for Krish
        krish_pid = "PAT-2026-85014E"
        docs_resp = await client.get(
            f"{BASE_URL}/documents",
            headers=doc_headers,
            params={"patient_id": krish_pid}
        )
        assert docs_resp.status_code == 200, f"List docs failed: {docs_resp.text}"
        docs_data = docs_resp.json()
        print(f"2. Retrieved {docs_data['total']} documents for Krish.")
        for d in docs_data["items"]:
            print(f"   Doc ID: {d['document_id']} | Title: {d['title']} | Uploader: {d.get('uploader_name')} ({d.get('uploader_role')}) | Uploader Object: {d.get('uploader')}")
            assert d.get("uploader_role") in ["patient", "doctor", "staff", "unknown"]
            assert d.get("uploader") is not None
            assert d["uploader"].get("role") is not None

        # 3. Test direct inference with Krish's real Brain MRI file
        target_doc = docs_data["items"][0]
        file_resp = await client.get(
            f"{BASE_URL}/documents/{target_doc['document_id']}/download",
            headers=doc_headers
        )
        assert file_resp.status_code == 200, "Failed to download MRI bytes"
        mri_bytes = file_resp.content
        print(f"3. Downloaded {len(mri_bytes)} bytes of Krish's real Brain MRI.")

        # 4. Test inference WITHOUT patient_id as Doctor -> Expect 400 Bad Request
        missing_pid_resp = await client.post(
            f"{BASE_URL}/ai/infer",
            headers=doc_headers,
            files={"image": ("mri.png", mri_bytes, "image/png")},
            data={"analysis_type": "BRAIN_MRI"}
        )
        print(f"4. Missing patient_id response status: {missing_pid_resp.status_code}")
        assert missing_pid_resp.status_code == 400, "Should reject doctor infer without patient_id"
        print("   Correctly rejected inference with 400 Bad Request when patient_id is omitted.")

        # 5. Test inference WITH Krish's canonical patient_id
        infer_resp = await client.post(
            f"{BASE_URL}/ai/infer",
            headers=doc_headers,
            files={"image": ("mri.png", mri_bytes, "image/png")},
            data={"analysis_type": "BRAIN_MRI", "patient_id": krish_pid}
        )
        assert infer_resp.status_code == 200, f"Infer failed: {infer_resp.text}"
        infer_data = infer_resp.json()
        created_analysis_id = infer_data["analysis_id"]
        print(f"5. Real Brain MRI Inference Succeeded:")
        print(f"   Analysis ID: {created_analysis_id}")
        print(f"   Predicted Class: {infer_data['predicted_class']}")
        print(f"   Confidence: {infer_data['confidence']}")
        print(f"   Grad-CAM Available: {infer_data['gradcam_available']}")

        # 6. Verify Analysis Detail Record
        an_resp = await client.get(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}",
            headers=doc_headers
        )
        assert an_resp.status_code == 200, f"Get analysis failed: {an_resp.text}"
        an_data = an_resp.json()
        print(f"6. Analysis Record Verification:")
        print(f"   Stored patient_id: {an_data['patient_id']}")
        print(f"   Stored doctor_id: {an_data['doctor_id']}")
        print(f"   Associated document_id: {an_data.get('document_id')}")
        assert an_data["patient_id"] == krish_pid, f"Expected {krish_pid}, got {an_data['patient_id']}!"
        assert an_data["doctor_id"] == "DOC-RAO-001"

        # 7. Verify Document Linkage & Provenance
        assert an_data.get("document_id") is not None, "Analysis must be linked to a document"
        linked_doc_resp = await client.get(
            f"{BASE_URL}/documents/{an_data['document_id']}",
            headers=doc_headers
        )
        assert linked_doc_resp.status_code == 200
        linked_doc = linked_doc_resp.json()
        print(f"7. Linked Document Verification:")
        print(f"   Doc ID: {linked_doc['document_id']}")
        print(f"   Patient ID: {linked_doc['patient_id']}")
        print(f"   Uploader: {linked_doc['uploader_name']} ({linked_doc['uploader_role']})")
        print(f"   Analysis ID: {linked_doc.get('ai_analysis_id')}")
        assert linked_doc["patient_id"] == krish_pid
        assert linked_doc["ai_analysis_id"] == created_analysis_id
        assert linked_doc["uploader_role"] == "doctor"
        assert linked_doc["uploader_name"] == "Dr. Arjun Rao"

        # 8. Test Authenticated Original Image Endpoint
        img_resp = await client.get(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}/image",
            headers=doc_headers
        )
        assert img_resp.status_code == 200, f"Get image failed: {img_resp.status_code}"
        print(f"8. Original image endpoint returned HTTP 200, {len(img_resp.content)} bytes, Content-Type: {img_resp.headers.get('content-type')}")
        assert len(img_resp.content) > 0

        # 9. Test Review with Clinical Assessment
        review_resp = await client.post(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}/review",
            headers=doc_headers,
            json={
                "decision": "accepted",
                "clinical_interpretation": "Axial Brain MRI reviewed. Sided lesion verified with deep learning ResNet50 model.",
                "release_to_patient": False
            }
        )
        assert review_resp.status_code == 200
        print("9. Doctor review saved successfully.")

        # 10. Test Explicit Release
        release_resp = await client.post(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}/release",
            headers=doc_headers
        )
        assert release_resp.status_code == 200
        print("10. Explicit release to patient succeeded.")

        # 11. Verify Krish (Patient) can view the released report
        krish_token = create_access_token(user_id="USR-2026-E66A3C", role="patient")
        krish_headers = {"Authorization": f"Bearer {krish_token}"}

        krish_report_resp = await client.get(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}/report",
            headers=krish_headers
        )
        assert krish_report_resp.status_code == 200, f"Krish failed to access report: {krish_report_resp.text}"
        print(f"11. Krish successfully accessed own released AI report ({krish_report_resp.json()['analysis_id']}).")

        # 12. Verify Patient Two cannot view Krish's report (Patient Isolation)
        pat2_token = create_access_token(user_id="USR-PAT-TWO", role="patient")
        pat2_headers = {"Authorization": f"Bearer {pat2_token}"}
        pat2_cross_resp = await client.get(
            f"{BASE_URL}/ai-analyses/{created_analysis_id}/report",
            headers=pat2_headers
        )
        print(f"12. Patient Two cross-patient access attempt status: {pat2_cross_resp.status_code}")
        assert pat2_cross_resp.status_code in [403, 404], "Cross patient isolation violated!"
        print("12. Patient isolation verified: Patient Two blocked from Krish's report.")

        print("\nALL VERIFICATIONS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(test_provenance_and_ai())
