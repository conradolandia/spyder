#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test the palettes directly, bypassing the theme_manager to isolate the issue
"""

import importlib
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("palette_debug")

# Remove any existing theme modules from cache to start fresh
for key in list(sys.modules.keys()):
    if 'colorsystem' in key or 'palette' in key:
        logger.info(f"Removing {key} from sys.modules")
        del sys.modules[key]

# Import the colorsystem modules directly
logger.info("\nImporting color system modules directly:")

# Import dracula colors
from spyder.utils.themes.dracula.colorsystem import Primary as DracPrimary
from spyder.utils.themes.dracula.colorsystem import Syntax as DracSyntax

# Import solarized colors
from spyder.utils.themes.solarized.colorsystem import Primary as SolarPrimary
from spyder.utils.themes.solarized.colorsystem import Syntax as SolarSyntax

# Import qdarkstyle colors
from spyder.utils.themes.qdarkstyle.colorsystem import Primary as QdsPrimary
from spyder.utils.themes.qdarkstyle.colorsystem import Syntax as QdsSyntax

logger.info(f"Dracula Primary.B10 = {DracPrimary.B10}")
logger.info(f"Solarized Primary.B10 = {SolarPrimary.B10}")
logger.info(f"QDarkStyle Primary.B10 = {QdsPrimary.B10}")

logger.info(f"Dracula Syntax.B10 = {DracSyntax.B10}")
logger.info(f"Solarized Syntax.B10 = {SolarSyntax.B10}")
logger.info(f"QDarkStyle Syntax.B10 = {QdsSyntax.B10}")

# Try to import the palette modules directly
logger.info("\nImporting palette modules directly:")

# Force clean all modules
for key in list(sys.modules.keys()):
    if any(x in key for x in ['dracula', 'solarized', 'qdarkstyle', 'colorsystem', 'palette']):
        logger.info(f"Removing {key} from sys.modules")
        del sys.modules[key]

# Reload Dracula palette
logger.info("\nLoading Dracula palette:")
spec = importlib.util.find_spec('spyder.utils.themes.dracula.palette')
drac_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = drac_module
spec.loader.exec_module(drac_module)

from spyder.utils.themes.dracula.palette import SpyderPaletteDark as DracPaletteDark
logger.info(f"Dracula Dark EDITOR_BACKGROUND = {DracPaletteDark.EDITOR_BACKGROUND}")

# Reload Solarized palette
logger.info("\nLoading Solarized palette:")
spec = importlib.util.find_spec('spyder.utils.themes.solarized.palette')
solar_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = solar_module
spec.loader.exec_module(solar_module)

from spyder.utils.themes.solarized.palette import SpyderPaletteDark as SolarPaletteDark
logger.info(f"Solarized Dark EDITOR_BACKGROUND = {SolarPaletteDark.EDITOR_BACKGROUND}")

# Reload QDarkStyle palette
logger.info("\nLoading QDarkStyle palette:")
spec = importlib.util.find_spec('spyder.utils.themes.qdarkstyle.palette')
qds_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qds_module
spec.loader.exec_module(qds_module)

from spyder.utils.themes.qdarkstyle.palette import SpyderPaletteDark as QdsPaletteDark
logger.info(f"QDarkStyle Dark EDITOR_BACKGROUND = {QdsPaletteDark.EDITOR_BACKGROUND}")

# Try loading colorsystem modules directly using their absolute paths
import os
logger.info("\nLoading colorsystem modules from file paths:")

dracula_color_path = os.path.abspath("/home/andi/Dev/Spyder/spyder/spyder/utils/themes/dracula/colorsystem.py")
solarized_color_path = os.path.abspath("/home/andi/Dev/Spyder/spyder/spyder/utils/themes/solarized/colorsystem.py")
qdarkstyle_color_path = os.path.abspath("/home/andi/Dev/Spyder/spyder/spyder/utils/themes/qdarkstyle/colorsystem.py")

logger.info(f"Dracula colorsystem.py exists: {os.path.exists(dracula_color_path)}")
logger.info(f"Solarized colorsystem.py exists: {os.path.exists(solarized_color_path)}")
logger.info(f"QDarkStyle colorsystem.py exists: {os.path.exists(qdarkstyle_color_path)}")

# Print the first few lines of each colorsystem.py to verify they're different
logger.info("\nComparing colorsystem.py files:")

with open(dracula_color_path, 'r') as f:
    dracula_content = f.read(500)  # Read first 500 chars
    
with open(solarized_color_path, 'r') as f:
    solarized_content = f.read(500)  # Read first 500 chars
    
with open(qdarkstyle_color_path, 'r') as f:
    qdarkstyle_content = f.read(500)  # Read first 500 chars

logger.info(f"Dracula colorsystem.py starts with:\n{dracula_content[:200]}...")
logger.info(f"Solarized colorsystem.py starts with:\n{solarized_content[:200]}...")
logger.info(f"QDarkStyle colorsystem.py starts with:\n{qdarkstyle_content[:200]}...")
