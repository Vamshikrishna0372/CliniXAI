"""
CliniXAI Model Promotion CLI.

Safely validates and promotes trained per-module model artifacts from `model-training/<module>/outputs/`
into the production model directory `backend/ai_models/`.

Usage:
    python promote.py --module chest
    python promote.py --module brain
    python promote.py --all
"""

import sys
import shutil
import argparse
import logging
from pathlib import Path

TRAINING_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(TRAINING_ROOT))

from common.config_base import get_module_config, SUPPORTED_MODULES

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("promote")

BACKEND_AI_MODELS_DIR = TRAINING_ROOT.parent / "backend" / "ai_models"


def promote_module(module_slug: str) -> bool:
    """Validate and copy module model artifacts to backend/ai_models/."""
    mod_cfg = get_module_config(module_slug)
    outputs_dir = Path(mod_cfg.OUTPUTS_DIR)
    BACKEND_AI_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    src_model = outputs_dir / mod_cfg.MODEL_FILENAME
    if not src_model.exists():
        src_model = outputs_dir / "model.keras"

    if not src_model.exists():
        log.error("Promotion failed for %s: Model artifact not found at %s", module_slug, src_model)
        return False

    target_model = BACKEND_AI_MODELS_DIR / mod_cfg.MODEL_FILENAME
    target_meta = BACKEND_AI_MODELS_DIR / mod_cfg.METADATA_FILENAME
    target_cmap = BACKEND_AI_MODELS_DIR / mod_cfg.CLASS_MAP_FILENAME

    # Copy Model
    shutil.copy2(src_model, target_model)
    log.info("✓ Promoted model: %s -> %s", src_model.name, target_model)

    # Copy Metadata
    src_meta = outputs_dir / mod_cfg.METADATA_FILENAME
    if not src_meta.exists():
        src_meta = outputs_dir / "model_metadata.json"
    if src_meta.exists():
        shutil.copy2(src_meta, target_meta)
        log.info("✓ Promoted metadata: %s -> %s", src_meta.name, target_meta)

    # Copy Class Map
    src_cmap = outputs_dir / mod_cfg.CLASS_MAP_FILENAME
    if not src_cmap.exists():
        src_cmap = outputs_dir / "class_names.json"
    if src_cmap.exists():
        shutil.copy2(src_cmap, target_cmap)
        log.info("✓ Promoted class map: %s -> %s", src_cmap.name, target_cmap)

    log.info("Successfully promoted module '%s' to production storage!", module_slug)
    return True


def main():
    parser = argparse.ArgumentParser(description="CliniXAI Model Promotion CLI")
    parser.add_argument("--module", "-m", type=str, help="Module slug to promote (chest, brain, skin, eye, bone)")
    parser.add_argument("--all", "-a", action="store_true", help="Promote all available trained modules")

    args = parser.parse_args()

    if args.all:
        promoted = 0
        for slug in SUPPORTED_MODULES:
            if promote_module(slug):
                promoted += 1
        log.info("Promoted %d / %d modules.", promoted, len(SUPPORTED_MODULES))
        return

    if not args.module:
        parser.print_help()
        return

    promote_module(args.module)


if __name__ == "__main__":
    main()
