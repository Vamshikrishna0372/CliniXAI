# CliniXAI — Production Deployment & Operational Runbook

This guide details the procedure for deploying the **CliniXAI** platform to production environments, including FastAPI backend, React frontend, MongoDB Atlas database, and the Brain MRI AI inference pipeline.

---

## 1. System Architecture & Components

```
                    ┌─────────────────────────┐
                    │    React / Vite SPA     │
                    │   (Production Web UI)   │
                    └────────────┬────────────┘
                                 │ HTTP/HTTPS (JWT Auth)
                                 ▼
                    ┌─────────────────────────┐
                    │      FastAPI API        │
                    │   (ASGI App Server)     │
                    └────┬──────────────┬─────┘
                         │              │
        MongoDB Driver   │              │ TensorFlow Keras API
        (Motor AsyncIO)  ▼              ▼
     ┌──────────────────────┐  ┌──────────────────────┐
     │  MongoDB Atlas DB    │  │ Brain MRI AI Model   │
     │  (TLS, Indexes, ACL) │  │ (ResNet50 + GradCAM) │
     └──────────────────────┘  └──────────────────────┘
```

---

## 2. Environment Configuration

### A. Backend (`.env`)

Copy `backend/.env.example` to `backend/.env` on your production application server and configure:

| Variable | Recommended Production Value | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Suppresses dev stack traces and enables strict error handling |
| `DEBUG` | `false` | Must be false in production |
| `MONGODB_URI` | `mongodb+srv://<user>:<password>@cluster.mongodb.net/clinixai?retryWrites=true&w=majority` | MongoDB Atlas Connection String |
| `MONGODB_DB_NAME` | `clinixai` | Primary database name |
| `JWT_SECRET_KEY` | `<256-bit cryptographically secure string>` | Generate via `openssl rand -hex 32` |
| `CORS_ORIGINS` | `https://your-domain.com` | Restrict allowed frontend origins |
| `STORAGE_PROVIDER` | `object` or `local` | Set `object` for S3-compatible cloud storage |
| `AI_ENABLED` | `true` | Enables AI inference & Grad-CAM pipeline |
| `LOG_LEVEL` | `INFO` | Production log level |

> [!CAUTION]
> NEVER commit `.env` or plain-text database credentials to source control.

### B. Frontend (`.env`)

Configure `clinixai-health-flow/.env`:

```ini
VITE_API_BASE_URL=https://api.your-domain.com/api/v1
```

> [!IMPORTANT]
> `VITE_*` variables are embedded into client-side JavaScript. **Never place secrets, private keys, or MongoDB URIs in frontend environment variables.**

---

## 3. Database Preparation (MongoDB Atlas)

1. Verify network access rules in MongoDB Atlas (whitelist backend server IP address).
2. Ensure user credentials have readWrite role on database `clinixai`.
3. Application auto-initialization will verify/create required indexes at startup via `app.database.indexes.ensure_database_indexes()`.

Indexes automatically verified:
- `users`: `email` (unique), `user_id` (unique)
- `patients`: `patient_id` (unique), `user_id` (sparse, unique)
- `doctors`: `doctor_id` (unique), `user_id` (unique)
- `appointments`: `appointment_id` (unique), compound `(doctor_id, appointment_date, start_time)`
- `ai_analyses`: `analysis_id` (unique), `patient_id`, `created_at`
- `audit_logs`: `audit_id` (unique), `actor_id`, `timestamp`

---

## 4. AI Model Artifact Placement

Ensure trained Brain MRI artifacts are present in `backend/ai_models/`:

```
backend/ai_models/
├── brain_model.keras        # Trained Keras classification model
├── brain_metadata.json      # Model architecture & input shape metadata
└── brain_class_names.json   # Class labels: ["Glioma", "Meningioma", "Pituitary", "No Tumor"]
```

The model loader (`app.ai.loader.AIModelLoader`) lazily initializes and caches the model state upon startup to optimize RAM usage.

---

## 5. Startup & Execution Commands

### A. Backend Deployment (Uvicorn / Gunicorn)

Run Gunicorn with Uvicorn worker class:

```bash
cd backend
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

### B. Frontend Deployment

Build static production bundle:

```bash
cd clinixai-health-flow
npm run build
```

The output build directory `.output/public` or `dist/` can be served via NGINX, Cloudflare Pages, Vercel, or AWS S3 + CloudFront.

---

## 6. Health Checks & Observability

### Endpoints
- Application Health: `GET /api/v1/health`
- AI Service Health: `GET /api/v1/ai/health`
- Model Registry: `GET /api/v1/ai/models`

Expected HTTP 200 Health Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0",
  "environment": "production"
}
```

---

## 7. Backup, Recovery & Rollback Strategy

1. **MongoDB Atlas Backups**: Continuous automated snapshots enabled via Atlas Backup policy.
2. **AI Artifact Backup**: Store versioned model weights (`brain_model.keras`) in secure Object Storage bucket.
3. **Rollback Procedure**:
   - Revert frontend static bundle to previous commit hash.
   - Revert backend container image to previous tag.
   - Database schema modifications are backward-compatible.

---

## 8. Troubleshooting

- **CORS Errors**: Verify `CORS_ORIGINS` in backend `.env` matches exact protocol and domain of the deployed frontend.
- **Inference Errors**: Ensure `tensorflow` and `pillow` dependencies are installed and `ai_models/brain_model.keras` is readable by the backend process.
- **Connection Refused**: Check MongoDB Atlas IP access whitelist and URI connection string formatting.
