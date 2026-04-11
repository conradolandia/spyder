# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# ----------------------------------------------------------------------------

"""
Testing utilities to be used with pytest.
"""

# Third party imports
import pytest

# Local imports
from spyder.config.manager import CONF
from spyder.plugins.preferences.plugin import Preferences
from spyder.plugins.preferences.tests.config_dialog_helpers import (
    MainWindowMock,
    config_dialog,
)

# Re-export for tests that import from this module
__all__ = [
    'MainWindowMock',
    'config_dialog',
    'global_config_dialog',
]


@pytest.fixture
def global_config_dialog(qtbot):
    """
    Fixture that includes the general preferences options.

    These options are the ones not tied to a specific plugin.
    """
    mainwindow = MainWindowMock(None)
    qtbot.addWidget(mainwindow)

    preferences = Preferences(mainwindow, CONF)
    preferences.open_dialog()
    container = preferences.get_container()
    dlg = container.dialog

    yield dlg

    dlg.close()
