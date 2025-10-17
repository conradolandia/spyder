# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Palettes for dark and light themes used in Spyder.
"""

# Standard library imports
import logging
from spyder.utils.theme_manager import theme_manager

logger = logging.getLogger(__name__)


# =============================================================================
# ---- Theme manager integration
# =============================================================================


def _get_theme_palette():
    """
    Get SpyderPalette from theme manager.

    Returns
    -------
    class
        SpyderPalette class from the loaded theme, or None if loading fails.
    """
    try:
        # Export all available themes to config BEFORE loading the selected theme
        # This ensures all themes are properly populated with their own colors
        # even when config file is new/reset
        try:
            theme_manager.export_all_themes_to_config()
        except Exception as theme_exp:
            logger.warning(f"Failed to export all themes to config: {theme_exp}")
            
        # Get selected theme from config
        from spyder.config.manager import CONF
        selected = CONF.get("appearance", "selected", default="qdarkstyle/dark")
        
        # Parse theme name and mode from the selected variant
        if "/" in selected:
            theme_name, ui_mode = selected.rsplit("/", 1)
        else:
            # Fallback for old config format
            theme_name = selected
            ui_mode = "dark"
        
        # Load the theme
        palette_class, _ = theme_manager.load_theme(theme_name, ui_mode)
        return palette_class

    except Exception as e:
        logger.error(f"Failed to load theme from config: {e}")
        return None


# =============================================================================
# ---- Exported classes
# =============================================================================

# Try to get palette from theme manager first, fall back to original logic
_theme_palette = _get_theme_palette()

if _theme_palette is not None:
    # Use theme manager palette
    SpyderPalette = _theme_palette
