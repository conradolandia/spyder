# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Theme manager for Spyder's new theming system.
"""

# Standard library imports
import importlib
from pathlib import Path

# Local imports
from spyder.config.base import is_dark_interface, running_under_pytest
from spyder.config.fonts import MEDIUM, MONOSPACE
from spyder.plugins.help.utils.sphinxify import CSS_PATH



class ThemeManager:
    """Manager for Spyder's theming system."""

    def __init__(self):
        self._current_theme = None
        self._current_palette = None
        self._current_stylesheet = None
        self._current_theme_module = None  # Store the loaded theme module
        self._loaded_resource_modules = {}  # Keep references to resource modules

    @staticmethod
    def get_available_themes():
        """Get list of available themes from registered theme packages."""
        themes = []
        
        # List of theme packages to search
        # Add more package names here as needed
        theme_packages = ['spyder_themes']
        
        for package_name in theme_packages:
            try:
                package = importlib.import_module(package_name)
                if hasattr(package, 'THEMES') and hasattr(package, 'get_theme_module'):
                    # Iterate through registered themes
                    for theme_name in package.THEMES:
                        try:
                            theme_module = package.get_theme_module(theme_name)
                            # Validate theme has required attributes
                            if hasattr(theme_module, 'THEME_ID') and \
                               (hasattr(theme_module, 'SpyderPaletteDark') or \
                                hasattr(theme_module, 'SpyderPaletteLight')):
                                # Store full module path for loading
                                themes.append(f"{package_name}.{theme_name}")
                        except (ImportError, AttributeError, ValueError):
                            # Skip invalid themes
                            pass
            except ImportError:
                # Package not installed, skip
                pass
        
        return sorted(themes)

    @staticmethod
    def get_theme_modes(theme_name):
        """Get available UI modes by checking palette classes."""
        try:
            theme_module = importlib.import_module(theme_name)
            modes = []
            if hasattr(theme_module, 'SpyderPaletteDark'):
                modes.append('dark')
            if hasattr(theme_module, 'SpyderPaletteLight'):
                modes.append('light')
            return modes if modes else ['dark', 'light']
        except ImportError:
            return ['dark', 'light']

    @staticmethod
    def get_available_theme_variants():
        """Get list of available theme/mode combinations."""
        variants = []
        for theme_name in ThemeManager.get_available_themes():
            for mode in ThemeManager.get_theme_modes(theme_name):
                variants.append(f"{theme_name}/{mode}")

        return sorted(variants)
    
    @staticmethod
    def get_theme_display_name(theme_variant):
        """
        Get display name for a theme variant.
        
        Parameters
        ----------
        theme_variant : str
            Theme variant in format 'package.theme/mode' (e.g., 'spyder_themes.dracula/dark')
            
        Returns
        -------
        str
            User-friendly display name (e.g., 'Dracula Dark')
        """
        try:
            # Extract base theme name and mode
            if '/' in theme_variant:
                theme_path, mode = theme_variant.rsplit('/', 1)
            else:
                theme_path = theme_variant
                mode = None
            
            # For package-based themes, extract the theme name from docstring
            if '.' in theme_path:
                # Import the theme module to get its metadata
                theme_module = importlib.import_module(theme_path)
                
                # Extract theme name from docstring
                if theme_module.__doc__ and 'Theme:' in theme_module.__doc__:
                    lines = theme_module.__doc__.strip().split('\n')
                    for line in lines:
                        if line.strip().startswith('Theme:'):
                            theme_name = line.split('Theme:')[1].strip()
                            break
                    else:
                        # Fallback: use last part of path
                        theme_name = theme_path.split('.')[-1].replace('-', ' ').replace('_', ' ').title()
                else:
                    # Fallback: use last part of path
                    theme_name = theme_path.split('.')[-1].replace('-', ' ').replace('_', ' ').title()
            else:
                # Old-style theme, just capitalize
                theme_name = theme_path.capitalize()
            
            # Add mode if present
            if mode:
                return f"{theme_name} ({mode.title()})"
            else:
                return theme_name
                
        except Exception:
            # Ultimate fallback: just format the variant name
            return theme_variant.replace('_', ' ').replace('.', ' ').title()

    def get_syntax_color_scheme(self, palette):
        """
        Extract syntax highlighting colors from a theme palette.

        Parameters
        ----------
        palette : class
            Theme palette class with EDITOR_* attributes

        Returns
        -------
        dict
            Dictionary with syntax color scheme in the format expected by
            set_color_scheme(), compatible with COLOR_SCHEME_KEYS format.
        """
        # Map palette EDITOR_* attributes to COLOR_SCHEME_KEYS format
        color_scheme = {
            "background": palette.EDITOR_BACKGROUND,
            "currentline": palette.EDITOR_CURRENTLINE,
            "currentcell": palette.EDITOR_CURRENTCELL,
            "occurrence": palette.EDITOR_OCCURRENCE,
            "ctrlclick": palette.EDITOR_CTRLCLICK,
            "sideareas": palette.EDITOR_SIDEAREAS,
            "matched_p": palette.EDITOR_MATCHED_P,
            "unmatched_p": palette.EDITOR_UNMATCHED_P,
            "normal": palette.EDITOR_NORMAL,
            "keyword": palette.EDITOR_KEYWORD,
            "builtin": palette.EDITOR_BUILTIN,
            "definition": palette.EDITOR_DEFINITION,
            "comment": palette.EDITOR_COMMENT,
            "string": palette.EDITOR_STRING,
            "number": palette.EDITOR_NUMBER,
            "instance": palette.EDITOR_INSTANCE,
            "magic": palette.EDITOR_MAGIC,
        }

        return color_scheme

    def export_theme_to_config(self, theme_name, ui_mode, replace=False):
        """
        Export theme syntax colors to user configuration file.

        Parameters
        ----------
        theme_name : str
            Name of the theme
        ui_mode : str
            'dark' or 'light' mode
        replace : bool, optional
            If True, overwrites existing colors (for reset to defaults).
            If False, only adds if not already present. Default is False.
        """
        # Import here to avoid circular dependency
        from spyder.config.gui import set_color_scheme
        from spyder.config.manager import CONF

        # Remember current theme to restore later
        current_theme = self._current_theme

        # Load the theme to get its palette (without auto-export to avoid circular calls)
        palette, _ = self._load_theme_internal(theme_name, ui_mode)

        # Get the syntax color scheme from the theme
        color_scheme = self.get_syntax_color_scheme(palette)

        # Build the full theme variant name (e.g., "solarized/dark")
        variant_name = f"{theme_name}/{ui_mode}"

        # Force direct update of colors in config when replace=True
        if replace:
            section = "appearance"
            for key, value in color_scheme.items():
                option = f"{variant_name}/{key}"
                CONF.set(section, option, value)
        else:
            # Use set_color_scheme for normal operation (when not forcing replacement)
            set_color_scheme(variant_name, color_scheme, replace=replace)
        
        # Also save the display name for the theme variant
        display_name = ThemeManager.get_theme_display_name(variant_name)
        CONF.set("appearance", f"{variant_name}/name", display_name)
        
        # Restore original theme if different from what we just exported
        if current_theme and current_theme != theme_name:
            try:
                # Determine ui_mode from current interface state
                restore_ui_mode = "dark" if is_dark_interface() else "light"
                self._load_theme_internal(current_theme, restore_ui_mode)
            except Exception:
                # If restoration fails, just continue
                pass

    def export_all_themes_to_config(self):
        """
        Export all available theme variants to config file.
        
        This ensures all themes are available in the config for the preferences UI
        and for users to customize. Only exports themes that don't already exist
        in the config (doesn't overwrite user customizations).
        """
        from spyder.config.manager import CONF
        from spyder.utils.syntaxhighlighters import COLOR_SCHEME_KEYS
        import logging
        logger = logging.getLogger(__name__)
        
        # Remember the current theme to restore it after exporting all themes
        current_theme = self._current_theme
        
        for theme_name in self.get_available_themes():
            for ui_mode in self.get_theme_modes(theme_name):
                variant_name = f"{theme_name}/{ui_mode}"
                
                # Check if this theme variant exists and is complete in config
                # For a theme to be considered complete, it needs all color keys
                is_complete = True
                try:
                    # Check for name first
                    CONF.get("appearance", f"{variant_name}/name")
                    
                    # Then check for all required color keys
                    for key in COLOR_SCHEME_KEYS:
                        CONF.get("appearance", f"{variant_name}/{key}")
                except Exception:
                    # If any check fails, the theme is incomplete
                    is_complete = False
                
                if not is_complete:
                    # Theme doesn't exist or is incomplete, we need to load it first
                    # to get its proper colors, then export
                    try:
                        # Load the theme palette without auto-exporting 
                        # (using internal method to avoid circular calls)
                        palette, _ = self._load_theme_internal(theme_name, ui_mode)
                        
                        # Now manually extract colors from the correct palette and save to config
                        color_scheme = self.get_syntax_color_scheme(palette)
                        
                        # Import here to avoid circular dependency
                        from spyder.config.gui import set_color_scheme
                        set_color_scheme(variant_name, color_scheme, replace=False)
                        
                        # Set the display name
                        display_name = ThemeManager.get_theme_display_name(variant_name)
                        CONF.set("appearance", f"{variant_name}/name", display_name)
                        
                        logger.info(f"Exported theme {variant_name} to config")
                    except Exception as e:
                        # Log but don't fail if a theme can't be exported
                        logger.warning(f"Failed to export theme {variant_name}: {e}")
        
        # Restore original theme if needed
        if current_theme and current_theme != self._current_theme:
            try:
                # Determine ui_mode from current interface state
                restore_ui_mode = "dark" if is_dark_interface() else "light"
                self.load_theme(current_theme, restore_ui_mode)
            except Exception:
                # If restoration fails, just continue with the current theme
                pass

    def _load_theme_internal(self, theme_name, ui_mode=None):
        """Load theme using standard package import."""
        if ui_mode is None:
            ui_mode = "dark" if is_dark_interface() else "light"
        
        # Import theme module using full module path
        theme_module = importlib.import_module(theme_name)
        
        # Get palette class
        if ui_mode == "dark":
            if not hasattr(theme_module, 'SpyderPaletteDark'):
                raise ValueError(f"Theme '{theme_name}' has no SpyderPaletteDark class")
            palette_class = theme_module.SpyderPaletteDark
        else:
            if not hasattr(theme_module, 'SpyderPaletteLight'):
                raise ValueError(f"Theme '{theme_name}' has no SpyderPaletteLight class")
            palette_class = theme_module.SpyderPaletteLight
        
        # Load stylesheet
        stylesheet = self._load_stylesheet(theme_name, ui_mode)
        
        return palette_class, stylesheet

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
        # Use internal method to load theme
        palette, stylesheet = self._load_theme_internal(theme_name, ui_mode)

        # Store current theme info
        self._current_theme = theme_name
        self._current_palette = palette
        self._current_stylesheet = stylesheet

        # Manually and directly ensure theme colors are saved to config
        # This approach bypasses any potential module caching issues
        # by using palette values directly from the loaded theme
        from spyder.config.manager import CONF
                      
        # Map palette attributes to config keys
        palette_attrs = {
            "background": palette.EDITOR_BACKGROUND,
            "currentline": palette.EDITOR_CURRENTLINE, 
            "currentcell": palette.EDITOR_CURRENTCELL,
            "occurrence": palette.EDITOR_OCCURRENCE,
            "ctrlclick": palette.EDITOR_CTRLCLICK,
            "sideareas": palette.EDITOR_SIDEAREAS,
            "matched_p": palette.EDITOR_MATCHED_P,
            "unmatched_p": palette.EDITOR_UNMATCHED_P,
            "normal": palette.EDITOR_NORMAL,
            "keyword": palette.EDITOR_KEYWORD,
            "builtin": palette.EDITOR_BUILTIN,
            "definition": palette.EDITOR_DEFINITION,
            "comment": palette.EDITOR_COMMENT,
            "string": palette.EDITOR_STRING,
            "number": palette.EDITOR_NUMBER,
            "instance": palette.EDITOR_INSTANCE,
            "magic": palette.EDITOR_MAGIC,
        }
        
        # Set all colors directly in the config
        variant_name = f"{theme_name}/{ui_mode}"
        for key, value in palette_attrs.items():
            option = f"{variant_name}/{key}"
            CONF.set("appearance", option, value)
            
        # Also set the display name using the helper method
        display_name = ThemeManager.get_theme_display_name(variant_name)
        CONF.set("appearance", f"{variant_name}/name", display_name)

        return palette, stylesheet

    def _load_stylesheet(self, theme_name, ui_mode):
        """Load the QSS stylesheet for a theme."""
        # Get theme module path
        theme_module = importlib.import_module(theme_name)
        theme_path = Path(theme_module.__path__[0])
        
        # Construct stylesheet paths
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
    # List of available theme variants (will be populated dynamically)
    "names": [],
    # Default to qdarkstyle/dark if no selection exists
    "selected": "qdarkstyle/dark",
}


# Global theme manager instance
theme_manager = ThemeManager()
