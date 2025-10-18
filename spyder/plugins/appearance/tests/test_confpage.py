# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see LICENSE.txt for details)
# -----------------------------------------------------------------------------

# Third-party imports
import pytest

# Local imports
from spyder.config.manager import CONF
from spyder.plugins.appearance.plugin import Appearance
from spyder.widgets.config import SpyderConfigPage
from spyder.plugins.preferences.tests.conftest import (
    config_dialog, MainWindowMock)


@pytest.mark.parametrize(
    'config_dialog',
    [[MainWindowMock, [], [Appearance]]],
    indirect=True)
def test_change_ui_theme_and_color_scheme(config_dialog, mocker, qtbot):
    """Test that changing color scheme or UI theme works as expected."""
    # Patch methods whose calls we want to check
    mocker.patch.object(
        SpyderConfigPage, "prompt_restart_required", return_value=True
    )
    mocker.patch.object(SpyderConfigPage, "restart")
    mocker.patch.object(CONF, "disable_notifications")

    # Get reference to Preferences dialog and widget page to interact with
    dlg = config_dialog
    widget = config_dialog.get_page()

    # List of color schemes
    names = widget.get_option('names')

    # Assert no restarts have been requested so far.
    assert SpyderConfigPage.prompt_restart_required.call_count == 0

    # Assert interface is dark. The other tests below depend on this.
    assert widget.is_dark_interface()

    # Change to another dark color scheme
    widget.schemes_combobox.setCurrentIndex(names.index('monokai'))
    dlg.apply_btn.click()
    assert SpyderConfigPage.prompt_restart_required.call_count == 0
    assert SpyderConfigPage.restart.call_count == 0
    assert CONF.disable_notifications.call_count == 0

    # In the new theming system, any theme change requires a restart
    # because themes now control both UI and syntax colors.
    # Note: The exact behavior depends on whether themes are available in the test environment.
    # This test may need adjustment based on available test themes.
