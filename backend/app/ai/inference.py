"""
Backend Model Inference Engine for CliniXAI Multi-Model Medical AI Architecture.

Executes forward pass for registered medical imaging models (Chest X-Ray, Brain MRI,
Skin Dermoscopy, Retinal Fundus, Bone X-Ray) and returns structured PredictionResult.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional

from app.models.ai_analysis import PredictionResult
from app.ai.model_loader import get_model_loader
from app.ai.registry import ClassificationMode, get_ai_registry


def run_inference(
    preprocessed_tensor: np.ndarray,
    module_id: str = "CHEST_XRAY",
) -> Tuple[PredictionResult, str]:
    """
    Run inference for a specified registered medical AI module.

    Parameters
    ----------
    preprocessed_tensor : np.ndarray shape (H, W, C) or (1, H, W, C)
    module_id           : str — Registered module identifier or slug (e.g., 'CHEST_XRAY', 'brain')

    Returns
    -------
    (prediction_result, model_version)
    """
    registry = get_ai_registry()
    norm_id = registry.normalize_identifier(module_id)
    mod_cfg = registry.get_module(norm_id)

    loader = get_model_loader()
    artifact = loader.load_module(norm_id)

    if not artifact.is_available:
        raise RuntimeError(f"Cannot run inference for module '{norm_id}': {artifact.error_message}")

    if preprocessed_tensor.ndim == 3:
        batch_tensor = np.expand_dims(preprocessed_tensor, axis=0)
    else:
        batch_tensor = preprocessed_tensor

    model = artifact.model
    class_names = artifact.class_names or mod_cfg.default_class_names
    mode = mod_cfg.classification_mode

    probs = model.predict(batch_tensor, verbose=0)[0]  # shape (1,) or (C,)

    decision_threshold = float(artifact.metadata.get("decision_threshold", 0.5))

    if mode == ClassificationMode.MULTILABEL:
        # Multilabel classification (sigmoid activation per output node)
        class_probabilities = {
            class_names[i] if i < len(class_names) else f"finding_{i}": round(float(probs[i]), 4)
            for i in range(len(probs))
        }
        positive_findings = [c for c, p in class_probabilities.items() if p >= decision_threshold]
        predicted_class = ", ".join(positive_findings) if positive_findings else "No abnormal findings detected"
        confidence = float(np.max(probs)) if len(probs) > 0 else 0.0
        low_confidence = bool(confidence < decision_threshold)

    elif len(probs) == 1 or mode == ClassificationMode.BINARY:
        # Binary classification output (single sigmoid node)
        prob_positive = float(probs[0]) if len(probs) > 0 else float(probs)
        prob_negative = float(1.0 - prob_positive)

        class_probabilities = {
            class_names[0]: round(prob_negative, 4),
            class_names[1] if len(class_names) > 1 else "Positive": round(prob_positive, 4),
        }

        if prob_positive >= decision_threshold:
            predicted_class = class_names[1] if len(class_names) > 1 else "Positive"
            confidence = prob_positive
        else:
            predicted_class = class_names[0]
            confidence = prob_negative

        low_confidence = bool(abs(prob_positive - 0.5) < 0.15)

    else:
        # Multiclass output (softmax)
        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])
        predicted_class = class_names[pred_idx] if pred_idx < len(class_names) else f"class_{pred_idx}"

        class_probabilities = {
            class_names[i] if i < len(class_names) else f"class_{i}": round(float(probs[i]), 4)
            for i in range(len(probs))
        }
        low_confidence = bool(confidence < 0.5)

    model_version = artifact.metadata.get("model_version", mod_cfg.version)

    result = PredictionResult(
        predicted_class=predicted_class,
        confidence=round(confidence, 4),
        class_probabilities=class_probabilities,
        decision_threshold=decision_threshold,
        low_confidence=low_confidence,
    )

    return result, model_version
