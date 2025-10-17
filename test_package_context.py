#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to diagnose package context issues with theme loading.
"""

import sys
import importlib.util
import importlib.machinery
from pathlib import Path

# Test theme path
theme_path = Path("/home/andi/Dev/Spyder/spyder/spyder/utils/themes/solarized")
palette_path = theme_path / "palette.py"
colorsystem_path = theme_path / "colorsystem.py"

print("=" * 70)
print("DIAGNOSTIC TEST: Theme Package Context")
print("=" * 70)

# Test 1: Simple import with sys.path modification
print("\n[TEST 1] Simple import with sys.path modification")
print("-" * 70)
try:
    # Clear any cached modules
    if 'colorsystem' in sys.modules:
        del sys.modules['colorsystem']
    
    # Add theme directory to sys.path
    sys.path.insert(0, str(theme_path))
    
    # Load palette module
    spec = importlib.util.spec_from_file_location("test_palette_1", palette_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    print(f"✓ Successfully loaded palette")
    print(f"  - SpyderPaletteDark.EDITOR_BACKGROUND = {module.SpyderPaletteDark.EDITOR_BACKGROUND}")
    
    sys.path.remove(str(theme_path))
except Exception as e:
    print(f"✗ Failed: {type(e).__name__}: {e}")

# Test 2: Package-based import with proper module registration
print("\n[TEST 2] Package-based import with sys.modules registration")
print("-" * 70)
try:
    # Clear all cached modules
    for key in list(sys.modules.keys()):
        if 'colorsystem' in key or 'solarized' in key:
            del sys.modules[key]
    
    # Create package structure in sys.modules
    package_name = "spyder.utils.themes.solarized"
    
    # Check if parent packages exist
    if "spyder" not in sys.modules:
        print("  Note: 'spyder' package not in sys.modules")
    if "spyder.utils" not in sys.modules:
        print("  Note: 'spyder.utils' package not in sys.modules")
    if "spyder.utils.themes" not in sys.modules:
        print("  Note: 'spyder.utils.themes' package not in sys.modules")
    
    # Try to load colorsystem first with full package name
    colorsystem_name = f"{package_name}.colorsystem"
    spec = importlib.util.spec_from_file_location(colorsystem_name, colorsystem_path)
    colorsystem_module = importlib.util.module_from_spec(spec)
    sys.modules[colorsystem_name] = colorsystem_module
    spec.loader.exec_module(colorsystem_module)
    
    print(f"✓ Successfully loaded {colorsystem_name}")
    print(f"  - Primary.B10 = {colorsystem_module.Primary.B10}")
    
    # Now try to load palette with relative imports
    palette_name = f"{package_name}.palette"
    spec = importlib.util.spec_from_file_location(palette_name, palette_path)
    palette_module = importlib.util.module_from_spec(spec)
    sys.modules[palette_name] = palette_module
    
    # Set __package__ attribute for relative imports
    palette_module.__package__ = package_name
    
    spec.loader.exec_module(palette_module)
    
    print(f"✓ Successfully loaded {palette_name}")
    print(f"  - SpyderPaletteDark.EDITOR_BACKGROUND = {palette_module.SpyderPaletteDark.EDITOR_BACKGROUND}")
    
except Exception as e:
    print(f"✗ Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check what happens with __name__ and __package__
print("\n[TEST 3] Check module attributes")
print("-" * 70)
try:
    # Clear modules
    if 'colorsystem' in sys.modules:
        del sys.modules['colorsystem']
    
    sys.path.insert(0, str(theme_path))
    
    spec = importlib.util.spec_from_file_location("test_palette_3", palette_path)
    module = importlib.util.module_from_spec(spec)
    
    print(f"Before exec_module:")
    print(f"  - module.__name__ = {module.__name__}")
    print(f"  - module.__package__ = {getattr(module, '__package__', 'NOT SET')}")
    print(f"  - module.__file__ = {module.__file__}")
    print(f"  - spec.name = {spec.name}")
    print(f"  - spec.parent = {spec.parent}")
    
    # Try setting __package__ before executing
    module.__package__ = ""  # Empty string means no package
    
    spec.loader.exec_module(module)
    
    print(f"\nAfter exec_module:")
    print(f"  - module.__name__ = {module.__name__}")
    print(f"  - module.__package__ = {module.__package__}")
    print(f"✓ Successfully loaded with __package__ = ''")
    print(f"  - SpyderPaletteDark.EDITOR_BACKGROUND = {module.SpyderPaletteDark.EDITOR_BACKGROUND}")
    
    sys.path.remove(str(theme_path))
except Exception as e:
    print(f"✗ Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Try with proper parent package hierarchy
print("\n[TEST 4] Full package hierarchy setup")
print("-" * 70)
try:
    # Clear modules
    for key in list(sys.modules.keys()):
        if 'test_' in key or 'colorsystem' in key or 'solarized' in key:
            if key in sys.modules:
                del sys.modules[key]
    
    # Create the full package hierarchy
    import types
    
    # Create parent packages if they don't exist
    if "spyder" not in sys.modules:
        spyder_pkg = types.ModuleType("spyder")
        spyder_pkg.__path__ = []
        sys.modules["spyder"] = spyder_pkg
        print("  Created 'spyder' package")
    
    if "spyder.utils" not in sys.modules:
        utils_pkg = types.ModuleType("spyder.utils")
        utils_pkg.__path__ = []
        sys.modules["spyder.utils"] = utils_pkg
        print("  Created 'spyder.utils' package")
    
    if "spyder.utils.themes" not in sys.modules:
        themes_pkg = types.ModuleType("spyder.utils.themes")
        themes_pkg.__path__ = [str(theme_path.parent)]
        sys.modules["spyder.utils.themes"] = themes_pkg
        print("  Created 'spyder.utils.themes' package")
    
    # Now create the solarized package
    solarized_pkg = types.ModuleType("spyder.utils.themes.solarized")
    solarized_pkg.__path__ = [str(theme_path)]
    solarized_pkg.__package__ = "spyder.utils.themes.solarized"
    sys.modules["spyder.utils.themes.solarized"] = solarized_pkg
    print("  Created 'spyder.utils.themes.solarized' package")
    
    # Load colorsystem into the package
    colorsystem_name = "spyder.utils.themes.solarized.colorsystem"
    spec = importlib.util.spec_from_file_location(colorsystem_name, colorsystem_path)
    colorsystem_module = importlib.util.module_from_spec(spec)
    colorsystem_module.__package__ = "spyder.utils.themes.solarized"
    sys.modules[colorsystem_name] = colorsystem_module
    spec.loader.exec_module(colorsystem_module)
    print(f"  Loaded {colorsystem_name}")
    print(f"    - Primary.B10 = {colorsystem_module.Primary.B10}")
    
    # Load palette with relative imports
    palette_name = "spyder.utils.themes.solarized.palette"
    spec = importlib.util.spec_from_file_location(palette_name, palette_path)
    palette_module = importlib.util.module_from_spec(spec)
    palette_module.__package__ = "spyder.utils.themes.solarized"
    sys.modules[palette_name] = palette_module
    
    print(f"\n  Before executing palette module:")
    print(f"    - __name__ = {palette_module.__name__}")
    print(f"    - __package__ = {palette_module.__package__}")
    
    spec.loader.exec_module(palette_module)
    
    print(f"✓ Successfully loaded {palette_name}")
    print(f"  - SpyderPaletteDark.EDITOR_BACKGROUND = {palette_module.SpyderPaletteDark.EDITOR_BACKGROUND}")
    
except Exception as e:
    print(f"✗ Failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTIC TEST COMPLETE")
print("=" * 70)
