# CliniXAI — Multi-Model Medical AI Training Workspace

This workspace contains the modular deep-learning training pipeline for **CliniXAI's Multi-Model Medical AI/XAI Architecture**.

Supported Initial Medical AI Modules:
1. **Chest X-Ray (`chest`)** — Pulmonary disease screening (`CHEST_XRAY`)
2. **Brain MRI (`brain`)** — Brain neoplasm/tumor classification (`BRAIN_MRI`)
3. **Skin Dermoscopy (`skin`)** — Cutaneous lesion analysis (`SKIN_DERMOSCOPY`)
4. **Eye / Retinal Fundus (`eye`)** — Diabetic retinopathy screening (`RETINAL_FUNDUS`)
5. **Bone X-Ray (`bone`)** — Acute fracture detection (`BONE_XRAY`)

---

## Workspace Directory Architecture

```
model-training/
├── common/                     # Shared training, validation, & artifact utilities
│   ├── config_base.py          # Dynamic module configuration resolver
│   ├── dataset_validator.py    # Modular dataset integrity & split checker
│   ├── model_builder.py        # Backbone architecture & classification head builder
│   └── artifact_utils.py       # Metadata & class mapping exporter
│
├── chest/                      # Chest X-Ray Module
│   ├── dataset/                # Place raw chest X-ray images here
│   ├── outputs/                # Isolated outputs (chest_model.keras, etc.)
│   └── config.py               # Module-specific configuration
│
├── brain/                      # Brain MRI Module
│   ├── dataset/                # Place raw brain MRI images here
│   ├── outputs/                # Isolated outputs (brain_model.keras, etc.)
│   └── config.py               # Module-specific configuration
│
├── skin/                      # Skin Dermoscopy Module
│   ├── dataset/                # Place raw skin lesion images here
│   ├── outputs/                # Isolated outputs (skin_model.keras, etc.)
│   └── config.py               # Module-specific configuration
│
├── eye/                       # Retinal Fundus Module
│   ├── dataset/                # Place raw fundus images here
│   ├── outputs/                # Isolated outputs (eye_model.keras, etc.)
│   └── config.py               # Module-specific configuration
│
├── bone/                      # Bone X-Ray Module
│   ├── dataset/                # Place raw bone X-ray images here
│   ├── outputs/                # Isolated outputs (bone_model.keras, etc.)
│   └── config.py               # Module-specific configuration
│
├── train.py                    # Master CLI to train individual modules
├── promote.py                  # Production promotion CLI script
└── README.md                   # Beginner-friendly guide
```

---

## Step-by-Step Training Guide (Beginner Friendly)

### 1. Downloading Medical Datasets
Download public/Kaggle medical imaging datasets for the module you wish to train.
Recommended public sources:
- **Chest X-Ray**: Kaggle Chest X-Ray Pneumonia dataset / NIH ChestX-ray14
- **Brain MRI**: Kaggle Brain Tumor Classification (MRI) dataset
- **Skin Dermoscopy**: ISIC Archive / HAM10000 dataset
- **Retinal Fundus**: Kaggle EyePACS / APTOS Diabetic Retinopathy dataset
- **Bone X-Ray**: MURA (Musculoskeletal Radiographs) dataset

---

### 2. Placing Dataset Files for a Module

Extract the downloaded dataset directly into the `dataset/` directory of the target module.

#### Folder-Labeled Layout Example (`brain`):
```
model-training/brain/dataset/
├── glioma/
│   ├── image_01.jpg
│   └── image_02.jpg
├── meningioma/
│   └── image_03.jpg
├── pituitary/
│   └── image_04.jpg
└── no_tumor/
    └── image_05.jpg
```

#### Pre-Split Layout Example (`chest`):
```
model-training/chest/dataset/
├── train/
│   ├── Normal/
│   └── Pneumonia/
├── validation/
│   ├── Normal/
│   └── Pneumonia/
└── test/
    ├── Normal/
    └── Pneumonia/
```

---

### 3. Validating the Dataset Before Training

Run the master CLI script with `--list-modules` or validate your dataset layout:

```bash
# Check all available training modules
python train.py --list-modules
```

To validate a module's dataset:
```bash
python -c "from common.dataset_validator import validate_module_dataset; from common.config_base import get_module_config; validate_module_dataset(get_module_config('brain'))"
```

The validator checks:
- Directory existence & readable image files
- Category classes detected
- Corrupted images detection
- Class balance ratio

---

### 4. Training ONE Module at a Time

Train a specific module using the master CLI:

```bash
# Example 1: Train Brain MRI module
python train.py --module brain

# Example 2: Train Chest X-Ray module
python train.py --module chest

# Example 3: Train Skin Dermoscopy module
python train.py --module skin
```

*Note: Training one module writes isolated outputs to `model-training/<module>/outputs/` and will **NEVER** overwrite another module's trained model.*

---

### 5. Evaluating the Trained Model

After training finishes, metrics and plots are generated in the module's `outputs/` directory.
Artifacts produced:
- `<module>_model.keras` — Trained TensorFlow model
- `<module>_metadata.json` — Model provenance and Grad-CAM layer configuration
- `<module>_class_names.json` — Class index mapping
- `dataset_report.json` — Dataset validation report

---

### 6. Where the Generated `.keras` File Appears

For example, after training `brain`:
`model-training/brain/outputs/brain_model.keras`

For `chest`:
`model-training/chest/outputs/chest_model.keras`

---

### 7. Promoting an Approved Model to Production

Once satisfied with evaluation results, promote the model to FastAPI production storage:

```bash
# Promote a single approved module
python promote.py --module brain

# Promote all available trained modules
python promote.py --all
```

---

### 8. Production Model Storage & FastAPI Selection

Production models are stored in:
`backend/ai_models/`

Target filenames:
- `backend/ai_models/chest_model.keras`
- `backend/ai_models/brain_model.keras`
- `backend/ai_models/skin_model.keras`
- `backend/ai_models/eye_model.keras`
- `backend/ai_models/bone_model.keras`

FastAPI selects models dynamically when a Doctor requests an AI analysis via `POST /api/v1/ai-analyses`:
1. Doctor selects analysis type (e.g. `BRAIN_MRI`, `CHEST_XRAY`).
2. FastAPI looks up the registered module configuration.
3. `ModelLoader` loads and caches `backend/ai_models/brain_model.keras`.
4. Preprocessing applies the module's target input shape `(224, 224, 3)` and normalization.
5. Inference generates class predictions & probabilities.
6. Grad-CAM generates PNG heatmap overlays using the target layer (`conv5_block3_out`).
7. Result is submitted for mandatory Doctor Review before patient report access.

---

### 9. Checking AI Subsystem & Model Availability

You can check module availability via the API:

```bash
# Check AI subsystem health and per-module availability
GET /api/v1/ai/health

# List all registered AI modules and statuses
GET /api/v1/ai/modules
```

If a model is not yet trained, the module reports status `"unavailable"` / `"missing"` without crashing the backend. Once promoted, that module automatically becomes available.
