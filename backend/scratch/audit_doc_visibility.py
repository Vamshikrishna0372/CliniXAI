import sys
sys.path.insert(0, "backend")
import asyncio
import json
from app.database.mongodb import connect_to_mongo, close_mongo_connection, db_manager
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_AI_ANALYSES, COLLECTION_PRESCRIPTIONS
)

async def main():
    await connect_to_mongo()
    db = db_manager.db
    
    # Dr. Arjun Rao
    doc_user = await db[COLLECTION_USERS].find_one({"email": "doctor.arjun@clinixai.com"})
    doc_rec = await db[COLLECTION_DOCTORS].find_one({"user_id": doc_user["user_id"]})
    doctor_id = doc_rec["doctor_id"]
    print(f"Doctor: {doctor_id} ({doc_rec['full_name']}, user_id={doc_user['user_id']})")
    
    # All documents
    docs = await db[COLLECTION_DOCUMENTS].find({"is_deleted": {"$ne": True}}).to_list(100)
    print(f"\nTotal active documents: {len(docs)}")
    
    # Audit for Patient A and Patient B
    print("\n" + "="*80)
    print("PATIENT A vs PATIENT B AUDIT IN DATABASE")
    print("="*80)
    
    for d in docs:
        pid = d.get("patient_id")
        doc_id = d.get("document_id")
        title = d.get("title")
        cat = d.get("category")
        fname = d.get("original_file_name") or d.get("file_name")
        mime = d.get("mime_type")
        storage = d.get("storage_path")
        deleted = d.get("is_deleted", False)
        apt_id = d.get("appointment_id")
        mr_id = d.get("medical_record_id")
        uploader = d.get("uploaded_by")
        
        # Check patient
        pat = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": pid}, {"user_id": pid}]})
        
        # Check doctor appointment
        check_pids = [pid]
        if pat:
            if pat.get("patient_id"): check_pids.append(pat["patient_id"])
            if pat.get("user_id"): check_pids.append(pat["user_id"])
        clean_pids = list(set([p for p in check_pids if p]))
        
        apt_q = {"patient_id": clean_pids[0], "doctor_id": doctor_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doctor_id}
        apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
        cns = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
        
        # Check if doctor is authorized
        is_uploader = uploader == doc_user["user_id"]
        authorized = bool(apt or cns or is_uploader)
        
        print(f"\nDOCUMENT: {doc_id}")
        print(f"  Title: {title}")
        print(f"  Category: {cat}")
        print(f"  MIME: {mime}")
        print(f"  Filename: {fname}")
        print(f"  Storage: {storage}")
        print(f"  Deleted: {deleted}")
        print(f"  patient_id in doc: {pid}")
        print(f"  Patient profile: {pat.get('patient_id') if pat else 'NO PATIENT PROFILE'}")
        print(f"  appointment_id: {apt_id}")
        print(f"  medical_record_id: {mr_id}")
        print(f"  uploaded_by: {uploader}")
        print(f"  Dr. Arjun authorized? {authorized} (Apt: {apt.get('appointment_id') if apt else None}, Consult: {cns.get('consultation_id') if cns else None})")
        
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(main())
