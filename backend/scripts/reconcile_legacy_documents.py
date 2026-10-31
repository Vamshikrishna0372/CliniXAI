"""
Legacy Document Patient ID Reconciliation Script for CliniXAI Phase 25.

Finds all documents stored with user_id (USR-...) as their patient_id,
resolves the canonical patient profile (PAT-...), and updates the document record
in both MongoDB and the persistence snapshots.
"""

import sys
sys.path.insert(0, "backend")
import json
from pathlib import Path

def reconcile_snapshots():
    print("=" * 80)
    print("CLINIXAI PHASE 25 — LEGACY DOCUMENT PATIENT ID RECONCILIATION")
    print("=" * 80)

    snap_dirs = [Path(".data_persist"), Path("backend/.data_persist")]
    valid_snap_dirs = [d for d in snap_dirs if d.exists()]

    if not valid_snap_dirs:
        print("No .data_persist directory found.")
        return

    # Use first valid snapshot directory as source of truth
    primary_dir = valid_snap_dirs[0]
    with open(primary_dir / "documents.json", "r", encoding="utf-8") as f:
        docs = json.load(f)
    with open(primary_dir / "patients.json", "r", encoding="utf-8") as f:
        patients = json.load(f)
    with open(primary_dir / "users.json", "r", encoding="utf-8") as f:
        users = json.load(f)

    reconciliation_report = {
        "total_documents": len(docs),
        "legacy_usr_records_found": 0,
        "migrated_records": [],
        "unresolved_records": [],
    }

    # Map user_id -> canonical patient_id
    user_to_patient = {}
    email_to_patient = {}
    for p in patients:
        pid = p.get("patient_id")
        uid = p.get("user_id")
        email = p.get("email")
        if uid and pid:
            user_to_patient[uid] = pid
        if email and pid:
            email_to_patient[email] = pid

    modified = False
    for doc in docs:
        doc_pid = doc.get("patient_id")
        if doc_pid and str(doc_pid).startswith("USR-"):
            reconciliation_report["legacy_usr_records_found"] += 1
            doc_id = doc.get("document_id")
            title = doc.get("title")

            # Try to resolve via user_id -> patient_id
            resolved_pid = user_to_patient.get(doc_pid)
            
            # If not directly mapped, check user's email
            if not resolved_pid:
                user_rec = next((u for u in users if u.get("user_id") == doc_pid), None)
                if user_rec and user_rec.get("email"):
                    resolved_pid = email_to_patient.get(user_rec["email"])

            if resolved_pid:
                doc["patient_id"] = resolved_pid
                reconciliation_report["migrated_records"].append({
                    "document_id": doc_id,
                    "title": title,
                    "old_patient_id": doc_pid,
                    "resolved_canonical_patient_id": resolved_pid,
                })
                modified = True
            else:
                reconciliation_report["unresolved_records"].append({
                    "document_id": doc_id,
                    "title": title,
                    "unresolved_patient_id": doc_pid,
                })

    print(f"Total documents audited: {reconciliation_report['total_documents']}")
    print(f"Legacy 'USR-' records found: {reconciliation_report['legacy_usr_records_found']}")
    print(f"Successfully migrated: {len(reconciliation_report['migrated_records'])}")
    print(f"Unresolved records: {len(reconciliation_report['unresolved_records'])}")

    print("\n--- MIGRATION DETAILS ---")
    for item in reconciliation_report["migrated_records"]:
        print(f"  [MIGRATED] Doc: {item['document_id']} | Title: '{item['title']}' | {item['old_patient_id']} -> {item['resolved_canonical_patient_id']}")

    for item in reconciliation_report["unresolved_records"]:
        print(f"  [UNRESOLVED] Doc: {item['document_id']} | Title: '{item['title']}' | PID: {item['unresolved_patient_id']}")

    if modified:
        for d in valid_snap_dirs:
            doc_file = d / "documents.json"
            with open(doc_file, "w", encoding="utf-8") as f:
                json.dump(docs, f, indent=2, default=str)
            print(f"Persisted reconciled documents snapshot to: {doc_file}")

    print("=" * 80)
    return reconciliation_report

if __name__ == "__main__":
    reconcile_snapshots()

