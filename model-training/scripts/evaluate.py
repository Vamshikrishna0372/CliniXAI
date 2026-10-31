"""
CliniXAI Phase 7 — Model Evaluation Script.

IMPORTANT: Runs evaluation ONLY on the held-out test set.
           The test set must NEVER have been used during training or
           hyperparameter selection.

Usage:
    python scripts/evaluate.py

Outputs (written to outputs/metrics/ and outputs/plots/)
---------------------------------------------------------
evaluation.json           — accuracy, precision, recall, F1, AUC, specificity
classification_report.json — per-class metrics
confusion_matrix.csv       — raw confusion matrix values
plots/confusion_matrix.png
plots/roc_curve.png        (binary classification only)
"""

import sys
import json
import logging
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("evaluate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_class_names() -> list:
    if not cfg.CLASS_NAMES_FILE.exists():
        log.error("class_names.json not found — run train.py first.")
        sys.exit(1)
    with open(cfg.CLASS_NAMES_FILE) as f:
        return json.load(f)


def _load_model(class_names: list):
    """Load best weights into a fresh model."""
    import tensorflow as tf
    from scripts.model import build_model

    num_classes = len(class_names)
    model = build_model(num_classes, frozen=False)

    if cfg.EXPORTED_MODEL.exists():
        log.info("Loading exported model: %s", cfg.EXPORTED_MODEL)
        model = tf.keras.models.load_model(str(cfg.EXPORTED_MODEL))
    elif cfg.BEST_CHECKPOINT.exists():
        log.info("Loading best checkpoint weights: %s", cfg.BEST_CHECKPOINT)
        model.load_weights(str(cfg.BEST_CHECKPOINT))
    else:
        log.error("No model or checkpoint found. Run train.py and export_model.py first.")
        sys.exit(1)

    return model


def _get_predictions(model, test_ds, num_classes: int):
    """Run inference over the full test set. Returns (y_true, y_pred_prob)."""
    import tensorflow as tf

    all_labels = []
    all_probs  = []

    for x_batch, y_batch in test_ds:
        probs = model.predict(x_batch, verbose=0)
        if num_classes == 2:
            # Binary: shape (N,1) → flatten
            all_probs.extend(probs.flatten().tolist())
            all_labels.extend(y_batch.numpy().flatten().tolist())
        else:
            # Multi-class: shape (N, C)
            all_probs.extend(probs.tolist())
            all_labels.extend(np.argmax(y_batch.numpy(), axis=1).tolist())

    return np.array(all_labels), np.array(all_probs)


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def _plot_confusion_matrix(cm: np.ndarray, class_names: list) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg.PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(max(6, len(class_names) * 1.5),
                                     max(5, len(class_names) * 1.3)))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    fig.colorbar(im)
    tick_marks = np.arange(len(class_names))
    ax.set_xticks(tick_marks)
    ax.set_xticklabels(class_names, rotation=45, ha="right")
    ax.set_yticks(tick_marks)
    ax.set_yticklabels(class_names)

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")

    ax.set_ylabel("True label")
    ax.set_xlabel("Predicted label")
    ax.set_title("Confusion Matrix — CliniXAI ResNet50 (Test Set)")
    fig.tight_layout()
    path = cfg.PLOTS_DIR / "confusion_matrix.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Confusion matrix plot saved → %s", path)


def _plot_roc_curve(y_true: np.ndarray, y_prob: np.ndarray) -> None:
    """Binary ROC curve only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve, auc

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc     = auc(fpr, tpr)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, color="darkorange", lw=2,
            label=f"ROC curve (AUC = {roc_auc:.4f})")
    ax.plot([0, 1], [0, 1], color="navy", lw=1, linestyle="--")
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate (Sensitivity)")
    ax.set_title("ROC Curve — CliniXAI ResNet50 (Test Set)")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = cfg.PLOTS_DIR / "roc_curve.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("ROC curve saved → %s", path)
    return roc_auc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    from sklearn.metrics import (
        confusion_matrix, classification_report,
        accuracy_score, precision_score, recall_score, f1_score,
        roc_auc_score,
    )
    import pandas as pd

    log.info("=" * 60)
    log.info("CliniXAI Phase 7 — Model Evaluation (Test Set)")
    log.info("=" * 60)

    class_names  = _load_class_names()
    num_classes  = len(class_names)
    model        = _load_model(class_names)

    # Build test dataset
    from scripts.augmentation import build_tf_datasets
    _, _, test_ds = build_tf_datasets(class_names)

    log.info("Running inference on test set …")
    y_true, y_prob = _get_predictions(model, test_ds, num_classes)

    # Predicted classes
    if num_classes == 2:
        y_pred = (y_prob >= cfg.BINARY_THRESHOLD).astype(int)
    else:
        y_pred = np.argmax(y_prob, axis=1)

    # ── Core metrics ─────────────────────────────────────────────────────────
    avg = "binary" if num_classes == 2 else "macro"

    accuracy  = float(accuracy_score(y_true, y_pred))
    precision = float(precision_score(y_true, y_pred, average=avg, zero_division=0))
    recall    = float(recall_score(y_true, y_pred, average=avg, zero_division=0))
    f1        = float(f1_score(y_true, y_pred, average=avg, zero_division=0))

    log.info("Accuracy  : %.4f", accuracy)
    log.info("Precision : %.4f", precision)
    log.info("Recall    : %.4f (Sensitivity)", recall)
    log.info("F1-Score  : %.4f", f1)

    eval_dict = {
        "accuracy":  accuracy,
        "precision": precision,
        "recall_sensitivity": recall,
        "f1_score":  f1,
        "threshold": cfg.BINARY_THRESHOLD,
        "num_classes": num_classes,
        "class_names": class_names,
    }

    # ── AUC ──────────────────────────────────────────────────────────────────
    try:
        if num_classes == 2:
            auc_score = float(roc_auc_score(y_true, y_prob))
        else:
            auc_score = float(roc_auc_score(
                y_true, y_prob, multi_class="ovr", average="macro"
            ))
        log.info("ROC-AUC   : %.4f", auc_score)
        eval_dict["roc_auc"] = auc_score
    except Exception as e:
        log.warning("ROC-AUC could not be computed: %s", e)

    # ── Specificity (binary only) ─────────────────────────────────────────────
    if num_classes == 2:
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        log.info("Specificity: %.4f", specificity)
        eval_dict["specificity"] = specificity

    # ── Confusion matrix ──────────────────────────────────────────────────────
    cm = confusion_matrix(y_true, y_pred)
    log.info("Confusion Matrix:\n%s", cm)
    _plot_confusion_matrix(cm, class_names)

    # Save CM as CSV
    cfg.METRICS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        cm,
        index=[f"true_{c}" for c in class_names],
        columns=[f"pred_{c}" for c in class_names],
    ).to_csv(cfg.CONFUSION_CSV)
    log.info("Confusion matrix CSV saved → %s", cfg.CONFUSION_CSV)

    # ── ROC curve (binary) ────────────────────────────────────────────────────
    if num_classes == 2:
        _plot_roc_curve(y_true, y_prob)

    # ── Per-class classification report ───────────────────────────────────────
    report_dict = classification_report(
        y_true, y_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    with open(cfg.CLASS_REPORT_FILE, "w") as f:
        json.dump(report_dict, f, indent=2)
    log.info("Classification report saved → %s", cfg.CLASS_REPORT_FILE)
    log.info("\n%s", classification_report(
        y_true, y_pred, target_names=class_names, zero_division=0
    ))

    # ── Error analysis — high-confidence misclassifications ───────────────────
    errors = []
    if num_classes == 2:
        for i, (gt, pred, prob) in enumerate(zip(y_true, y_pred, y_prob)):
            if gt != pred and abs(float(prob) - 0.5) > 0.3:
                errors.append({
                    "index": i,
                    "true_class": class_names[int(gt)],
                    "predicted_class": class_names[int(pred)],
                    "confidence": round(float(prob), 4),
                })
    else:
        for i, (gt, pred, probs) in enumerate(zip(y_true, y_pred, y_prob)):
            conf = float(np.max(probs))
            if gt != pred and conf > 0.7:
                errors.append({
                    "index": i,
                    "true_class": class_names[int(gt)],
                    "predicted_class": class_names[int(pred)],
                    "confidence": round(conf, 4),
                })
    eval_dict["high_confidence_errors"] = len(errors)
    error_path = cfg.METRICS_DIR / "high_confidence_errors.json"
    with open(error_path, "w") as f:
        json.dump(errors[:50], f, indent=2)    # cap at 50 entries
    log.info("High-confidence errors: %d  (saved → %s)", len(errors), error_path)

    # ── Save evaluation summary ───────────────────────────────────────────────
    with open(cfg.EVALUATION_FILE, "w") as f:
        json.dump(eval_dict, f, indent=2)
    log.info("Evaluation summary saved → %s", cfg.EVALUATION_FILE)

    log.info("")
    log.info("=" * 60)
    log.info("Evaluation complete.  Next: python scripts/export_model.py")
    log.info("=" * 60)

    # ── Model limitations reminder ────────────────────────────────────────────
    log.info("")
    log.warning(
        "CLINICAL REMINDER: These metrics reflect performance on the "
        "selected dataset only. This model is decision-support software "
        "and must be reviewed by a qualified medical professional. "
        "It is NOT clinically validated or FDA approved."
    )


if __name__ == "__main__":
    main()
