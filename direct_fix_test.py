#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Direct fix for theme color issues
"""

from spyder.utils.theme_manager import theme_manager
from spyder.config.manager import CONF

print("==== Initial state ====")
print(f"solarized/dark/background = {CONF.get('appearance', 'solarized/dark/background')}")

# First, load the theme properly to get the palette
palette, _ = theme_manager._load_theme_internal("solarized", "dark")

# Then, extract the color scheme
color_scheme = theme_manager.get_syntax_color_scheme(palette)

print("\n==== Color scheme from palette ====")
print(f"background = {color_scheme['background']}")  # Should be #002B36
print(f"normal = {color_scheme['normal']}")

print("\n==== Directly updating config ====")
for key, value in color_scheme.items():
    option = f"solarized/dark/{key}"
    CONF.set("appearance", option, value)
    print(f"Set {option} = {value}")

print("\n==== Verifying config after update ====")
print(f"solarized/dark/background = {CONF.get('appearance', 'solarized/dark/background')}")
print(f"solarized/dark/normal = {CONF.get('appearance', 'solarized/dark/normal')}")

print("\nScript completed - please check your config file to see if the changes persisted.")
print(f"Config file: {CONF._user_config._path}/spyder.ini")
