# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2009- Spyder Project Contributors
#
# Distributed under the terms of the MIT License
# (see spyder/__init__.py for details)
# -----------------------------------------------------------------------------

"""
Appearance Plugin.
"""

# Local imports
from spyder.api.plugin_registration.decorators import (
    on_plugin_available,
    on_plugin_teardown,
)
from spyder.api.plugins import Plugins, SpyderPluginV2
from spyder.api.translations import _
from spyder.config.manager import CONF
from spyder.plugins.appearance.confpage import AppearanceConfigPage
from spyder.utils.theme_manager import theme_manager


# --- Plugin
# ----------------------------------------------------------------------------
class Appearance(SpyderPluginV2):
    """
    Appearance Plugin.
    """

    NAME = "appearance"
    # Appearance should load first among config plugins
    REQUIRES = [Plugins.Preferences]
    CONTAINER_CLASS = None
    CONF_SECTION = NAME
    CONF_WIDGET_CLASS = AppearanceConfigPage
    CONF_FILE = False
    CAN_BE_DISABLED = False

    # ---- SpyderPluginV2 API
    # -------------------------------------------------------------------------
    @staticmethod
    def get_name():
        return _("Appearance")

    @staticmethod
    def get_description():
        return _("Manage application appearance and themes.")

    @classmethod
    def get_icon(cls):
        return cls.create_icon('eyedropper')

    def on_initialize(self):
        """Initialize the appearance plugin."""
        # Ensure theme names are populated in config for other plugins to use
        # Get available theme variants and populate the names config
        theme_variants = theme_manager.get_available_theme_variants()
        if theme_variants:
            CONF.set('appearance', 'names', theme_variants)

    @on_plugin_available(plugin=Plugins.Preferences)
    def register_preferences(self):
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.register_plugin_preferences(self)

    @on_plugin_teardown(plugin=Plugins.Preferences)
    def deregister_preferences(self):
        preferences = self.get_plugin(Plugins.Preferences)
        preferences.deregister_plugin_preferences(self)
