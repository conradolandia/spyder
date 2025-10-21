# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""Appearance entry in Preferences."""

import configparser
import sys

import qstylizer.style
from qtconsole.styles import dark_color
from qtpy.QtCore import Qt, Slot
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFontComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from spyder.api.plugin_registration.registry import PLUGIN_REGISTRY
from spyder.api.preferences import PluginConfigPage
from spyder.api.translations import _
from spyder.config.gui import get_font, set_font

from spyder.config.manager import CONF
from spyder.plugins.appearance.widgets import SchemeEditor
from spyder.utils import syntaxhighlighters
from spyder.utils.palette import SpyderPalette
from spyder.utils.stylesheet import AppStyle
from spyder.widgets.simplecodeeditor import SimpleCodeEditor


PREVIEW_TEXT = (
    '"""A string"""\n\n'
    '# A comment\n\n'
    'class Foo(object):\n'
    '    def __init__(self):\n'
    '        bar = 42\n'
    '        print(bar)\n'
)


class AppearanceConfigPage(PluginConfigPage):

    def __init__(self, plugin, parent):
        super().__init__(plugin, parent)
        self._is_shown = False

        # Notifications for this option are disabled when the plugin is
        # initialized, so we need to restore them here.
        CONF.restore_notifications(section='appearance', option='selected')

    def setup_page(self):
        names = self.get_option("names")
        try:
            names.pop(names.index(u'Custom'))
        except ValueError:
            pass
        custom_names = self.get_option("custom_names", [])

        # UI theme options
        ui_group = QGroupBox(_("Interface Theme"))

        # UI theme Widgets
        edit_button = QPushButton(_("Edit selected syntax theme"))
        create_button = QPushButton(_("Create new syntax theme"))
        self.delete_button = QPushButton(_("Delete syntax theme"))
        self.reset_button = QPushButton(_("Reset to defaults"))

        self.stacked_widget = QStackedWidget(self)
        self.scheme_editor_dialog = SchemeEditor(
            parent=self,
            stack=self.stacked_widget
        )

        self.scheme_choices_dict = {}
        schemes_combobox_widget = self.create_combobox(
            '', [('', '')], 'selected', items_elide_mode=Qt.ElideNone,
            restart=True
        )
        self.schemes_combobox = schemes_combobox_widget.combobox

        # UI theme layout
        ui_layout = QGridLayout(ui_group)
        if sys.platform == "darwin":
            # Default spacing is too big on Mac
            ui_layout.setVerticalSpacing(2 * AppStyle. MarginSize)

        btns = [self.schemes_combobox, edit_button, self.reset_button,
                create_button, self.delete_button]
        for i, btn in enumerate(btns):
            ui_layout.addWidget(btn, i, 1)
        ui_layout.setColumnStretch(0, 1)
        ui_layout.setColumnStretch(1, 2)
        ui_layout.setColumnStretch(2, 1)
        ui_layout.setContentsMargins(0, 12, 0, 12)

        # Fonts options
        fonts_group = QGroupBox(_("Fonts"))

        # Fonts widgets
        self.plain_text_font = self.create_fontgroup(
            option='font',
            title=_("Monospace"),
            fontfilters=QFontComboBox.MonospacedFonts,
            without_group=True)

        self.app_font = self.create_fontgroup(
            option='app_font',
            title=_("Interface"),
            fontfilters=QFontComboBox.ProportionalFonts,
            restart=True,
            without_group=True)

        # System font checkbox
        if sys.platform == 'darwin':
            system_font_tip = _("Changing the interface font does not work "
                                "reliably on macOS")
        else:
            system_font_tip = None

        system_font_checkbox = self.create_checkbox(
            _("Use the system default interface font"),
            'use_system_font',
            restart=True,
            tip=system_font_tip
        )

        # Preview widgets
        preview_editor_label = QLabel(_("Editor"))
        self.preview_editor = SimpleCodeEditor(self)
        self.preview_editor.setFixedWidth(260)
        self.preview_editor.set_language('Python')
        self.preview_editor.set_text(PREVIEW_TEXT)
        self.preview_editor.set_blanks_enabled(False)
        self.preview_editor.set_scrollpastend_enabled(False)

        preview_interface_label = QLabel(_("Interface font"))
        self.preview_interface = QLabel("Sample text")
        self.preview_interface.setFixedWidth(260)
        self.preview_interface.setFixedHeight(45)
        self.preview_interface.setWordWrap(True)
        self.preview_interface.setTextInteractionFlags(
            Qt.TextEditorInteraction
        )
        self.preview_interface.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        preview_interface_label_css = qstylizer.style.StyleSheet()
        preview_interface_label_css.QLabel.setValues(
            border=f"1px solid {SpyderPalette.COLOR_BACKGROUND_4}",
            borderRadius=SpyderPalette.SIZE_BORDER_RADIUS,
            backgroundColor=SpyderPalette.COLOR_BACKGROUND_2,
        )
        self.preview_interface.setStyleSheet(
            preview_interface_label_css.toString()
        )

        # Fonts layout
        fonts_grid_layout = QGridLayout()
        fonts_grid_layout.addWidget(self.plain_text_font.fontlabel, 0, 0)
        fonts_grid_layout.addWidget(self.plain_text_font.fontbox, 0, 1)
        fonts_grid_layout.addWidget(self.plain_text_font.sizebox, 0, 2)
        fonts_grid_layout.addWidget(self.app_font.fontlabel, 2, 0)
        fonts_grid_layout.addWidget(self.app_font.fontbox, 2, 1)
        fonts_grid_layout.addWidget(self.app_font.sizebox, 2, 2)
        fonts_grid_layout.setRowStretch(fonts_grid_layout.rowCount(), 1)

        fonts_layout = QVBoxLayout()
        fonts_layout.addLayout(fonts_grid_layout)
        fonts_layout.addSpacing(5)
        fonts_layout.addWidget(system_font_checkbox)

        fonts_group.setLayout(fonts_layout)

        # Left options layout
        options_layout = QVBoxLayout()
        options_layout.addWidget(ui_group)
        options_layout.addWidget(fonts_group)

        # Right previews layout
        preview_group = QGroupBox(_("Previews"))
        preview_layout = QVBoxLayout()
        preview_layout.addSpacing(AppStyle.MarginSize)
        preview_layout.addWidget(preview_editor_label)
        preview_layout.addWidget(self.preview_editor)
        preview_layout.addSpacing(2 * AppStyle.MarginSize)
        preview_layout.addWidget(preview_interface_label)
        preview_layout.addWidget(self.preview_interface)
        preview_group.setLayout(preview_layout)

        # Combined layout
        combined_layout = QGridLayout()
        combined_layout.setHorizontalSpacing(AppStyle.MarginSize * 5)
        combined_layout.addLayout(options_layout, 0, 0)
        combined_layout.addWidget(preview_group, 0, 1)

        # Final layout
        # Note: This is necessary to prevent the layout from growing downward
        # indefinitely.
        final_layout = QVBoxLayout()
        final_layout.addLayout(combined_layout)
        final_layout.addStretch()
        self.setLayout(final_layout)

        # Signals and slots
        create_button.clicked.connect(self.create_new_scheme)
        edit_button.clicked.connect(self.edit_scheme)
        self.reset_button.clicked.connect(self.reset_to_default)
        self.delete_button.clicked.connect(self.delete_scheme)
        self.schemes_combobox.currentIndexChanged.connect(
            lambda index: self.update_editor_preview()
        )
        self.schemes_combobox.sig_popup_is_hidden.connect(
            self.update_editor_preview
        )
        self.schemes_combobox.sig_item_in_popup_changed.connect(
            lambda scheme_name: self.update_editor_preview(
                scheme_name=scheme_name
            )
        )
        self.schemes_combobox.currentIndexChanged.connect(self.update_buttons)
        self.schemes_combobox.currentIndexChanged.connect(
            self.on_scheme_changed
        )
        self.plain_text_font.fontbox.currentFontChanged.connect(
            lambda font: self.update_editor_preview()
        )
        self.plain_text_font.fontbox.sig_popup_is_hidden.connect(
            self.update_editor_preview
        )
        self.plain_text_font.fontbox.sig_item_in_popup_changed.connect(
            lambda font_family: self.update_editor_preview(
                scheme_name=None, font_family=font_family
            )
        )
        self.plain_text_font.sizebox.valueChanged.connect(
            lambda value: self.update_editor_preview()
        )
        self.app_font.fontbox.currentFontChanged.connect(
            lambda font: self.update_interface_preview()
        )
        self.app_font.fontbox.sig_popup_is_hidden.connect(
            self.update_interface_preview
        )
        self.app_font.fontbox.sig_item_in_popup_changed.connect(
            self.update_interface_preview
        )
        self.app_font.sizebox.valueChanged.connect(
            lambda value: self.update_interface_preview()
        )
        system_font_checkbox.checkbox.stateChanged.connect(
            self.update_app_font_group
        )

        # Now load the schemes into the editor dialog
        for name in names:
            try:
                self.scheme_editor_dialog.add_color_scheme_stack(name)
            except (configparser.NoOptionError, Exception):
                # Skip themes that can't be loaded
                pass

        valid_custom_names = []
        for name in custom_names:
            try:
                self.scheme_editor_dialog.add_color_scheme_stack(
                    name, custom=True
                )
                valid_custom_names.append(name)
            except configparser.NoOptionError:
                # Ignore invalid custom syntax highlighting themes
                # See spyder-ide/spyder#22492
                pass

        self.set_option("custom_names", valid_custom_names)

        if sys.platform == 'darwin':
            system_font_checkbox.checkbox.setEnabled(False)
        self.update_app_font_group(system_font_checkbox.checkbox.isChecked())
        self.update_combobox()
        self.update_editor_preview()

    def get_font(self, option):
        """Return global font used in Spyder."""
        return get_font(option=option)

    def set_font(self, font, option):
        """Set global font used in Spyder."""
        set_font(font, option=option)

        # The app font can't be set in place. Instead, it requires a restart
        if option != 'app_font':
            # Update fonts for all plugins
            plugins = self.main.widgetlist + self.main.thirdparty_plugins
            for plugin in plugins:
                plugin.update_font()

    def apply_settings(self):
        # Only save theme if it actually changed
        try:
            current_scheme = self.current_scheme
            saved_scheme = self.get_option('selected', default='')
            if current_scheme != saved_scheme:
                self.set_option('selected', current_scheme)
        except Exception:
            # Ignore errors if no theme is selected
            pass
        
        CONF.restore_notifications(section='appearance', option='selected')
        self.update_combobox()
        self.update_editor_preview()

        # This applies font changes to all open editors immediately
        # Fixes spyder-ide/spyder#22693
        for plugin_name in PLUGIN_REGISTRY:
            plugin = PLUGIN_REGISTRY.get_plugin(plugin_name)
            plugin.update_font()

        return set(self.changed_options)

    # ---- Helpers
    # -------------------------------------------------------------------------
    @property
    def current_scheme_name(self):
        return self.schemes_combobox.currentText()

    @property
    def current_scheme(self):
        return self.scheme_choices_dict[self.current_scheme_name]

    @property
    def current_scheme_index(self):
        return self.schemes_combobox.currentIndex()

    @property
    def current_ui_theme_index(self):
        # No longer have separate UI theme combobox
        # UI mode is derived from selected theme variant
        return 0  # Placeholder for backward compatibility

    # ---- Qt methods
    # -------------------------------------------------------------------------
    def showEvent(self, event):
        """Adjustments when the page is shown."""
        super().showEvent(event)

        if not self._is_shown:
            # Set the right interface font for Mac in the respective combobox,
            # so that preview_interface shows it appropriately.
            if sys.platform == "darwin":
                index = self.app_font.fontbox.findText("SF Pro")
                if index != -1:
                    self.app_font.fontbox.setCurrentIndex(index)

        self._is_shown = True

    # ---- Update contents
    # -------------------------------------------------------------------------
    def update_combobox(self):
        """Recreates the combobox contents."""
        # Save currently selected theme (not index, since order may change)
        current_scheme = self.get_option('selected', default='spyder_themes.qdarkstyle/dark')
        
        self.schemes_combobox.blockSignals(True)
        
        # Use theme manager to get available themes dynamically
        from spyder.utils.theme_manager import theme_manager
        names = theme_manager.get_available_theme_variants()
        try:
            names.pop(names.index(u'Custom'))
        except ValueError:
            pass
        custom_names = self.get_option("custom_names", [])

        # Clear existing data
        self.scheme_choices_dict.clear()
        combobox = self.schemes_combobox
        combobox.clear()

        # Add separator placeholder for custom names
        if custom_names:
            choices = names + [None] + custom_names
        else:
            choices = names

        # Single pass: build dict and populate combobox at the same time
        for name in choices:
            if name is None:
                # Insert separator
                combobox.insertSeparator(combobox.count())
                continue
            
            # Get display name (from config or generate it)
            try:
                display_name = str(self.get_option('{0}/name'.format(name)))
            except Exception:
                display_name = theme_manager.get_theme_display_name(name)
            
            # Add to dictionary and combobox
            self.scheme_choices_dict[display_name] = name
            combobox.addItem(display_name, name)

        # Find and select the current theme (by value, not index)
        index = combobox.findData(current_scheme)
        if index == -1:
            # Theme not found, default to qdarkstyle/dark
            index = combobox.findData('spyder_themes.qdarkstyle/dark')
        if index == -1:
            # Still not found, just use first item
            index = 0
        
        self.schemes_combobox.blockSignals(False)
        self.schemes_combobox.setCurrentIndex(index)

    def update_buttons(self):
        """Updates the enable status of delete and reset buttons."""
        current_scheme = self.current_scheme
        names = self.get_option("names")
        try:
            names.pop(names.index(u'Custom'))
        except ValueError:
            pass
        delete_enabled = current_scheme not in names
        self.delete_button.setEnabled(delete_enabled)
        self.reset_button.setEnabled(not delete_enabled)

    def update_editor_preview(self, scheme_name=None, font_family=None):
        """Update the color scheme of the preview editor and adds text."""
        if scheme_name is None:
            scheme_name = self.current_scheme
        else:
            scheme_name = self.scheme_choices_dict[scheme_name]

        if font_family is None:
            plain_text_font = self.plain_text_font.fontbox.currentFont()
        else:
            plain_text_font = QFont(font_family)

        plain_text_font.setPointSize(self.plain_text_font.sizebox.value())
        self.preview_editor.setup_editor(
            font=plain_text_font,
            color_scheme=scheme_name
        )

    def update_interface_preview(self, font_family=None):
        """Update the interface preview label."""
        if font_family is None:
            app_font = self.app_font.fontbox.currentFont()
        else:
            app_font = QFont(font_family)

        app_font.setPointSize(self.app_font.sizebox.value())
        self.preview_interface.setFont(app_font)

    def update_app_font_group(self, state):
        """Update app font group enabled state."""
        subwidgets = ['fontlabel', 'fontbox', 'sizebox']

        if state:
            for widget in subwidgets:
                getattr(self.app_font, widget).setEnabled(False)
        else:
            for widget in subwidgets:
                getattr(self.app_font, widget).setEnabled(True)

    # ---- Actions
    # -------------------------------------------------------------------------
    def on_scheme_changed(self):
        """Handle scheme selection change - update preview only."""
        try:
            # Only update the preview, don't save to config yet
            # The theme will be saved when user clicks Apply/OK
            self.update_editor_preview()
        except Exception:
            # Ignore errors during initialization
            pass
    
    def create_new_scheme(self):
        """Creates a new color scheme with a custom name."""
        names = self.get_option('names')
        custom_names = self.get_option('custom_names', [])

        # Get the available number this new color scheme
        counter = len(custom_names) - 1
        custom_index = [int(n.split('-')[-1]) for n in custom_names]
        for i in range(len(custom_names)):
            if custom_index[i] != i:
                counter = i - 1
                break
        custom_name = "custom-{0}".format(counter+1)

        # Add the config settings, based on the current one.
        custom_names.append(custom_name)
        self.set_option('custom_names', custom_names)
        for key in syntaxhighlighters.COLOR_SCHEME_KEYS:
            name = "{0}/{1}".format(custom_name, key)
            default_name = "{0}/{1}".format(self.current_scheme, key)
            option = self.get_option(default_name)
            self.set_option(name, option)
        self.set_option('{0}/name'.format(custom_name), custom_name)

        # Now they need to be loaded! how to make a partial load_from_conf?
        dlg = self.scheme_editor_dialog
        dlg.add_color_scheme_stack(custom_name, custom=True)
        dlg.set_scheme(custom_name)
        self.load_from_conf()

        if dlg.exec_():
            # This is needed to have the custom name updated on the combobox
            name = dlg.get_scheme_name()
            self.set_option('{0}/name'.format(custom_name), name)

            # The +1 is needed because of the separator in the combobox
            index = (names + custom_names).index(custom_name) + 1
            self.update_combobox()
            self.schemes_combobox.setCurrentIndex(index)
        else:
            # Delete the config ....
            custom_names.remove(custom_name)
            self.set_option('custom_names', custom_names)
            dlg.delete_color_scheme_stack(custom_name)

    def edit_scheme(self):
        """Edit current scheme."""
        dlg = self.scheme_editor_dialog
        dlg.set_scheme(self.current_scheme)
        dlg.rejected.connect(lambda: self.apply_button_enabled.emit(False))

        if dlg.exec_():
            # Update temp scheme to reflect instant edits on the preview
            temporal_color_scheme = dlg.get_edited_color_scheme()
            for key in temporal_color_scheme:
                option = "temp/{0}".format(key)
                value = temporal_color_scheme[key]
                self.set_option(option, value)

            if not self.scheme_choices_dict.get("temp"):
                self.scheme_choices_dict["temp"] = "temp"

            self.update_editor_preview(scheme_name='temp')

    def delete_scheme(self):
        """Deletes the currently selected custom color scheme."""
        scheme_name = self.current_scheme

        answer = QMessageBox.warning(
            self,
            _("Warning"),
            _("Are you sure you want to delete this theme?"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            # Delete from custom_names
            custom_names = self.get_option('custom_names', [])
            if scheme_name in custom_names:
                custom_names.remove(scheme_name)
            self.set_option('custom_names', custom_names)

            # Delete config options
            for key in syntaxhighlighters.COLOR_SCHEME_KEYS:
                option = "{0}/{1}".format(scheme_name, key)
                CONF.remove_option(self.CONF_SECTION, option)
            CONF.remove_option(self.CONF_SECTION,
                               "{0}/name".format(scheme_name))

            self.update_combobox()
            self.update_editor_preview()

    def set_scheme(self, scheme_name):
        """
        Set the current stack in the dialog to the scheme with 'scheme_name'.
        """
        dlg = self.scheme_editor_dialog
        dlg.set_scheme(scheme_name)

    @Slot()
    def reset_to_default(self):
        """Restore initial values for default color schemes."""
        # Checks that this is indeed a default scheme
        scheme = self.current_scheme
        names = self.get_option('names')
        
        if scheme in names:
            # Check if this is a new theme variant (contains '/')
            if '/' in scheme:
                # New theme system: extract theme from ThemeManager and export
                from spyder.utils.theme_manager import theme_manager
                try:
                    theme_name, ui_mode = scheme.rsplit('/', 1)
                    # Export with replace=True to overwrite user customizations
                    theme_manager.export_theme_to_config(
                        theme_name, ui_mode, replace=True
                    )
                except Exception:
                    # Fallback to old method if extraction fails
                    for key in syntaxhighlighters.COLOR_SCHEME_KEYS:
                        option = "{0}/{1}".format(scheme, key)
                        value = CONF.get_default(self.CONF_SECTION, option)
                        self.set_option(option, value)
            else:
                # Old theme system
                for key in syntaxhighlighters.COLOR_SCHEME_KEYS:
                    option = "{0}/{1}".format(scheme, key)
                    value = CONF.get_default(self.CONF_SECTION, option)
                    self.set_option(option, value)

            self.load_from_conf()

    def is_dark_interface(self):
        """
        Check if our interface is dark independently from our config
        system.

        We need to do this because when applying settings we can't
        detect correctly the current theme.
        """
        return dark_color(SpyderPalette.COLOR_BACKGROUND_1)

