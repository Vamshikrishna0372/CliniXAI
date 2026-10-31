"""
CliniXAI Multi-Model Master Training CLI.

Provides a unified command-line interface to validate datasets and train individual
specialized medical AI modules (Chest X-Ray, Brain MRI, Skin Dermoscopy, Retinal Fundus, Bone X-Ray).

Usage:
    python train.py --module brain
    python train.py --module chest
    python train.py --module skin
    python train.py --module eye
    python train.py --module bone
    python train.py --list-modules
    python train.py --help
"""

import sys
import argparse
import logging
from pathlib import Path

TRAINING_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(TRAINING_ROOT))

from common.config_base import get_module_config, SUPPORTED_MODULES
from common.dataset_validator import validate_module_dataset
from common.trainer import run_training
from common.artifact_utils import export_module_artifacts

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("train_cli")


def list_supported_modules():
    """Print all available training modules and their details."""
    print("=" * 60)
    print("CliniXAI Medical AI Training Workspace — Supported Modules")
    print("=" * 60)
    for slug in SUPPORTED_MODULES:
        try:
            cfg = get_module_config(slug)
            print(f"  • {slug:<10} -> {cfg.DISPLAY_NAME} ({cfg.MODALITY})")
            print(f"    Dataset  : model-training/{slug}/dataset/")
            print(f"    Outputs  : model-training/{slug}/outputs/{cfg.MODEL_FILENAME}")
        except Exception as e:
            print(f"  • {slug:<10} -> [Config Error: {e}]")
    print("=" * 60)


def train_module(
    module_slug: str,
    initial_epochs: int = 20,
    fine_tune_epochs: int = 20,
    batch_size: int = 32,
    validation_split: float = 0.20,
    raise_on_dataset_error: bool = True,
) -> None:
    """Validate dataset and run the full two-stage training pipeline."""
    mod_cfg = get_module_config(module_slug)

    log.info("=" * 60)
    log.info("CliniXAI Multi-Model Training — Module: %s (%s)",
             mod_cfg.MODULE_SLUG.upper(), mod_cfg.DISPLAY_NAME)
    log.info("=" * 60)

    # ── 1. Validate dataset ──────────────────────────────────────────────────
    report = validate_module_dataset(mod_cfg, raise_on_error=raise_on_dataset_error)
    if report["status"] == "FAIL":
        log.error("Dataset validation FAILED for module '%s'. Stopping.", module_slug)
        sys.exit(1)

    class_names = report["classes"]
    if not class_names:
        class_names = list(mod_cfg.DEFAULT_CLASSES)
        log.warning("Validator found no classes — falling back to config defaults: %s", class_names)

    log.info("Classes detected: %s (%d)", class_names, len(class_names))
    log.info("Training images (approx): %d", report.get("total_images", 0))

    # ── 2. Run complete two-stage training pipeline ──────────────────────────
    result = run_training(
        mod_config=mod_cfg,
        class_names=class_names,
        validation_split=validation_split,
        initial_epochs=initial_epochs,
        fine_tune_epochs=fine_tune_epochs,
        batch_size=batch_size,
        initial_lr=1e-3,
        fine_tune_lr=1e-5,
        fine_tune_at_layer=143,
        dropout_rate=0.3,
        early_stopping_patience=7,
        reduce_lr_patience=3,
        reduce_lr_factor=0.3,
        reduce_lr_min_lr=1e-7,
        random_seed=42,
    )

    # ── 3. Export metadata & class-map artifacts ─────────────────────────────
    extra_metadata = {
        "model_sha256": result.get("model_sha256"),
        "best_epoch": result.get("best_epoch"),
        "validation_metrics": result.get("best_val_metrics"),
        "preprocessing_configuration": {
            "input_size": list(mod_cfg.IMAGE_SIZE),
            "num_channels": mod_cfg.NUM_CHANNELS,
            "preprocessing_fn": mod_cfg.PREPROCESSING_FN,
            "augment_horizontal_flip": getattr(mod_cfg, "AUGMENT_HORIZONTAL_FLIP", False),
        },
    }
    export_module_artifacts(
        mod_cfg,
        class_names=result["class_names"],
        test_metrics=result["evaluation"],
        gradcam_layer=result["gradcam_layer"],
        extra_metadata=extra_metadata,
    )

    # ── 4. Final summary ─────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("Training COMPLETE — Module: %s", mod_cfg.MODULE_SLUG.upper())
    log.info("  Stage 1 epochs  : %d", result["stage1_epochs"])
    log.info("  Stage 2 epochs  : %d", result["stage2_epochs"])
    log.info("  Total time      : %.1f s", result["total_duration_s"])
    log.info("  Model artifact  : %s", result["model_path"])
    if result["evaluation"]:
        for k, v in result["evaluation"].items():
            log.info("  Test %-18s: %.4f", k, v)
    log.info("To promote to backend production storage, run:")
    log.info("    python promote.py --module %s", mod_cfg.MODULE_SLUG)
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="CliniXAI Multi-Model Medical AI Training CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train.py --module brain
  python train.py --module chest --epochs 15 --fine-tune-epochs 10
  python train.py --module skin --batch-size 16
  python train.py --list-modules
        """,
    )

    parser.add_argument(
        "--module", "-m",
        type=str,
        help="Target medical AI module to train (chest, brain, skin, eye, bone)",
    )
    parser.add_argument(
        "--list-modules", "-l",
        action="store_true",
        help="List all registered medical AI training modules",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=20,
        help="Number of Stage-1 (frozen backbone) training epochs (default: 20)",
    )
    parser.add_argument(
        "--fine-tune-epochs",
        type=int,
        default=20,
        help="Number of Stage-2 (fine-tuning) epochs (default: 20)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Training batch size (default: 32)",
    )
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.20,
        help="Fraction of training data to use as validation (default: 0.20)",
    )

    args = parser.parse_args()

    if args.list_modules:
        list_supported_modules()
        return

    if not args.module:
        parser.print_help()
        print("\nAvailable modules:", ", ".join(SUPPORTED_MODULES))
        return

    train_module(
        module_slug=args.module,
        initial_epochs=args.epochs,
        fine_tune_epochs=args.fine_tune_epochs,
        batch_size=args.batch_size,
        validation_split=args.val_split,
        raise_on_dataset_error=False,
    )


if __name__ == "__main__":
    main()
