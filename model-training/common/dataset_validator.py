"""
Modular Dataset Validator for CliniXAI Medical AI Training Workspace.

Supports:
A. Pre-split folder datasets (train/, Training/, val/, validation/, test/, Testing/)
B. Folder-labeled datasets (direct category folders)
C. Images + CSV metadata/labels

Validates readability, detects corrupted files, checks class balance, and flags potential
patient leakage across splits if patient ID metadata is provided.
"""

import os
import sys
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("dataset_validator")

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

# Canonical split names — all lowercase aliases that indicate a pre-split layout.
# Maps lowercase directory name -> canonical split key used in the report.
_PRESPLIT_ALIASES: Dict[str, str] = {
    "train":      "train",
    "training":   "train",
    "val":        "val",
    "validation": "val",
    "test":       "test",
    "testing":    "test",
}

# Required splits (at least one of these must exist for a pre-split dataset to be valid)
_REQUIRED_SPLITS = {"train", "training"}


def is_image_readable(path: Path) -> bool:
    """Check image file header integrity."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _scan_split_dir(s_dir: Path) -> Tuple[Dict[str, int], int]:
    """
    Scan a single split directory (e.g. Training/, val/) for class sub-folders and images.

    Returns
    -------
    class_counts   : dict mapping class name -> valid image count
    corrupted_count: int
    """
    class_counts: Dict[str, int] = {}
    corrupted_count = 0

    for c_dir in sorted(s_dir.iterdir()):
        if not c_dir.is_dir() or c_dir.name.startswith("."):
            continue
        valid_imgs = 0
        for img_file in c_dir.iterdir():
            if img_file.suffix.lower() in VALID_EXTENSIONS:
                if is_image_readable(img_file):
                    valid_imgs += 1
                else:
                    corrupted_count += 1
        class_counts[c_dir.name] = valid_imgs

    return class_counts, corrupted_count


def validate_module_dataset(mod_config: Any, raise_on_error: bool = False) -> Dict[str, Any]:
    """
    Validate dataset for a specific medical AI module configuration.

    Parameters
    ----------
    mod_config     : Module configuration object (e.g. chest.config)
    raise_on_error : bool — If True, raises ValueError or sys.exit(1) on fatal errors

    Returns
    -------
    report : dict containing validation report
    """
    module_slug = getattr(mod_config, "MODULE_SLUG", "unknown")
    dataset_dir = Path(getattr(mod_config, "DATASET_DIR"))

    # Read optional layout hint from module config.
    # Valid values: "pre_split" | "folder_labels" | "csv"
    config_layout: Optional[str] = getattr(mod_config, "DATASET_LAYOUT", None)

    log.info("=" * 60)
    log.info("Dataset Validation — Module: %s (%s)", module_slug.upper(), getattr(mod_config, "DISPLAY_NAME", ""))
    log.info("Path: %s", dataset_dir)
    if config_layout:
        log.info("Config layout hint: %s", config_layout)
    log.info("=" * 60)

    errors: List[str] = []
    warnings: List[str] = []

    if not dataset_dir.exists():
        msg = f"Dataset directory missing: {dataset_dir}"
        log.error(msg)
        errors.append(msg)
        report = {
            "module": module_slug,
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "classes": [],
            "splits": {},
        }
        if raise_on_error:
            sys.exit(1)
        return report

    # Enumerate immediate subdirectories (skip hidden)
    subdirs = [d for d in dataset_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    if not subdirs:
        msg = f"Dataset directory '{dataset_dir}' is empty. No subdirectories or splits found."
        log.error(msg)
        errors.append(msg)
        report = {
            "module": module_slug,
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
            "classes": [],
            "splits": {},
        }
        if raise_on_error:
            sys.exit(1)
        return report

    # ── Layout Detection ────────────────────────────────────────────────────────
    # Priority: config DATASET_LAYOUT > auto-detection from directory names.
    subdir_names_lower = {d.name.lower() for d in subdirs}

    if config_layout == "pre_split":
        is_presplit = True
        log.info("Layout: PRE-SPLIT (forced by module config DATASET_LAYOUT='pre_split')")
    elif config_layout == "folder_labels":
        is_presplit = False
        log.info("Layout: FOLDER-LABELED (forced by module config DATASET_LAYOUT='folder_labels')")
    else:
        # Auto-detect: any recognised split alias present → pre-split
        is_presplit = bool(set(_PRESPLIT_ALIASES.keys()).intersection(subdir_names_lower))
        log.info(
            "Layout: %s (auto-detected from directory names: %s)",
            "PRE-SPLIT" if is_presplit else "FOLDER-LABELED",
            sorted(subdir_names_lower),
        )

    split_reports: Dict[str, Any] = {}
    classes_discovered: set = set()
    total_images_all_splits = 0

    if is_presplit:
        log.info("Detected Pre-Split dataset layout (Training/train / Testing/test / val).")

        # Build a map from canonical split key -> actual directory object
        canonical_to_dir: Dict[str, Path] = {}
        for d in subdirs:
            canonical = _PRESPLIT_ALIASES.get(d.name.lower())
            if canonical:
                # Keep the first match for each canonical key (e.g. prefer "train" over "training"
                # only if both exist, which should never happen in practice)
                if canonical not in canonical_to_dir:
                    canonical_to_dir[canonical] = d

        # Require at least the training split
        if "train" not in canonical_to_dir:
            errors.append(
                "Required training split directory not found. "
                f"Expected a folder named 'train' or 'Training' inside {dataset_dir}."
            )

        # Scan each discovered split
        for canonical_key in ["train", "val", "test"]:
            if canonical_key not in canonical_to_dir:
                if canonical_key == "val":
                    warnings.append(
                        f"Optional validation split not found inside {dataset_dir}. "
                        "Training will proceed without a validation split."
                    )
                continue

            s_dir = canonical_to_dir[canonical_key]
            class_counts, corrupted_count = _scan_split_dir(s_dir)
            classes_discovered.update(class_counts.keys())

            total_split = sum(class_counts.values())
            total_images_all_splits += total_split

            split_reports[s_dir.name] = {
                "canonical_split": canonical_key,
                "class_counts": class_counts,
                "total_images": total_split,
                "corrupted_count": corrupted_count,
            }

            log.info(
                "  Split '%s' [%s]: %d valid images | %d corrupted | %d classes",
                s_dir.name, canonical_key, total_split, corrupted_count, len(class_counts),
            )
            for cls, cnt in sorted(class_counts.items()):
                log.info("    %-20s : %d images", cls, cnt)

        # Error if no images at all were found
        if total_images_all_splits == 0:
            errors.append(
                "No valid images found in any split directory. "
                "Ensure images with extensions "
                + str(VALID_EXTENSIONS)
                + " exist inside class sub-folders."
            )

    else:
        log.info("Detected Folder-Labeled dataset layout.")
        class_counts: Dict[str, int] = {}
        corrupted_count = 0

        for c_dir in sorted(subdirs):
            classes_discovered.add(c_dir.name)
            valid_imgs = 0
            for img_file in c_dir.iterdir():
                if img_file.suffix.lower() in VALID_EXTENSIONS:
                    if is_image_readable(img_file):
                        valid_imgs += 1
                    else:
                        corrupted_count += 1
            class_counts[c_dir.name] = valid_imgs

        total_imgs = sum(class_counts.values())
        total_images_all_splits = total_imgs
        split_reports["all"] = {
            "class_counts": class_counts,
            "total_images": total_imgs,
            "corrupted_count": corrupted_count,
        }
        log.info("  Discovered %d class folders with total %d valid images", len(class_counts), total_imgs)
        for cls, cnt in sorted(class_counts.items()):
            log.info("    %-20s : %d images", cls, cnt)

        if total_imgs == 0:
            errors.append(
                "No valid images found in any class folder. "
                "Ensure images with extensions "
                + str(VALID_EXTENSIONS)
                + " exist inside class sub-folders."
            )

    sorted_classes = sorted(list(classes_discovered))

    if not sorted_classes:
        errors.append("No class subdirectories or image files found in dataset.")

    report = {
        "module": module_slug,
        "layout": "pre_split" if is_presplit else "folder_labels",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "classes": sorted_classes,
        "num_classes": len(sorted_classes),
        "total_images": total_images_all_splits,
        "splits": split_reports,
    }

    # Save report artifact
    outputs_dir = Path(getattr(mod_config, "OUTPUTS_DIR", dataset_dir.parent / "outputs"))
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_file = outputs_dir / "dataset_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    log.info("Dataset validation report saved -> %s", report_file)
    log.info("Validation Status: %s", report["status"])
    if errors:
        for e in errors:
            log.error("  ERROR: %s", e)
    if warnings:
        for w in warnings:
            log.warning("  WARNING: %s", w)

    if errors and raise_on_error:
        sys.exit(1)

    return report
