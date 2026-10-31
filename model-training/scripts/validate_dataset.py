"""
Dataset validation for CliniXAI Phase 7.

Checks structural integrity of train/validation/test splits before training.
Run independently or called from train.py.

Usage:
    python scripts/validate_dataset.py
"""

import os
import sys
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# ── path bootstrap ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("dataset_validator")

# Supported image extensions
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_image_readable(path: Path) -> bool:
    """Return True if the image header is readable (quick magic-byte check)."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()          # verify header only — fast
        return True
    except Exception:
        return False


def _scan_split(split_dir: Path) -> Tuple[Dict[str, List[Path]], List[Path]]:
    """
    Scan one split directory.

    Returns
    -------
    class_files  : {class_name: [Path, ...]}
    corrupted    : [Path, ...]
    """
    class_files: Dict[str, List[Path]] = defaultdict(list)
    corrupted: List[Path] = []

    if not split_dir.exists():
        return class_files, corrupted

    for class_dir in sorted(split_dir.iterdir()):
        if not class_dir.is_dir():
            continue
        for f in class_dir.iterdir():
            if f.suffix.lower() not in VALID_EXTENSIONS:
                log.warning("  Unsupported format skipped: %s", f.name)
                continue
            if _check_image_readable(f):
                class_files[class_dir.name].append(f)
            else:
                log.warning("  Corrupted image detected: %s", f)
                corrupted.append(f)

    return class_files, corrupted


# ---------------------------------------------------------------------------
# Core validator
# ---------------------------------------------------------------------------

def validate_dataset(raise_on_error: bool = True) -> dict:
    """
    Validate the full dataset directory.

    Parameters
    ----------
    raise_on_error : bool
        If True, sys.exit(1) on critical failures.

    Returns
    -------
    report : dict  (also written to outputs/metrics/dataset_report.json)
    """
    log.info("=" * 60)
    log.info("CliniXAI Phase 7 — Dataset Validation")
    log.info("=" * 60)

    errors: List[str] = []
    warnings: List[str] = []

    # 1. Check split directories exist
    for split_name, split_dir in [
        ("train",      cfg.TRAIN_DIR),
        ("validation", cfg.VAL_DIR),
        ("test",       cfg.TEST_DIR),
    ]:
        if not split_dir.exists():
            msg = f"Split directory missing: {split_dir}"
            log.error(msg)
            errors.append(msg)
        else:
            log.info("  ✓  %s split found at %s", split_name, split_dir)

    if errors:
        log.error("Critical: one or more split directories are missing.")
        if raise_on_error:
            sys.exit(1)

    # 2. Scan each split
    split_reports = {}
    all_class_sets = []

    for split_name, split_dir in [
        ("train",      cfg.TRAIN_DIR),
        ("validation", cfg.VAL_DIR),
        ("test",       cfg.TEST_DIR),
    ]:
        if not split_dir.exists():
            split_reports[split_name] = {"error": "directory missing"}
            continue

        log.info("")
        log.info("Scanning split: %s", split_name.upper())
        class_files, corrupted = _scan_split(split_dir)

        class_counts = {k: len(v) for k, v in class_files.items()}
        total = sum(class_counts.values())

        log.info("  Classes  : %s", list(class_counts.keys()))
        log.info("  Total    : %d images", total)
        for cls, cnt in class_counts.items():
            log.info("    %-20s  %d images", cls, cnt)
        if corrupted:
            log.warning("  Corrupted: %d images skipped", len(corrupted))
            warnings.append(
                f"{split_name}: {len(corrupted)} corrupted image(s) skipped"
            )

        # Empty class detection
        for cls, cnt in class_counts.items():
            if cnt == 0:
                msg = f"{split_name} → class '{cls}' has 0 valid images"
                log.error(msg)
                errors.append(msg)

        if total == 0:
            msg = f"{split_name} split contains no valid images"
            log.error(msg)
            errors.append(msg)

        all_class_sets.append(frozenset(class_counts.keys()))
        split_reports[split_name] = {
            "class_counts": class_counts,
            "total_images": total,
            "corrupted_count": len(corrupted),
        }

    # 3. Class consistency across splits
    if len(all_class_sets) > 1 and len(set(all_class_sets)) > 1:
        msg = (
            "Class names are inconsistent across splits: "
            + str([list(s) for s in all_class_sets])
        )
        log.error(msg)
        errors.append(msg)
    elif all_class_sets:
        log.info("")
        log.info("  ✓  Classes consistent across splits: %s", sorted(list(all_class_sets[0])))

    # 4. Imbalance detection (training only)
    train_counts = split_reports.get("train", {}).get("class_counts", {})
    if train_counts:
        counts = list(train_counts.values())
        if max(counts) > 0 and min(counts) > 0:
            imbalance_ratio = max(counts) / min(counts)
            if imbalance_ratio > 3.0:
                msg = (
                    f"Significant class imbalance detected in train split "
                    f"(ratio {imbalance_ratio:.1f}x). Class weights will be applied."
                )
                log.warning(msg)
                warnings.append(msg)
            else:
                log.info("  ✓  Class balance ratio: %.2fx (acceptable)", imbalance_ratio)

    # 5. Build report
    classes = sorted(list(all_class_sets[0])) if all_class_sets else []
    report = {
        "status":         "PASS" if not errors else "FAIL",
        "errors":         errors,
        "warnings":       warnings,
        "classes":        classes,
        "num_classes":    len(classes),
        "splits":         split_reports,
    }

    # 6. Save report
    cfg.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = cfg.METRICS_DIR / "dataset_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("")
    log.info("Dataset report saved → %s", report_path)

    # 7. Final verdict
    log.info("")
    if errors:
        log.error("Dataset validation FAILED — %d error(s).", len(errors))
        for e in errors:
            log.error("  • %s", e)
        if raise_on_error:
            sys.exit(1)
    else:
        log.info("=" * 60)
        log.info("Dataset validation PASSED — %d classes, ready for training.", len(classes))
        log.info("=" * 60)

    return report


if __name__ == "__main__":
    validate_dataset(raise_on_error=True)
