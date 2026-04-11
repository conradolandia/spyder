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
from spyder.plugins.preferences.tests.config_dialog_helpers import (
    MainWindowMock,
    config_dialog,  # noqa: F401 — registers fixture for this test module
)


@pytest.mark.parametrize(
    'config_dialog',
    [[MainWindowMock, [], [Appearance]]],
    indirect=True)
def test_apply_theme_variant_triggers_restart_prompt(config_dialog, mocker, qtbot):
    """Built-in theme variant change + Apply: one restart prompt, mute ``selected``."""
    mocker.patch.object(
        SpyderConfigPage, "prompt_restart_required", return_value=False
    )
    mocker.patch.object(SpyderConfigPage, "restart")
    mocker.patch.object(CONF, "disable_notifications")

    dlg = config_dialog
    widget = config_dialog.get_page()

    assert SpyderConfigPage.prompt_restart_required.call_count == 0

    assert widget.is_dark_interface()

    cb = widget.schemes_combobox
    current = widget.current_scheme
    other_index = None
    for i in range(cb.count()):
        data = cb.itemData(i)
        if data is not None and data != current:
            other_index = i
            break
    assert other_index is not None
    cb.setCurrentIndex(other_index)
    dlg.apply_btn.click()
    assert SpyderConfigPage.prompt_restart_required.call_count == 1
    assert SpyderConfigPage.restart.call_count == 0
    assert CONF.disable_notifications.call_count == 1


@pytest.mark.parametrize(
    'config_dialog',
    [[MainWindowMock, [], [Appearance]]],
    indirect=True)
def test_apply_monospace_font_only_no_restart_prompt(config_dialog, mocker, qtbot):
    """Monospace font is not a restart option; theme unchanged → no prompt, no mute."""
    mocker.patch.object(
        SpyderConfigPage, "prompt_restart_required", return_value=False
    )
    mocker.patch.object(SpyderConfigPage, "restart")
    mocker.patch.object(CONF, "disable_notifications")

    dlg = config_dialog
    widget = dlg.get_page()
    sizebox = widget.plain_text_font.sizebox

    v = sizebox.value()
    if v < sizebox.maximum():
        sizebox.setValue(v + 1)
    else:
        sizebox.setValue(v - 1)

    dlg.apply_btn.click()
    assert SpyderConfigPage.prompt_restart_required.call_count == 0
    assert SpyderConfigPage.restart.call_count == 0
    assert CONF.disable_notifications.call_count == 0
