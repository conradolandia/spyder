#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final debug for theme color issues
"""

from spyder.utils.theme_manager import theme_manager
from spyder.config.manager import CONF

# Load the solarized theme's palette directly
palette, _ = theme_manager._load_theme_internal("solarized", "dark")

# Extract the expected color scheme
color_scheme = theme_manager.get_syntax_color_scheme(palette)
expected_background = color_scheme['background']  # Should be #002B36

# Get current value from config
current_background = CONF.get("appearance", "solarized/dark/background")

print(f"Expected solarized background: {expected_background}")
print(f"Current solarized background in config: {current_background}")

# Direct update and verify
print("\nDirectly updating config...")
CONF.set("appearance", "solarized/dark/background", expected_background)
updated_background = CONF.get("appearance", "solarized/dark/background")
print(f"After update: {updated_background}")

# Force a reload of the solarized theme
print("\nForcing theme reload...")
theme_manager.export_theme_to_config("solarized", "dark", replace=True)

# Verify after export
final_background = CONF.get("appearance", "solarized/dark/background") 
print(f"After export_theme_to_config: {final_background}")

print("\nExit to see if changes persist in the config file.")
