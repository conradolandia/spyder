# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Theme manager for Spyder's new theming system.
"""

# Standard library imports
import ast
import sys
from pathlib import Path

import pkg_resources

# Local imports
from spyder.config.base import running_under_pytest
from spyder.config.fonts import MEDIUM, MONOSPACE
from spyder.plugins.help.utils.sphinxify import CSS_PATH

# Theme configuration
THEMES_DIR = Path(pkg_resources.resource_filename("spyder.utils", "themes"))
SELECTED_THEME = "solarized"  # Hardcoded theme selection for now
SELECTED_UI_MODE = "dark"  # Hardcoded variant selection for now
SELECTED = f"{SELECTED_THEME}/{SELECTED_UI_MODE}"


class ThemeManager:
    """Manager for Spyder's theming system."""

    def __init__(self):
        # Use package resources to find themes directory
        self._themes_dir = THEMES_DIR
        self._current_theme = None
        self._current_palette = None
        self._current_stylesheet = None
        self._current_theme_module = None  # Store the loaded theme module
        self._loaded_resource_modules = {}  # Keep references to resource modules
        self._current_ui_mode = None  # Track current interface mode

    @staticmethod
    def is_dark_interface():
        from spyder.config.manager import CONF

        return CONF.get("appearance", "ui_theme") == "dark"

    @staticmethod
    def get_available_themes():
        """Get list of available themes."""
        if not THEMES_DIR.exists():
            return []

        themes = []
        for theme_dir in THEMES_DIR.iterdir():
            if theme_dir.is_dir() and (theme_dir / "palette.py").exists():
                themes.append(theme_dir.name)
            else:
                raise RuntimeError(
                    "Theme directory structure is invalid: "
                    f"missing palette.py in theme subdirectory {theme_dir}."
                )

        return sorted(themes)

    @staticmethod
    def get_theme_modes(theme_name):
        """
        Get available UI modes for a specific theme.

        Parameters
        ----------
        theme_name : str
            Name of the theme

        Returns
        -------
        list of str
            List of available mode IDs (e.g., ['dark', 'light'])
        """
        palette_file = THEMES_DIR / theme_name / "palette.py"
        modes = []

        try:
            with open(palette_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            # Iterate through top-level class definitions
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    # Look for ID attribute in class body
                    for item in node.body:
                        if (
                            isinstance(item, ast.Assign)
                            and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                            and item.targets[0].id == "ID"
                            and isinstance(item.value, ast.Constant)
                        ):
                            mode_id = item.value.value
                            if mode_id in ("dark", "light"):
                                modes.append(mode_id)
                            break
        except Exception:
            pass

        return modes

    @staticmethod
    def get_available_theme_variants():
        """Get list of available theme/mode combinations."""
        variants = []
        for theme_name in ThemeManager.get_available_themes():
            for mode in ThemeManager.get_theme_modes(theme_name):
                variants.append(f"{theme_name}/{mode}")

        return sorted(variants)

    def load_theme(self, theme_name, ui_mode=None):
        """
        Load a theme by name.

        Parameters
        ----------
        theme_name : str
            Name of the theme to load
        ui_mode : str, optional
            'dark' or 'light'. If None, uses current interface mode.

        Returns
        -------
        tuple
            (palette, stylesheet) for the loaded theme
        """
        if ui_mode is None:
            ui_mode = "dark" if self.is_dark_interface() else "light"

        theme_path = self._themes_dir / theme_name

        if not theme_path.exists():
            raise ValueError(f"Theme '{theme_name}' not found")

        # Import the theme module
        theme_module_path = theme_path / "palette.py"
        if not theme_module_path.exists():
            raise ValueError(f"Theme '{theme_name}' has no palette.py")

        # Add the theme directory to sys.path temporarily
        theme_dir_str = str(theme_path)
        if theme_dir_str not in sys.path:
            sys.path.insert(0, theme_dir_str)

        try:
            # First, load the colorsystem module if it exists
            colorsystem_path = theme_path / "colorsystem.py"
            colorsystem_namespace = {}
            if colorsystem_path.exists():
                with open(colorsystem_path, "r", encoding="utf-8") as f:
                    colorsystem_code = f.read()
                exec(colorsystem_code, colorsystem_namespace)

            # Import the theme module using exec
            with open(theme_module_path, "r", encoding="utf-8") as f:
                theme_code = f.read()

            # Create a namespace for the theme module with necessary globals
            theme_namespace = {
                "__name__": f"{theme_name}_palette",
                "__file__": str(theme_module_path),
                "__package__": theme_name,
            }

            # Add colorsystem classes to the namespace
            theme_namespace.update(colorsystem_namespace)

            # Execute the theme code in the namespace
            exec(theme_code, theme_namespace)

            # Create a simple module-like object
            class ThemeModule:
                def __init__(self, namespace):
                    self.__dict__.update(namespace)

            theme_module = ThemeModule(theme_namespace)

            # Get the SpyderPalette from the theme (it's already set based on interface mode)
            palette_class = getattr(theme_module, "SpyderPalette", None)

            if palette_class is None:
                raise ValueError(f"Theme '{theme_name}' has no SpyderPalette defined")

            # The palette is now a class, not an instance, so we can use it directly
            # or create an instance if needed
            palette = palette_class

            # Load the stylesheet
            stylesheet = self._load_stylesheet(theme_name, ui_mode)

            # Store current theme info
            self._current_theme = theme_name
            self._current_palette = palette
            self._current_stylesheet = stylesheet
            self._current_theme_module = theme_namespace  # Store the theme module
            self._current_ui_mode = ui_mode

            return palette, stylesheet

        finally:
            # Remove theme directory from sys.path
            if theme_dir_str in sys.path:
                sys.path.remove(theme_dir_str)

    def _load_stylesheet(self, theme_name, ui_mode):
        """Load the QSS stylesheet for a theme."""
        theme_path = self._themes_dir / theme_name

        if ui_mode == "dark":
            qss_file = theme_path / "dark" / "darkstyle.qss"
            rc_file = theme_path / "dark" / "pyqt5_darkstyle_rc.py"
        else:
            qss_file = theme_path / "light" / "lightstyle.qss"
            rc_file = theme_path / "light" / "pyqt5_lightstyle_rc.py"

        if not qss_file.exists():
            raise ValueError(
                f"Stylesheet not found for theme '{theme_name}' in {ui_mode} mode"
            )

        # Load the resources if they exist
        if rc_file.exists():
            self._load_theme_resources(rc_file)

        with open(qss_file, "r", encoding="utf-8") as f:
            return f.read()

    def _load_theme_resources(self, rc_file):
        """Load theme resources into Qt resource system."""
        try:
            # Import the resource module directly (like QDarkStyleSheet does)
            import importlib.util
            import logging

            logger = logging.getLogger(__name__)

            # Create a unique module name based on the file path
            module_name = f"theme_resources_{rc_file.stem}_{hash(str(rc_file)) % 10000}"

            spec = importlib.util.spec_from_file_location(module_name, rc_file)
            resource_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(resource_module)

            # Keep a reference to the module to prevent garbage collection
            self._loaded_resource_modules[str(rc_file)] = resource_module

            logger.info(f"Successfully loaded theme resources from {rc_file}")

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to load theme resources from {rc_file}: {e}")

    def get_current_theme(self):
        """Get the currently loaded theme name."""
        return self._current_theme

    def get_current_stylesheet(self):
        """Get the currently loaded stylesheet."""
        return self._current_stylesheet


# Global appearance object
APPEARANCE = {
    "css_path": CSS_PATH,
    "icon_theme": "spyder 3",
    # This is our monospace font
    "font/family": MONOSPACE,
    "font/size": MEDIUM,
    "font/italic": False,
    "font/bold": False,
    # We set the app font used in the system when Spyder starts, so we don't
    # need to do it here.
    "app_font/family": "Arial" if running_under_pytest() else "",
    # This default value helps to do visual checks in our tests when run
    # independently and avoids Qt warnings related to a null font size. It can
    # also be useful in case we fail to detect the interface font.
    "app_font/size": 10,
    "app_font/italic": False,
    "app_font/bold": False,
    "use_system_font": True,
    # We set these values at startup too.
    "monospace_app_font/family": "",
    "monospace_app_font/size": 0,
    "monospace_app_font/italic": False,
    "monospace_app_font/bold": False,
    "ui_mode": SELECTED_UI_MODE,
    # Themes (was 'names')
    "themes": ThemeManager.get_available_theme_variants(),
    "selected": SELECTED,
}


# Global theme manager instance
theme_manager = ThemeManager()
