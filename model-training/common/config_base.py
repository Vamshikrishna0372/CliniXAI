"""
Base Configuration & Resolver for CliniXAI Multi-Model Training Workspace.
"""

import sys
import importlib
from pathlib import Path
from typing import Dict, Any, List

TRAINING_ROOT = Path(__file__).parent.parent.resolve()

SUPPORTED_MODULES = ["chest", "brain", "skin", "eye", "bone"]


def get_module_config(module_slug: str) -> Any:
    """
    Dynamically load and return module configuration module for given slug.

    Parameters
    ----------
    module_slug : str — e.g., 'chest', 'brain', 'skin', 'eye', 'bone'

    Returns
    -------
    module config object
    """
    slug = module_slug.strip().lower()

    # Alias mapping
    aliases = {
        "chest_xray": "chest",
        "brain_mri": "brain",
        "skin_dermoscopy": "skin",
        "retinal_fundus": "eye",
        "bone_xray": "bone",
    }
    slug = aliases.get(slug, slug)

    if slug not in SUPPORTED_MODULES:
        raise ValueError(
            f"Unsupported training module '{module_slug}'. "
            f"Supported modules: {SUPPORTED_MODULES}"
        )

    # Ensure training root is on sys.path
    if str(TRAINING_ROOT) not in sys.path:
        sys.path.insert(0, str(TRAINING_ROOT))

    try:
        mod = importlib.import_module(f"{slug}.config")
        return mod
    except ImportError as e:
        raise ImportError(f"Could not import config for module '{slug}': {e}")
