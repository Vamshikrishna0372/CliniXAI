# CliniXAI Backend — Production Architecture & Complete Feature Reference

> **AI-Powered Hospital Management & Clinical Decision Support Platform**

Production-ready FastAPI and MongoDB backend architecture for CliniXAI featuring four-role RBAC, Authentication, Core Hospital Operations, Doctor Clinical Decision Support, Medical Documents & Secure Files, Billing & Payments, Multi-Model ResNet50 + Grad-CAM Explainable AI, Audit Logging, Follow-ups, Unified Search Engine, Aggregated Clinical Timeline, Soft-Delete & Restore Management, and Health Monitoring.

---

## 🛠️ Technology Stack

* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
* **Server**: [Uvicorn](https://www.uvicorn.org/)
* **Database**: [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) / Local MongoDB
* **Async MongoDB Driver**: [Motor](https://motor.readthedocs.io/) & [PyMongo](https://pymongo.readthedocs.io/)
* **Password Hashing**: [Passlib](https://passlib.readthedocs.io/) + [Bcrypt](https://pypi.org/project/bcrypt/)
* **Authentication Tokens**: [PyJWT](https://pyjwt.readthedocs.io/) (JWT Access & Refresh tokens)
* **Configuration**: [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
* **QR Generation**: [qrcode](https://pypi.org/project/qrcode/) + [Pillow](https://pypi.org/project/pillow/)
* **Testing**: `pytest`, `unittest`, `httpx`

---

## 📁 Repository Architecture

```text
CliniXAI/backend/
├── app/
│   ├── main.py                     # FastAPI setup, lifespan, RateLimiter & Security middleware
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # API v1 consolidated router
│   │       └── routes/
│   │           ├── health.py       # Health, Liveness, and Readiness endpoints
│   │           ├── auth.py         # Authentication, Registration, Password & Verification
│   │           ├── patients.py     # Patient self profile, search & Clinical Timeline
│   │           ├── departments.py  # Department management & soft status
│   │           ├── doctors.py      # Doctor provisioning, profile & slot availability
│   │           ├── staff.py        # Hospital Staff management
│   │           ├── appointments.py # Booking, Rescheduling, Check-In & Queue
│   │           ├── consultations.py# Doctor consultation workspace & completions
│   │           ├── prescriptions.py# Doctor prescription issuing & follow-ups
│   │           ├── medical_records.py# Medical record upload & secure file access
│   │           ├── billing.py      # Billing, Payments & Receipts
│   │           ├── notifications.py# Inbox notifications
│   │           ├── follow_ups.py   # Patient follow-up appointment tracking
│   │           ├── documents.py    # Medical document uploads, metadata & streaming
│   │           ├── audit_logs.py   # Security & operational audit logs (Admin)
│   │           ├── search.py       # Unified multi-resource backend search engine
│   │           ├── admin.py        # Soft-delete list, restore, and permanent purge
│   │           ├── ai_analyses.py  # Multi-model AI inference, Grad-CAM & Doctor review
│   │           ├── integrations.py # Google OAuth, Calendar, Location & Status
│   │           └── qr.py           # Patient & Appointment QR tokens, images & QR check-in
│   ├── core/
│   │   ├── config.py               # Settings management & env validation
│   │   ├── logging.py              # Structured logging
│   │   ├── exceptions.py           # Custom exception hierarchy & exception handler
│   │   ├── security.py             # Bcrypt hashing & JWT token handling
│   │   └── middleware.py           # Security headers & timing middleware
│   ├── database/
│   │   ├── collections.py          # All 16 MongoDB collection constants
│   │   ├── indexes.py              # Automated MongoDB collection indexes
│   │   └── mongodb.py              # Async Motor database connection pool
│   ├── models/
│   │   └── ...                     # Domain Pydantic & Mongo models (including soft delete fields)
│   ├── schemas/
│   │   └── ...                     # API Request and Response Pydantic schemas
│   ├── services/
│   │   ├── auth_service.py         # Authentication & user sessions
│   │   ├── patient_service.py      # Patient operations
│   │   ├── doctor_service.py       # Doctor & slot availability
│   │   ├── appointment_service.py  # Booking, state machine & double-booking prevention
│   │   ├── follow_up_service.py    # Follow-up lifecycle
│   │   ├── document_service.py     # Medical documents upload, validation & streaming
│   │   ├── audit_service.py        # Persistent audit logging
│   │   ├── search_service.py       # Unified backend search across collections
│   │   ├── timeline_service.py     # Aggregated clinical timeline
│   │   └── ai_service.py           # AI inference & doctor review workflow
│   └── utils/
│       └── ...                     # File validation, ID generators, tokens, datetime utilities
├── tests/
│   ├── test_all.py                 # Core master runner
│   ├── test_backend_complete.py    # Complete backend verification test suite
│   └── ...                         # Feature test suites
├── .env.example                    # Environment variable template
├── requirements.txt                # Python dependencies
└── README.md                       # Documentation
```

---

## 🔒 Security, Authentication & Role-Based Authorization

1. **Four Core Roles**: `Patient`, `Doctor`, `Hospital Staff`, `Hospital Admin` (with alias support for `Admin` and `Staff`).
2. **Patient Isolation**: Patients are restricted to accessing only their own profile, appointments, consultations, prescriptions, medical records, billing, notifications, documents, follow-ups, and timeline.
3. **Insecure Direct Object Reference (IDOR) Protection**: Resource access is verified against ownership or explicit clinical relationships.
4. **Audit Logging**: Sensitive operations (login, logout, patient updates, appointment state changes, prescriptions, AI reviews, billing, document uploads, soft-deletes, restores) are persistently logged to `audit_logs` with actor ID, role, IP, timestamp, and metadata.

---

## 🤖 AI Multi-Model Subsystem & Explainable AI (XAI)

1. **Supported Modules**:
   - `CHEST_XRAY`: Chest X-Ray Analysis (`chest_model.keras`)
   - `BRAIN_MRI`: Brain MRI Tumor Classification (`brain_model.keras`)
   - `SKIN_DERMOSCOPY`: Skin Dermoscopy Lesion Analysis (`skin_model.keras`)
   - `RETINAL_FUNDUS`: Retinal Fundus Screening (`eye_model.keras`)
   - `BONE_XRAY`: Bone X-Ray Fracture Detection (`bone_model.keras`)
2. **Missing Model Graceful Fallback**: Server starts safely and reports model availability status via `GET /api/v1/ai/health` and `GET /api/v1/ai/models`. Missing `.keras` files return clear error metadata without crashing the system.
3. **Explainable AI (Grad-CAM)**: Generates spatial activation heatmaps overlaid on input medical images for loaded models.
4. **Doctor AI Review Workflow**: Doctor evaluates AI prediction (`Accepted`, `Rejected`, `Needs Further Review`, `Accepted as Supporting`) and attaches clinical notes.

---

## 🧪 Comprehensive Testing

Run the full automated backend test suite:

```bash
python -m pytest backend/tests
```

