"""Billing & Payment Business Logic Service for CliniXAI Phase 16."""

import asyncio
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError
)
from app.database.collections import (
    COLLECTION_BILLING, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PAYMENTS
)
from app.models.billing import (
    BillingInDB, BillingStatus, BillLineItem, PaymentRecord, PaymentStatus, PaymentMethod
)
from app.models.notification import NotificationType
from app.models.user import UserInDB, UserRole
from app.schemas.billing import (
    CreateBillRequest, AddLineItemRequest, RecordPaymentRequest, VoidPaymentRequest, CancelBillRequest
)
from app.services.notification_service import NotificationService
from app.services.audit_service import log_audit_event
from app.utils.id_generator import generate_bill_id, generate_payment_id
from app.utils.datetime import utc_now

from pymongo import ReturnDocument

# Statuses that allow mutation
_MUTABLE_STATUSES = {BillingStatus.DRAFT, BillingStatus.ISSUED, BillingStatus.PARTIALLY_PAID}


class BillingService:
    """Core billing management, payment recording, and receipt service."""

    @staticmethod
    async def _find_by_bill_id(db: AsyncIOMotorDatabase, bill_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_BILLING].find_one({"bill_id": bill_id})
        if not doc:
            raise ResourceNotFoundError("Bill", bill_id)
        doc.pop("_id", None)
        return doc

    @staticmethod
    def _assert_mutable(bill: Dict[str, Any]) -> None:
        """Raises AppValidationError if the bill is in a terminal state."""
        if bill["status"] not in {s.value for s in _MUTABLE_STATUSES}:
            raise AppValidationError(
                f"Bill '{bill['bill_id']}' is in status '{bill['status']}' and cannot be modified."
            )

    @staticmethod
    def _assert_admin_or_staff(current_user: UserInDB) -> None:
        """Enforces that only Hospital Admin or Staff can author financial mutations."""
        if current_user.role not in (UserRole.HOSPITAL_ADMIN, UserRole.HOSPITAL_STAFF):
            raise ForbiddenError("Only Hospital Admin or Staff can perform this billing operation.")

    # ── Create Bill ────────────────────────────────────────────────────────────

    @staticmethod
    async def create_bill(
        db: AsyncIOMotorDatabase,
        request: CreateBillRequest,
        current_user: UserInDB,
    ) -> BillingInDB:
        """Creates a new patient billing record in DRAFT status."""
        BillingService._assert_admin_or_staff(current_user)

        # Idempotency check via idempotency_key
        if request.idempotency_key:
            existing_by_key = await db[COLLECTION_BILLING].find_one(
                {"idempotency_key": request.idempotency_key, "is_deleted": {"$ne": True}}
            )
            if existing_by_key:
                existing_by_key.pop("_id", None)
                return BillingInDB(**existing_by_key)

        patient_id = request.patient_id
        doctor_id: Optional[str] = None
        department_id: Optional[str] = None

        if request.consultation_id:
            consult = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": request.consultation_id})
            if not consult:
                raise ResourceNotFoundError("Consultation", request.consultation_id)
            if consult.get("status") == "cancelled":
                raise AppValidationError("Cannot create bill for a cancelled consultation.")
            
            # Derive or verify patient_id
            if not patient_id:
                patient_id = consult["patient_id"]
            elif consult["patient_id"] != patient_id:
                raise AppValidationError("Consultation does not belong to the specified patient.")
            
            doctor_id = consult.get("doctor_id")
            department_id = consult.get("department_id")

            # Check if active bill already exists for this consultation (Idempotency / duplicate protection)
            existing_consult_bill = await db[COLLECTION_BILLING].find_one(
                {
                    "consultation_id": request.consultation_id,
                    "status": {"$ne": BillingStatus.CANCELLED.value},
                    "is_deleted": {"$ne": True}
                }
            )
            if existing_consult_bill:
                existing_consult_bill.pop("_id", None)
                logger.info(f"Returning existing bill {existing_consult_bill['bill_id']} for consultation {request.consultation_id}")
                return BillingInDB(**existing_consult_bill)

        if request.appointment_id:
            apt = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": request.appointment_id})
            if not apt:
                raise ResourceNotFoundError("Appointment", request.appointment_id)
            if not patient_id:
                patient_id = apt["patient_id"]
            elif apt["patient_id"] != patient_id:
                raise AppValidationError("Appointment does not belong to the specified patient.")
            doctor_id = doctor_id or apt.get("doctor_id")
            department_id = department_id or apt.get("department_id")

        if not patient_id:
            raise AppValidationError("patient_id is required to create a bill.")

        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
        if not patient:
            raise ResourceNotFoundError("Patient", patient_id)

        # Build line items
        line_items = [
            BillLineItem(
                item_code=li.item_code or f"ITEM-{idx+1:03d}",
                description=li.description.strip(),
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_percent=li.tax_percent,
                discount_amount=li.discount_amount,
            )
            for idx, li in enumerate(request.line_items)
        ]

        subtotal = round(sum(li.subtotal for li in line_items), 2)
        total_discount = round(sum(li.discount_amount for li in line_items) + (request.discount or 0.0), 2)
        if total_discount > subtotal:
            raise AppValidationError("Total discount cannot exceed subtotal.")

        now = utc_now()
        bill = BillingInDB(
            bill_id=generate_bill_id(),
            patient_id=patient_id,
            appointment_id=request.appointment_id,
            consultation_id=request.consultation_id,
            prescription_id=request.prescription_id,
            department_id=department_id,
            doctor_id=doctor_id,
            line_items=line_items,
            discount=request.discount or 0.0,
            notes=request.notes.strip() if request.notes else None,
            idempotency_key=request.idempotency_key,
            status=BillingStatus.DRAFT,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        bill.recalculate_totals()

        await db[COLLECTION_BILLING].insert_one(bill.to_mongo_dict())

        # Audit log
        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="billing.created",
                resource="billing",
                resource_id=bill.bill_id,
                metadata={"patient_id": patient_id, "grand_total": bill.grand_total, "status": bill.status.value},
            )
        except Exception as audit_err:
            logger.warning(f"Failed to log audit event for bill creation: {audit_err}")

        # Snapshot save
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(f"Created Bill {bill.bill_id} for Patient {patient_id}. Total: INR {bill.grand_total}")
        return bill

    # ── Auto Create Bill from Consultation ─────────────────────────────────────

    @staticmethod
    async def create_bill_from_consultation(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        current_user: UserInDB,
    ) -> BillingInDB:
        """Automatically generates a bill using Doctor's consultation fee from completed consultation."""
        consultation = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": consultation_id})
        if not consultation:
            raise ResourceNotFoundError("Consultation", consultation_id)

        existing = await db[COLLECTION_BILLING].find_one(
            {"consultation_id": consultation_id, "status": {"$ne": BillingStatus.CANCELLED.value}, "is_deleted": {"$ne": True}}
        )
        if existing:
            existing.pop("_id", None)
            return BillingInDB(**existing)

        patient_id = consultation["patient_id"]
        doctor_id = consultation.get("doctor_id")
        appointment_id = consultation.get("appointment_id")
        department_id = consultation.get("department_id")

        if not department_id and appointment_id:
            apt = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": appointment_id})
            if apt:
                department_id = apt.get("department_id")

        consultation_fee = 500.0
        doctor_name = "Doctor Consultation"
        if doctor_id:
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": doctor_id})
            if doc:
                consultation_fee = float(doc.get("consultation_fee", 500.0))
                doc_last_name = doc.get("last_name") or doc.get("name") or "Doctor"
                doctor_name = f"Consultation Fee - Dr. {doc_last_name}"

        line_items = [
            BillLineItem(
                item_code="CONS-FEE",
                description=doctor_name,
                quantity=1.0,
                unit_price=consultation_fee,
                tax_percent=0.0,
                discount_amount=0.0,
            )
        ]

        now = utc_now()
        bill = BillingInDB(
            bill_id=generate_bill_id(),
            patient_id=patient_id,
            appointment_id=appointment_id,
            consultation_id=consultation_id,
            prescription_id=consultation.get("prescription_id"),
            department_id=department_id,
            doctor_id=doctor_id,
            line_items=line_items,
            notes=f"Auto-generated bill for Consultation {consultation_id}",
            status=BillingStatus.ISSUED,
            issued_at=now,
            created_by=current_user.user_id,
            created_at=now,
            updated_at=now,
        )
        bill.recalculate_totals()

        await db[COLLECTION_BILLING].insert_one(bill.to_mongo_dict())

        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="billing.created",
                resource="billing",
                resource_id=bill.bill_id,
                metadata={"consultation_id": consultation_id, "grand_total": bill.grand_total},
            )
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="billing.issued",
                resource="billing",
                resource_id=bill.bill_id,
                metadata={"consultation_id": consultation_id, "grand_total": bill.grand_total},
            )
        except Exception:
            pass

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(f"Auto-created Bill {bill.bill_id} from Consultation {consultation_id} for Patient {patient_id}. Total: INR {bill.grand_total}")
        return bill

    # ── Issue Bill ─────────────────────────────────────────────────────────────

    @staticmethod
    async def issue_bill(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Transitions bill from DRAFT → ISSUED and dispatches notification to patient."""
        BillingService._assert_admin_or_staff(current_user)
        bill = await BillingService._find_by_bill_id(db, bill_id)

        if bill["status"] != BillingStatus.DRAFT.value:
            raise AppValidationError(f"Only DRAFT bills can be issued. Current status: '{bill['status']}'.")
        if not bill.get("line_items"):
            raise AppValidationError("Cannot issue a bill with no line items.")

        now = utc_now()
        await db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {"status": BillingStatus.ISSUED.value, "issued_at": now, "updated_at": now}},
        )

        # Look up patient user_id for notification
        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": bill["patient_id"]})
        if patient and patient.get("user_id"):
            await NotificationService.dispatch(
                db,
                recipient_user_id=patient["user_id"],
                notification_type=NotificationType.BILL_ISSUED,
                title="Bill Issued",
                body=f"Your bill {bill_id} for INR {bill['grand_total']:.2f} has been issued.",
                reference_id=bill_id,
                reference_type="billing",
                dedupe_key=f"bill_issued:{bill_id}:{patient['user_id']}",
            )

        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="billing.issued",
                resource="billing",
                resource_id=bill_id,
                metadata={"patient_id": bill["patient_id"], "grand_total": bill["grand_total"]},
            )
        except Exception:
            pass

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(f"Bill {bill_id} issued by {current_user.user_id}")
        return await BillingService._find_by_bill_id(db, bill_id)

    # ── Add Line Item ──────────────────────────────────────────────────────────

    @staticmethod
    async def add_line_item(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        request: AddLineItemRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Appends a line item to an existing mutable bill and recalculates totals."""
        BillingService._assert_admin_or_staff(current_user)
        bill = await BillingService._find_by_bill_id(db, bill_id)
        BillingService._assert_mutable(bill)

        new_item = BillLineItem(
            item_code=request.item_code or f"ITEM-{len(bill.get('line_items', []))+1:03d}",
            description=request.description.strip(),
            quantity=request.quantity,
            unit_price=request.unit_price,
            tax_percent=request.tax_percent,
            discount_amount=request.discount_amount,
        )

        billing_obj = BillingInDB(**bill)
        billing_obj.line_items.append(new_item)
        billing_obj.recalculate_totals()
        billing_obj.updated_at = utc_now()

        await db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "line_items": [li.model_dump() for li in billing_obj.line_items],
                "subtotal": billing_obj.subtotal,
                "total_tax": billing_obj.total_tax,
                "total_discount": billing_obj.total_discount,
                "discount": billing_obj.discount,
                "grand_total": billing_obj.grand_total,
                "total_amount": billing_obj.total_amount,
                "balance_due": billing_obj.balance_due,
                "balance_amount": billing_obj.balance_amount,
                "updated_at": billing_obj.updated_at,
            }},
        )

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        return await BillingService._find_by_bill_id(db, bill_id)

    # ── Record Payment ─────────────────────────────────────────────────────────

    @staticmethod
    async def record_payment(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        request: RecordPaymentRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Records an offline payment transaction (Cash, UPI, Card) against a bill.
        
        Strictly restricted to Hospital Staff and Admin.
        Enforces MongoDB database-level atomic conditional updates ensuring:
          balance_due >= payment.amount
          amount_paid + payment.amount <= total_amount
        Operates thread-safely and multi-process safely without in-memory lock dependencies.
        """
        BillingService._assert_admin_or_staff(current_user)

        amount = round(request.amount, 2)
        if amount <= 0.0:
            raise AppValidationError("Payment amount must be a positive finite number greater than zero.")

        ref_to_check = request.reference_number or request.reference
        idempotency_key = request.idempotency_key

        # 1. Idempotency Key check: ensure same key + same operation returns cached result; conflicting payload is rejected
        if idempotency_key:
            existing_pmt = await db[COLLECTION_PAYMENTS].find_one({"idempotency_key": idempotency_key})
            if existing_pmt:
                # Validate matching payload
                is_same_bill = (existing_pmt.get("bill_id") == bill_id)
                is_same_amount = (abs(existing_pmt.get("amount", 0.0) - amount) < 0.005)
                is_same_method = (existing_pmt.get("method") == request.method.value)
                if is_same_bill and is_same_amount and is_same_method:
                    logger.info(f"Idempotent payment replay for key {idempotency_key} on bill {bill_id}.")
                    return await BillingService._find_by_bill_id(db, bill_id)
                else:
                    raise ResourceConflictError(
                        f"Idempotency key '{idempotency_key}' conflict: payload does not match original payment "
                        f"(original bill: {existing_pmt.get('bill_id')}, amount: {existing_pmt.get('amount')}, method: {existing_pmt.get('method')})."
                    )

        # 2. Check duplicate reference number for offline UPI/Card transactions
        if ref_to_check:
            existing_ref = await db[COLLECTION_PAYMENTS].find_one({
                "bill_id": bill_id,
                "reference_number": ref_to_check,
                "status": {"$in": [PaymentStatus.COMPLETED.value, PaymentStatus.RECORDED.value]},
            })
            if existing_ref:
                logger.info(f"Duplicate payment reference {ref_to_check} detected on bill {bill_id}. Idempotent return.")
                return await BillingService._find_by_bill_id(db, bill_id)

        # 3. Read current bill for initial checks & auto-issuance
        bill = await BillingService._find_by_bill_id(db, bill_id)

        # Check existing payments embedded in the bill
        for pmt in bill.get("payments", []):
            if pmt.get("status") in (PaymentStatus.COMPLETED.value, PaymentStatus.RECORDED.value):
                if ref_to_check and (pmt.get("reference_number") == ref_to_check or pmt.get("reference") == ref_to_check):
                    logger.info(f"Duplicate payment reference {ref_to_check} detected on bill {bill_id}. Idempotent return.")
                    return bill
                if idempotency_key and pmt.get("idempotency_key") == idempotency_key:
                    logger.info(f"Duplicate payment idempotency_key {idempotency_key} detected on bill {bill_id}. Idempotent return.")
                    return bill

        if bill.get("status") == BillingStatus.CANCELLED.value:
            raise AppValidationError(f"Cannot record payment on cancelled bill '{bill_id}'.")

        # Auto-issue draft bill if receiving payment
        if bill.get("status") == BillingStatus.DRAFT.value:
            now_issue = utc_now()
            await db[COLLECTION_BILLING].update_one(
                {"bill_id": bill_id, "status": BillingStatus.DRAFT.value},
                {"$set": {"status": BillingStatus.ISSUED.value, "issued_at": now_issue, "updated_at": now_issue}},
            )
            bill["status"] = BillingStatus.ISSUED.value

        balance_due = bill.get("balance_due", bill.get("balance_amount", bill.get("grand_total", 0.0)))
        if bill.get("status") == BillingStatus.PAID.value or balance_due <= 0.0:
            raise AppValidationError(f"Bill '{bill_id}' is already fully paid.")

        if amount > round(balance_due + 0.005, 2):
            raise AppValidationError(
                f"Payment amount INR {amount:.2f} exceeds balance due INR {balance_due:.2f}."
            )

        now = utc_now()
        payment_id = generate_payment_id()
        payment = PaymentRecord(
            payment_id=payment_id,
            bill_id=bill_id,
            patient_id=bill["patient_id"],
            amount=amount,
            method=request.method,
            status=PaymentStatus.COMPLETED,
            reference_number=ref_to_check,
            reference=ref_to_check,
            idempotency_key=idempotency_key,
            notes=request.notes.strip() if request.notes else None,
            paid_at=now,
            recorded_at=now,
            recorded_by=current_user.user_id,
        )

        # 4. DATABASE-LEVEL ATOMIC CONDITIONAL UPDATE ON MONGODB
        # Invariant enforced: balance_due >= amount - 0.005, status in (DRAFT, ISSUED, PARTIALLY_PAID), not deleted
        min_balance_due = round(amount - 0.005, 2)
        atomic_filter = {
            "bill_id": bill_id,
            "status": {"$in": [BillingStatus.DRAFT.value, BillingStatus.ISSUED.value, BillingStatus.PARTIALLY_PAID.value]},
            "is_deleted": {"$ne": True},
            "balance_due": {"$gte": min_balance_due},
        }
        atomic_update = {
            "$inc": {
                "amount_paid": amount,
                "paid_amount": amount,
                "balance_due": -amount,
                "balance_amount": -amount,
            },
            "$push": {
                "payments": payment.model_dump()
            },
            "$set": {
                "updated_at": now
            }
        }

        updated_bill = await db[COLLECTION_BILLING].find_one_and_update(
            atomic_filter,
            atomic_update,
            return_document=ReturnDocument.AFTER
        )

        # If atomic conditional update returned None, check why and raise descriptive validation error
        if not updated_bill:
            latest = await db[COLLECTION_BILLING].find_one({"bill_id": bill_id})
            if not latest:
                raise ResourceNotFoundError("Bill", bill_id)
            if latest.get("status") == BillingStatus.CANCELLED.value:
                raise AppValidationError(f"Cannot record payment on cancelled bill '{bill_id}'.")
            if latest.get("status") == BillingStatus.PAID.value or latest.get("balance_due", 0.0) <= 0.0:
                raise AppValidationError(f"Bill '{bill_id}' is already fully paid.")
            cur_bal = latest.get("balance_due", 0.0)
            if amount > round(cur_bal + 0.005, 2):
                raise AppValidationError(
                    f"Payment amount INR {amount:.2f} exceeds remaining balance due INR {cur_bal:.2f}."
                )
            raise AppValidationError("Concurrent payment conflict detected; please retry payment.")

        # 5. Fine-tune status and precision rounding
        rem_balance = updated_bill.get("balance_due", 0.0)
        grand_total = updated_bill.get("grand_total", updated_bill.get("total_amount", 0.0))
        if rem_balance <= 0.005:
            new_status = BillingStatus.PAID.value
            final_balance = 0.0
            final_paid = round(grand_total, 2)
        else:
            new_status = BillingStatus.PARTIALLY_PAID.value
            final_balance = round(rem_balance, 2)
            final_paid = round(updated_bill.get("amount_paid", 0.0), 2)

        await db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "status": new_status,
                "balance_due": final_balance,
                "balance_amount": final_balance,
                "amount_paid": final_paid,
                "paid_amount": final_paid,
                "updated_at": now,
            }}
        )

        # 6. Insert payment document into authoritative payments collection
        try:
            await db[COLLECTION_PAYMENTS].insert_one(payment.model_dump())
        except Exception as exc:
            logger.error(f"Failed to write payment document {payment_id}: {exc}")
            # Compensating transaction: roll back the atomic update on bill
            await db[COLLECTION_BILLING].update_one(
                {"bill_id": bill_id},
                {
                    "$pull": {"payments": {"payment_id": payment_id}},
                    "$inc": {
                        "amount_paid": -amount,
                        "paid_amount": -amount,
                        "balance_due": amount,
                        "balance_amount": amount,
                    },
                    "$set": {
                        "status": bill.get("status", BillingStatus.ISSUED.value),
                        "updated_at": utc_now(),
                    }
                }
            )
            raise

        # 7. Patient Notification
        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": bill["patient_id"]})
        if patient and patient.get("user_id"):
            await NotificationService.dispatch(
                db,
                recipient_user_id=patient["user_id"],
                notification_type=NotificationType.PAYMENT_RECEIVED,
                title="Payment Received",
                body=f"Payment of INR {amount:.2f} via {request.method.value.upper()} received for Bill {bill_id}. Balance due: INR {final_balance:.2f}.",
                reference_id=bill_id,
                reference_type="billing",
                dedupe_key=f"payment_recorded:{payment_id}:{patient['user_id']}",
            )

        # 8. Audit log
        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="payment.recorded",
                resource="billing",
                resource_id=bill_id,
                metadata={
                    "payment_id": payment.payment_id,
                    "amount": amount,
                    "method": request.method.value,
                    "new_balance": final_balance,
                    "new_status": new_status,
                },
            )
        except Exception as exc_audit:
            logger.warning(f"Failed to record audit event for payment {payment.payment_id}: {exc_audit}")

        # 9. Snapshot persistence
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(
            f"Payment {payment.payment_id} of INR {amount} recorded for Bill {bill_id}. "
            f"Status: {new_status}, Balance: INR {final_balance}"
        )
        return await BillingService._find_by_bill_id(db, bill_id)

    # ── Void Payment ───────────────────────────────────────────────────────────

    @staticmethod
    async def void_payment(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        payment_id: str,
        request: VoidPaymentRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Voids an existing payment and recalculates the bill balance and status.
        
        Enforces MongoDB database-level atomic conditional transition ensuring:
          payment.status != 'voided'
        Multi-process and concurrent void requests cannot double-subtract or corrupt balances.
        """
        BillingService._assert_admin_or_staff(current_user)

        if not request.reason or not request.reason.strip():
            raise AppValidationError("A non-empty justification reason is required to void a payment.")

        now = utc_now()

        # 1. DATABASE-LEVEL ATOMIC CONDITIONAL UPDATE ON PAYMENTS
        # Only succeeds if the payment exists, matches the bill, and is NOT already voided
        voided_payment_doc = await db[COLLECTION_PAYMENTS].find_one_and_update(
            {
                "payment_id": payment_id,
                "bill_id": bill_id,
                "status": {"$ne": PaymentStatus.VOIDED.value},
            },
            {
                "$set": {
                    "status": PaymentStatus.VOIDED.value,
                    "voided_at": now,
                    "voided_by": current_user.user_id,
                    "void_reason": request.reason.strip(),
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.BEFORE,
        )

        if not voided_payment_doc:
            # Check why:
            existing_pmt = await db[COLLECTION_PAYMENTS].find_one({"payment_id": payment_id})
            if not existing_pmt:
                raise ResourceNotFoundError("Payment", payment_id)
            if existing_pmt.get("status") == PaymentStatus.VOIDED.value:
                raise AppValidationError(f"Payment '{payment_id}' is already voided.")
            if existing_pmt.get("bill_id") != bill_id:
                raise AppValidationError(f"Payment '{payment_id}' does not belong to Bill '{bill_id}'.")
            raise AppValidationError(f"Payment '{payment_id}' cannot be voided.")

        # 2. Update the parent bill: mark payment VOIDED in embedded array and recompute totals
        bill = await BillingService._find_by_bill_id(db, bill_id)
        billing_obj = BillingInDB(**bill)
        for p in billing_obj.payments:
            if p.payment_id == payment_id:
                p.status = PaymentStatus.VOIDED
                p.voided_at = now
                p.voided_by = current_user.user_id
                p.void_reason = request.reason.strip()
                break

        billing_obj.recalculate_totals()
        billing_obj.updated_at = now

        if billing_obj.balance_due <= 0.0:
            billing_obj.status = BillingStatus.PAID
        elif billing_obj.amount_paid > 0.0:
            billing_obj.status = BillingStatus.PARTIALLY_PAID
        else:
            billing_obj.status = BillingStatus.ISSUED

        await db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "payments": [p.model_dump() for p in billing_obj.payments],
                "amount_paid": billing_obj.amount_paid,
                "paid_amount": billing_obj.paid_amount,
                "balance_due": billing_obj.balance_due,
                "balance_amount": billing_obj.balance_amount,
                "status": billing_obj.status.value,
                "updated_at": billing_obj.updated_at,
            }}
        )

        # 3. Audit log
        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="payment.voided",
                resource="billing",
                resource_id=bill_id,
                metadata={"payment_id": payment_id, "reason": request.reason},
            )
        except Exception:
            pass

        # 4. Patient Notification
        try:
            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": billing_obj.patient_id})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.PAYMENT_VOIDED,
                    title="Payment Voided",
                    body=f"Payment {payment_id} for Bill {bill_id} has been voided. Reason: {request.reason.strip()}.",
                    reference_id=bill_id,
                    reference_type="billing",
                    dedupe_key=f"payment_voided:{payment_id}:{patient['user_id']}",
                )
        except Exception as notif_err:
            logger.warning(f"Failed to dispatch void payment notification for {payment_id}: {notif_err}")

        # 5. Snapshot persistence
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(f"Payment {payment_id} voided by {current_user.user_id}. Bill {bill_id} status: {billing_obj.status.value}")
        return await BillingService._find_by_bill_id(db, bill_id)

    # ── Cancel Bill ────────────────────────────────────────────────────────────

    @staticmethod
    async def cancel_bill(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        current_user: UserInDB,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancels a bill that has not been paid."""
        BillingService._assert_admin_or_staff(current_user)
        bill = await BillingService._find_by_bill_id(db, bill_id)

        if bill["status"] == BillingStatus.PAID.value:
            raise AppValidationError("Paid bills cannot be cancelled. Issue a refund instead.")
        if bill["status"] == BillingStatus.CANCELLED.value:
            raise AppValidationError("Bill is already cancelled.")

        # Check for recorded non-voided payments
        active_payments = [
            p for p in bill.get("payments", [])
            if p.get("status") in (PaymentStatus.COMPLETED.value, PaymentStatus.RECORDED.value)
        ]
        if active_payments:
            raise AppValidationError("Cannot cancel a bill with recorded active payments. Void payments first.")

        now = utc_now()
        await db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "status": BillingStatus.CANCELLED.value,
                "cancelled_at": now,
                "cancelled_by": current_user.user_id,
                "cancellation_reason": reason or "Cancelled by hospital staff",
                "updated_at": now,
            }},
        )

        try:
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="billing.cancelled",
                resource="billing",
                resource_id=bill_id,
                metadata={"reason": reason},
            )
        except Exception:
            pass

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        logger.info(f"Bill {bill_id} cancelled by {current_user.user_id}")
        return await BillingService._find_by_bill_id(db, bill_id)

    # ── List Bills ─────────────────────────────────────────────────────────────

    @staticmethod
    async def list_bills(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        patient_id: Optional[str] = None,
        status: Optional[BillingStatus] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Role-aware bill listing."""
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return [], 0
            # Strict isolation: Patient can ONLY query their own bills
            query["patient_id"] = patient["patient_id"]
        elif current_user.role == UserRole.DOCTOR:
            # Doctor read-only visibility into their patients' bills
            if patient_id:
                query["patient_id"] = patient_id
            else:
                doc = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
                if doc:
                    query["$or"] = [
                        {"doctor_id": doc["doctor_id"]},
                        {"doctor_id": current_user.user_id}
                    ]
        elif patient_id:
            query["patient_id"] = patient_id

        if status:
            query["status"] = status.value

        skip = (page - 1) * page_size
        total = await db[COLLECTION_BILLING].count_documents(query)
        cursor = db[COLLECTION_BILLING].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        for doc in docs:
            doc.pop("_id", None)
            # Ensure alias synchronization
            doc["total_amount"] = doc.get("total_amount") or doc.get("grand_total", 0.0)
            doc["paid_amount"] = doc.get("paid_amount") or doc.get("amount_paid", 0.0)
            doc["balance_amount"] = doc.get("balance_amount") or doc.get("balance_due", 0.0)
        return docs, total

    # ── Get Bill ───────────────────────────────────────────────────────────────

    @staticmethod
    async def get_bill_by_id(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Fetch bill with object-level auth."""
        bill = await BillingService._find_by_bill_id(db, bill_id)

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != bill["patient_id"]:
                raise ForbiddenError("You are not authorized to view this bill.")

        # Ensure alias synchronization
        bill["total_amount"] = bill.get("total_amount") or bill.get("grand_total", 0.0)
        bill["paid_amount"] = bill.get("paid_amount") or bill.get("amount_paid", 0.0)
        bill["balance_amount"] = bill.get("balance_amount") or bill.get("balance_due", 0.0)
        bill["discount"] = bill.get("discount") or bill.get("total_discount", 0.0)
        return bill

    # ── Receipt Retrieval ─────────────────────────────────────────────────────

    @staticmethod
    async def get_receipt_data(
        db: AsyncIOMotorDatabase,
        bill_id: str,
        payment_id: Optional[str],
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Returns structured receipt payload for payment transaction / bill."""
        bill = await BillingService.get_bill_by_id(db, bill_id, current_user)
        payments = [
            p for p in bill.get("payments", [])
            if p.get("status") in (PaymentStatus.COMPLETED.value, PaymentStatus.RECORDED.value)
        ]
        if not payments:
            raise AppValidationError(f"No completed payment recorded for bill '{bill_id}'. Cannot generate receipt.")

        target_payment = payments[-1]
        if payment_id:
            for p in payments:
                if p["payment_id"] == payment_id:
                    target_payment = p
                    break

        receipt_id = f"RCT-{target_payment['payment_id'].replace('PAY-', '')}"

        return {
            "receipt_id": receipt_id,
            "bill_id": bill_id,
            "patient_id": bill["patient_id"],
            "payment_id": target_payment["payment_id"],
            "amount_paid": target_payment["amount"],
            "payment_method": target_payment["method"],
            "reference_number": target_payment.get("reference_number") or target_payment.get("reference"),
            "grand_total": bill["grand_total"],
            "total_amount": bill.get("total_amount", bill["grand_total"]),
            "balance_due": bill["balance_due"],
            "balance_amount": bill.get("balance_amount", bill["balance_due"]),
            "status": bill["status"],
            "currency": "INR",
            "issued_at": target_payment.get("paid_at") or target_payment.get("recorded_at"),
            "issued_by": target_payment["recorded_by"],
        }
