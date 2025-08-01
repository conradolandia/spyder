# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Main plugin widget.

SpyderDockablePlugin plugins must provide a WIDGET_CLASS attribute that is a
subclass of PluginMainWidget.
"""

# Standard library imports
from collections import OrderedDict
import logging
from typing import Optional

# Third party imports
from qtpy import PYSIDE2
from qtpy.QtCore import QByteArray, QSize, Qt, Signal, Slot
from qtpy.QtGui import QFocusEvent, QIcon
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Local imports
from spyder.api.exceptions import SpyderAPIError
from spyder.api.translations import _
from spyder.api.widgets import PluginMainWidgetActions, PluginMainWidgetWidgets
from spyder.api.widgets.auxiliary_widgets import (MainCornerWidget,
                                                  SpyderWindowWidget)
from spyder.api.widgets.menus import (
    PluginMainWidgetOptionsMenu,
    OptionsMenuSections,
    PluginMainWidgetMenus
)
from spyder.api.widgets.mixins import SpyderWidgetMixin
from spyder.api.widgets.toolbars import MainWidgetToolbar
from spyder.py3compat import qbytearray_to_str
from spyder.utils.qthelpers import create_waitspinner
from spyder.utils.registries import ACTION_REGISTRY, TOOLBAR_REGISTRY
from spyder.utils.stylesheet import (
    AppStyle, APP_STYLESHEET, PANES_TABBAR_STYLESHEET,
    PANES_TOOLBAR_STYLESHEET)
from spyder.widgets.dock import DockTitleBar, SpyderDockWidget
from spyder.widgets.emptymessage import EmptyMessageWidget
from spyder.widgets.tabs import Tabs


# Logging
logger = logging.getLogger(__name__)


class PluginMainWidget(QWidget, SpyderWidgetMixin):
    """
    Spyder plugin main widget class.

    This class handles both a dockwidget pane and a floating window widget
    (undocked pane).

    Notes
    -----
    All Spyder dockable plugins define a main widget that must subclass this.

    This widget is a subclass of QMainWindow that consists of a single,
    central widget and a set of toolbars that are stacked above or below
    that widget.

    The toolbars are not moveable nor floatable and must occupy the entire
    horizontal space available for the plugin. This mean that toolbars must be
    stacked vertically and cannot be placed horizontally next to each other.
    """

    # ---- Attributes
    # -------------------------------------------------------------------------
    ENABLE_SPINNER = False
    """
    This attribute enables/disables showing a spinner on the top right to the
    left of the corner menu widget (Hamburguer menu).

    Plugins that provide actions that take time should make this `True` and
    use accordingly with the `start_spinner`/`stop_spinner` methods.

    The Find in files plugin is an example of a core plugin that uses it.

    Parameters
    ----------
    ENABLE_SPINNER: bool
        If `True` an extra space will be added to the toolbar (even if the
        spinner is not moving) to avoid items jumping to the left/right when
        the spinner appears. If `False` no extra space will be added. Default
        is False.
    """

    CONTEXT_NAME = None
    """
    This optional attribute defines the context name under which actions,
    toolbars, toolbuttons and menus should be registered on the
    Spyder global registry.

    If actions, toolbars, toolbuttons or menus belong to the global scope of
    the plugin, then this attribute should have a `None` value.
    """

    MARGIN_TOP = 0
    """
    Use this attribute to adjust the widget's top margin in pixels.
    """

    SHOW_MESSAGE_WHEN_EMPTY = False
    """
    This attribute enables/disables showing a message when the widget is empty.

    Notes
    -----
    - If True, at least you need to set the MESSAGE_WHEN_EMPTY attribute as
      well.
    - The Find in files plugin is an example of a core plugin that uses it.
    """

    MESSAGE_WHEN_EMPTY = None
    """
    This is the main message that will be shown when the widget is empty.

    Notes
    -----
    - This must be a string
    - The Find in files plugin is an example of a core plugin that uses it.
    """

    IMAGE_WHEN_EMPTY = None
    """
    Name of or path to the svg image to show when the widget is empty
    (optional).

    Notes
    -----
    - This needs to be an svg file so that it can be rendered correctly in high
      resolution screens.
    - The Find in files plugin is an example of a core plugin that uses it.
    """

    DESCRIPTION_WHEN_EMPTY = None
    """
    This is the description (i.e. additional text) that will be shown when the
    widget is empty (optional).

    Notes
    -----
    - This must be a string.
    - The Find in files plugin is an example of a core plugin that uses this.
    """

    SET_LAYOUT_WHEN_EMPTY = True
    """
    Whether to automatically set a vertical layout for the stacked widget that
    holds the empty message widget and the content one.

    Notes
    -----
    - You need to set this to False if you need to set a more complex layout in
      your widget.
    - The Debugger plugin is an example of a core plugin that uses this.
    """

    # ---- Signals
    # -------------------------------------------------------------------------
    sig_free_memory_requested = Signal()
    """
    This signal can be emitted to request the main application to garbage
    collect deleted objects.
    """

    sig_quit_requested = Signal()
    """
    This signal can be emitted to request the main application to quit.
    """

    sig_restart_requested = Signal()
    """
    This signal can be emitted to request the main application to restart.
    """

    sig_redirect_stdio_requested = Signal(bool)
    """
    This signal can be emitted to request the main application to redirect
    standard output/error when using Open/Save/Browse dialogs within widgets.

    Parameters
    ----------
    enable: bool
        Enable/Disable standard input/output redirection.
    """

    sig_exception_occurred = Signal(dict)
    """
    This signal can be emitted to report an exception handled by this widget.

    Parameters
    ----------
    # --- Optional overridable methods
    error_data: dict
        The dictionary containing error data. The expected keys are:
        >>> error_data= {
            "text": str,
            "is_traceback": bool,
            "repo": str,
            "title": str,
            "label": str,
            "steps": str,
        }

    Notes
    -----
    The `is_traceback` key indicates if `text` contains plain text or a
    Python error traceback.

    The `title` and `repo` keys indicate how the error data should
    customize the report dialog and Github error submission.

    The `label` and `steps` keys allow customizing the content of the
    error dialog.
    """

    sig_toggle_view_changed = Signal(bool)
    """
    This signal is emitted to inform the visibility of a dockable plugin
    has changed.

    This is triggered by checking/unchecking the entry for a pane in the
    `Window > Panes` menu.

    Parameters
    ----------
    visible: bool
        New visibility of the dockwidget.
    """

    sig_update_ancestor_requested = Signal()
    """
    This signal is emitted to inform the main window that a child widget
    needs its ancestor to be updated.
    """

    sig_unmaximize_plugin_requested = Signal((), (object,))
    """
    This signal is emitted to inform the main window that it needs to
    unmaximize the currently maximized plugin, if any.

    Parameters
    ----------
    plugin_instance: SpyderDockablePlugin
        Unmaximize plugin only if it is not `plugin_instance`.
    """

    sig_focus_status_changed = Signal(bool)
    """
    This signal is emitted to inform the focus status of the widget.

    Parameters
    ----------
    status: bool
        True if the widget is focused. False otherwise.
    """

    def __init__(self, name, plugin, parent=None):
        if not PYSIDE2:
            super().__init__(parent=parent, class_parent=plugin)
        else:
            QWidget.__init__(self, parent)
            SpyderWidgetMixin.__init__(self, class_parent=plugin)

        # Attributes
        # --------------------------------------------------------------------
        self._is_tab = False
        self._name = name
        self._plugin = plugin
        self._parent = parent
        self._default_margins = None
        self.is_visible = None
        self.dock_action = None
        self.undock_action = None
        self.close_action = None
        self._toolbars_already_rendered = False
        self._is_maximized = False

        # Attribute used to access the action, toolbar, toolbutton and menu
        # registries
        self.PLUGIN_NAME = name

        # We create our toggle action instead of using the one that comes with
        # dockwidget because it was not possible to raise and focus the plugin
        self.toggle_view_action = None
        self._toolbars = OrderedDict()
        self._auxiliary_toolbars = OrderedDict()

        # Widgets
        # --------------------------------------------------------------------
        self.windowwidget = None
        self.dockwidget = None
        self._icon = QIcon()
        self._spinner = None
        self._stack = None
        self._content_widget = None
        self._pane_empty = None

        if self.ENABLE_SPINNER:
            self._spinner = create_waitspinner(
                size=16, parent=self, name=PluginMainWidgetWidgets.Spinner
            )

        self._corner_widget = MainCornerWidget(
            parent=self,
            name=PluginMainWidgetWidgets.CornerWidget,
        )
        self._corner_widget.ID = 'main_corner'

        self._main_toolbar = MainWidgetToolbar(
            parent=self,
            title=_("Main widget toolbar"),
        )
        self._main_toolbar.ID = 'main_toolbar'

        TOOLBAR_REGISTRY.register_reference(
            self._main_toolbar, self._main_toolbar.ID,
            self.PLUGIN_NAME, self.CONTEXT_NAME)

        self._corner_toolbar = MainWidgetToolbar(
            parent=self,
            title=_("Main widget corner toolbar"),
        )
        self._corner_toolbar.ID = 'corner_toolbar'

        TOOLBAR_REGISTRY.register_reference(
            self._corner_toolbar, self._corner_toolbar.ID,
            self.PLUGIN_NAME, self.CONTEXT_NAME)

        self._corner_toolbar.setSizePolicy(QSizePolicy.Minimum,
                                           QSizePolicy.Expanding)

        self._options_menu = self._create_menu(
            PluginMainWidgetMenus.Options,
            title=_('Options menu'),
            MenuClass=PluginMainWidgetOptionsMenu
        )

        # Margins
        # --------------------------------------------------------------------
        # These margins are necessary to give some space between the widgets
        # inside this one and the window separator and borders.
        self._margin_right = AppStyle.MarginSize
        self._margin_bottom = AppStyle.MarginSize
        if not self.get_conf('vertical_tabs', section='main'):
            self._margin_left = AppStyle.MarginSize
        else:
            self._margin_left = 0

        # Layout
        # --------------------------------------------------------------------
        self._main_layout = QVBoxLayout()
        self._toolbars_layout = QVBoxLayout()
        self._main_toolbar_layout = QHBoxLayout()

        self._toolbars_layout.setContentsMargins(
            self._margin_left, 0, self._margin_right, 0)
        self._toolbars_layout.setSpacing(0)
        self._main_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self._main_toolbar_layout.setSpacing(0)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Add inititals layouts
        self._main_toolbar_layout.addWidget(self._main_toolbar, stretch=10000)
        self._main_toolbar_layout.addWidget(self._corner_toolbar, stretch=1)
        self._toolbars_layout.addLayout(self._main_toolbar_layout)
        self._main_layout.addLayout(self._toolbars_layout, stretch=1)

        # Create a stacked layout when the widget displays an empty message
        if self.SHOW_MESSAGE_WHEN_EMPTY and self.get_conf(
            "show_message_when_panes_are_empty", section="main"
        ):
            if not self.MESSAGE_WHEN_EMPTY:
                raise SpyderAPIError(
                    "You need to provide a message to show when the widget is "
                    "empty"
                )

            self._pane_empty = EmptyMessageWidget(
                self,
                self.IMAGE_WHEN_EMPTY,
                self.MESSAGE_WHEN_EMPTY,
                self.DESCRIPTION_WHEN_EMPTY,
                adjust_on_resize=True,
            )

            self._stack = QStackedWidget(self)
            self._stack.addWidget(self._pane_empty)

            if self.SET_LAYOUT_WHEN_EMPTY:
                layout = QVBoxLayout()
                layout.addWidget(self._stack)
                self.setLayout(layout)

    # ---- Private Methods
    # -------------------------------------------------------------------------
    def _setup(self):
        """
        Setup default actions, create options menu, and connect signals.
        """
        # Tabs
        children = self.findChildren(Tabs)
        if children:
            for child in children:
                self._is_tab = True
                # For widgets that use tabs, we add the corner widget using
                # the setCornerWidget method.
                child.setCornerWidget(self._corner_widget)
                self._corner_widget.setStyleSheet(str(PANES_TABBAR_STYLESHEET))
                break

        self._options_button = self.create_toolbutton(
            PluginMainWidgetWidgets.OptionsToolButton,
            text=_('Options'),
            icon=self.create_icon('tooloptions'),
        )

        self.add_corner_widget(self._options_button)

        if self.ENABLE_SPINNER:
            self.add_corner_widget(self._spinner)

        # Widget setup
        # --------------------------------------------------------------------
        self._main_toolbar.setVisible(not self._is_tab)
        self._corner_toolbar.setVisible(not self._is_tab)
        self._options_button.setPopupMode(QToolButton.InstantPopup)

        # Create default widget actions
        self.dock_action = self.create_action(
            name=PluginMainWidgetActions.DockPane,
            text=_("Dock"),
            tip=_("Dock the pane"),
            icon=self.create_icon('dock'),
            triggered=self.dock_window,
        )
        self.lock_unlock_action = self.create_action(
            name=PluginMainWidgetActions.LockUnlockPosition,
            text=_("Move"),
            tip=_("Unlock to move pane to another position"),
            icon=self.create_icon('drag_dock_widget'),
            triggered=self.lock_unlock_position,
        )
        self.undock_action = self.create_action(
            name=PluginMainWidgetActions.UndockPane,
            text=_("Undock"),
            tip=_("Undock the pane"),
            icon=self.create_icon('undock'),
            triggered=self.create_window,
        )
        self.close_action = self.create_action(
            name=PluginMainWidgetActions.ClosePane,
            text=_("Close"),
            tip=_("Close the pane"),
            icon=self.create_icon('close_pane'),
            triggered=self.close_dock,
        )
        # We use this instead of the QDockWidget.toggleViewAction
        self.toggle_view_action = self.create_action(
            name='switch to ' + self._name,
            text=self.get_title(),
            toggled=lambda checked: self.toggle_view(checked),
            context=Qt.WidgetWithChildrenShortcut,
            shortcut_context='_',
        )

        for item in [self.lock_unlock_action, self.undock_action,
                     self.dock_action, self.close_action]:
            self.add_item_to_menu(
                item,
                self._options_menu,
                section=OptionsMenuSections.Bottom,
            )

        self._options_button.setMenu(self._options_menu)
        self._options_menu.aboutToShow.connect(self._update_actions)

        # For widgets that do not use tabs, we add the corner widget to the
        # corner toolbar
        if not self._is_tab:
            self.add_item_to_toolbar(
                self._corner_widget,
                toolbar=self._corner_toolbar,
                section="corner",
            )
            self._corner_widget.setStyleSheet(str(PANES_TOOLBAR_STYLESHEET))

        # Update title
        self.setWindowTitle(self.get_title())

    def _update_actions(self):
        """
        Refresh Options menu.
        """
        show_dock_actions = self.windowwidget is None
        self.undock_action.setVisible(show_dock_actions)
        self.lock_unlock_action.setVisible(show_dock_actions)
        self.dock_action.setVisible(not show_dock_actions)

        # Widget setup
        self.update_actions()

    @Slot(bool)
    def _on_top_level_change(self, top_level):
        """
        Actions to perform when a plugin is undocked to be moved.
        """
        self.undock_action.setDisabled(top_level)

        # Change the cursor shape when dragging
        if top_level:
            QApplication.setOverrideCursor(Qt.ClosedHandCursor)
        else:
            QApplication.restoreOverrideCursor()

    @Slot(bool)
    def _on_title_bar_shown(self, visible):
        """
        Actions to perform when the title bar is shown/hidden.
        """
        if visible:
            self.lock_unlock_action.setText(_('Lock'))
            self.lock_unlock_action.setIcon(self.create_icon('lock_open'))
            for method_name in ['setToolTip', 'setStatusTip']:
                method = getattr(self.lock_unlock_action, method_name)
                method(_("Lock pane to the current position"))
        else:
            self.lock_unlock_action.setText(_('Move'))
            self.lock_unlock_action.setIcon(
                self.create_icon('drag_dock_widget'))
            for method_name in ['setToolTip', 'setStatusTip']:
                method = getattr(self.lock_unlock_action, method_name)
                method(_("Unlock to move pane to another position"))

    # ---- Public Qt overriden methods
    # -------------------------------------------------------------------------
    def setLayout(self, layout):
        """
        Set layout of the main widget of this plugin.
        """
        self._main_layout.addLayout(layout, stretch=1000000)
        super().setLayout(self._main_layout)
        layout.setContentsMargins(
            self._margin_left, self.MARGIN_TOP, self._margin_right,
            self._margin_bottom
        )
        layout.setSpacing(0)

    def closeEvent(self, event):
        self.on_close()
        super().closeEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.sig_focus_status_changed.emit(True)
        self.on_focus_in()
        return super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.sig_focus_status_changed.emit(False)
        self.on_focus_out()
        return super().focusOutEvent(event)

    # ---- Public methods to use
    # -------------------------------------------------------------------------
    def get_plugin(self):
        """
        Return the parent plugin.
        """
        return self._plugin

    def get_action(self, name, context: Optional[str] = None,
                   plugin: Optional[str] = None):
        """
        Return action by name.
        """
        plugin = self.PLUGIN_NAME if plugin is None else plugin
        context = self.CONTEXT_NAME if context is None else context

        return ACTION_REGISTRY.get_reference(name, plugin, context)

    def add_corner_widget(self, action_or_widget, before=None):
        """
        Add widget to corner, that is to the left of the last added widget.

        Parameters
        ----------
        action_or_widget: QAction or QWidget
            Any action or widget to add to the corner widget.
        before: QAction or QWidget
            Insert action_or_widget before this one.

        Notes
        -----
        By default widgets are added to the left of the last corner widget.

        The central widget provides an options menu button and a spinner so any
        additional widgets will be placed by default to the left of the
        spinner, if visible.
        """
        self._corner_widget.add_widget(action_or_widget, before=before)

    def get_corner_widget(self, name):
        """
        Return the a widget inside the corner widget by name.

        Parameters
        ----------
        name: str
            Unique name of the widget.
        """
        return self._corner_widget.get_widget(name)

    def start_spinner(self):
        """
        Start default status spinner.
        """
        if self.ENABLE_SPINNER:
            self._spinner.start()

    def stop_spinner(self):
        """
        Stop default status spinner.
        """
        if self.ENABLE_SPINNER:
            self._spinner.stop()

    def create_toolbar(self, toolbar_id):
        """
        Create and add an auxiliary toolbar to the top of the plugin.

        Parameters
        ----------
        toolbar_id: str
            Unique toolbar string identifier.

        Returns
        -------
        SpyderPluginToolbar
            The auxiliary toolbar that was created and added to the plugin
            interface.
        """
        toolbar = MainWidgetToolbar(parent=self)
        toolbar.ID = toolbar_id

        TOOLBAR_REGISTRY.register_reference(
            toolbar, toolbar_id, self.PLUGIN_NAME, self.CONTEXT_NAME)

        self._auxiliary_toolbars[toolbar_id] = toolbar
        self._toolbars_layout.addWidget(toolbar)

        return toolbar

    def get_options_menu(self):
        """
        Return the main options menu of the widget.
        """
        return self._options_menu

    def get_options_menu_button(self):
        """
        Return the main options menu button of the widget.
        """
        return self._options_button

    def get_main_toolbar(self):
        """
        Return the main toolbar of the plugin.

        Returns
        -------
        QToolBar
            The main toolbar of the widget that contains the options button.
        """
        return self._main_toolbar

    def get_auxiliary_toolbars(self):
        """
        Return the auxiliary toolbars of the plugin.

        Returns
        -------
        OrderedDict
            A dictionary of wirh toolbar IDs as keys and auxiliary toolbars as
            values.
        """
        return self._auxiliary_toolbars

    def set_icon_size(self, icon_size):
        """
        Set the icon size of the plugin's toolbars.

        Parameters
        ----------
        iconsize: int
            An integer corresponding to the size in pixels to which the icons
            of the plugin's toolbars need to be set.
        """
        self._icon_size = icon_size
        self._main_toolbar.set_icon_size(QSize(icon_size, icon_size))

    def show_status_message(self, message, timeout):
        """
        Show a status message in the Spyder widget.
        """
        status_bar = self.statusBar()
        if status_bar.isVisible():
            status_bar.showMessage(message, timeout)

    def get_focus_widget(self):
        """
        Get the widget to give focus to.

        Returns
        -------
        QWidget
            QWidget to give focus to.

        Notes
        -----
        This is applied when the plugin's dockwidget is raised to the top.
        """
        return self

    def update_margins(self, margin=None):
        """
        Update central widget margins.
        """
        layout = self.layout()
        if self._default_margins is None:
            self._default_margins = layout.getContentsMargins()

        if margin is not None:
            layout.setContentsMargins(margin, margin, margin, margin)
        else:
            layout.setContentsMargins(*self._default_margins)

    def update_title(self):
        """
        Update title of dockwidget or plugin window.
        """
        if self.dockwidget is not None:
            widget = self.dockwidget
        elif self.windowwidget is not None:
            widget = self.undocked_window
        else:
            return

        widget.setWindowTitle(self.get_title())

    def set_name(self, name):
        """
        Set widget name (plugin.NAME).
        """
        self._name = name

    def get_name(self):
        """
        Return widget name (plugin.NAME).
        """
        return self._name

    def set_icon(self, icon):
        """
        Set widget icon.
        """
        self._icon = icon

    def get_icon(self):
        """
        Return widget icon.
        """
        return self._icon

    def render_toolbars(self):
        """
        Render all the toolbars of the widget.

        Notes
        -----
        This action can only be performed once.
        """
        # if not self._toolbars_already_rendered:
        self._main_toolbar.render()
        self._corner_toolbar.render()
        for __, toolbar in self._auxiliary_toolbars.items():
            toolbar.render()

            # self._toolbars_already_rendered = True

    # ---- For widgets with an empty message
    # -------------------------------------------------------------------------
    def set_content_widget(self, widget, add_to_stack=True):
        """
        Set the widget that actually displays content when there is an empty
        message.

        Parameters
        ----------
        widget: QWidget
            Widget to set as the widget with content.
        add_to_stack: bool
            Whether to add this widget to stacked widget that holds the empty
            message.
        """
        self._content_widget = widget

        if self._stack is not None:
            if add_to_stack:
                self._stack.addWidget(self._content_widget)
        else:
            # This is necessary to automatically set a layout for Find or the
            # Profiler when the user disables empty messages in Preferences.
            if self.SET_LAYOUT_WHEN_EMPTY:
                layout = QVBoxLayout()
                layout.addWidget(self._content_widget)
                self.setLayout(layout)

    def show_content_widget(self):
        """
        Show the widget that actually displays content when there is an empty
        message.
        """
        if (
            self._stack is not None
            and self._content_widget is not None
            and self._stack.indexOf(self._content_widget) != -1
        ):
            self._stack.setCurrentWidget(self._content_widget)

    def show_empty_message(self):
        """Show the empty message widget."""
        if self.SHOW_MESSAGE_WHEN_EMPTY and self.get_conf(
            "show_message_when_panes_are_empty", section="main"
        ):
            self._stack.setCurrentWidget(self._pane_empty)

    # ---- SpyderWindowWidget handling
    # -------------------------------------------------------------------------
    @Slot()
    def create_window(self):
        """
        Create an undocked window containing this widget.
        """
        logger.debug(f"Undocking plugin {self._name}")

        # Widgets
        self.windowwidget = window = SpyderWindowWidget(self)

        # If the close corner button is used
        self.windowwidget.sig_closed.connect(self.close_window)

        # Wigdet setup
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.setCentralWidget(self)
        window.setWindowIcon(self.get_icon())
        window.setWindowTitle(self.get_title())
        window.resize(self.size())

        # Restore window geometry
        geometry = self.get_conf('window_geometry', default='')
        if geometry:
            try:
                window.restoreGeometry(
                    QByteArray().fromHex(str(geometry).encode('utf-8'))
                )

                # Move to the primary screen if the window is not placed in a
                # visible location.
                window.move_to_primary_screen()
            except Exception:
                pass

        # Dock widget setup
        if self.dockwidget:
            self.dockwidget.setFloating(False)
            self.dockwidget.setVisible(False)

        self.set_ancestor(window)
        self._update_actions()
        window.show()

    @Slot()
    def dock_window(self):
        """Dock undocked window back to the main window."""
        logger.debug(f"Docking window of plugin {self._name}")

        # Reset undocked state
        self.set_conf('window_was_undocked_before_hiding', False)

        # This avoids trying to close the window twice: once when calling
        # _close_window below and the other when Qt calls the closeEvent of
        # windowwidget
        self.windowwidget.blockSignals(True)

        # Close window
        self._close_window(switch_to_plugin=True)

        # Make plugin visible on main window
        self.dockwidget.setVisible(True)
        self.dockwidget.raise_()

    @Slot()
    def close_window(self):
        """
        Close undocked window when clicking on the close window button.

        Notes
        -----
        * This can either dock or hide the window, depending on whether the
          user hid the window before.
        * The default behavior is to dock the window, so that new users can
          experiment with the dock/undock functionality without surprises.
        * If the user closes the window by clicking on the `Close` action in
          the plugin's Options menu or by going to the `Window > Panes` menu,
          then we will hide it when they click on the close button again.
          That gives users the ability to show/hide plugins without
          docking/undocking them first.
        """
        if self.get_conf('window_was_undocked_before_hiding', default=False):
            self.close_dock()
        else:
            self.dock_window()

    def _close_window(self, save_undocked=False, switch_to_plugin=True):
        """
        Helper function to close the undocked window with different parameters.

        Parameters
        ----------
        save_undocked : bool, optional
            True if the undocked state needs to be saved. The default is False.
        switch_to_plugin : bool, optional
            Whether to switch to the plugin after closing the window. The
            default is True.

        Returns
        -------
        None.
        """
        if self.windowwidget is not None:
            # Save window geometry to restore it when undocking the plugin
            # again.
            geometry = self.windowwidget.saveGeometry()
            self.set_conf('window_geometry', qbytearray_to_str(geometry))

            # Save undocking state if requested
            if save_undocked:
                self.set_conf('undocked_on_window_close', True)

            # Fixes spyder-ide/spyder#10704
            self.__unsafe_window = self.windowwidget
            self.__unsafe_window.deleteLater()
            self.windowwidget.close()
            self.windowwidget = None

            # These actions can appear disabled when 'Dock' action is pressed
            self.undock_action.setDisabled(False)
            self.close_action.setDisabled(False)

            if self.dockwidget is not None:
                self.sig_update_ancestor_requested.emit()
                if switch_to_plugin:
                    # This is necessary to restore the main window layout when
                    # there's a maximized plugin on it when the user requests
                    # to dock back this plugin.
                    self.get_plugin().switch_to_plugin()

                self.dockwidget.setWidget(self)
                self._update_actions()
        else:
            # Reset undocked state
            self.set_conf('undocked_on_window_close', False)

    # ---- SpyderDockwidget handling
    # -------------------------------------------------------------------------
    def change_visibility(self, enable, force_focus=None):
        """Dock widget visibility has changed."""
        if self.dockwidget is None:
            return

        if enable:
            # Avoid double trigger of visibility change
            self.dockwidget.blockSignals(True)
            self.dockwidget.raise_()
            self.dockwidget.blockSignals(False)

        raise_and_focus = getattr(self, 'RAISE_AND_FOCUS', None)

        if force_focus is None:
            if raise_and_focus and enable:
                focus_widget = self.get_focus_widget()
                if focus_widget:
                    focus_widget.setFocus()
        elif force_focus is True:
            focus_widget = self.get_focus_widget()
            if focus_widget:
                focus_widget.setFocus()
        elif force_focus is False:
            pass

        # If the widget is undocked, it's always visible
        self.is_visible = enable or (self.windowwidget is not None)

        if (
            self.SHOW_MESSAGE_WHEN_EMPTY
            and self.get_conf(
                "show_message_when_panes_are_empty", section="main"
            )
            # We need to do this validation to prevent errors after changing
            # the option above in Preferences and restarting Spyder.
            and self._pane_empty is not None
        ):
            self._pane_empty.set_visibility(self.is_visible)

        # TODO: Pending on plugin migration that uses this
        # if getattr(self, 'DISABLE_ACTIONS_WHEN_HIDDEN', None):
        #     for __, action in self.get_actions().items():
        #         action.setEnabled(is_visible)

    def toggle_view(self, checked):
        """
        Toggle dockwidget's visibility when its entry is selected in
        the menu `Window > Panes`.

        Parameters
        ----------
        checked: bool
            Is the entry in `Window > Panes` checked or not?

        Notes
        -----
        If you need to attach some functionality when this changes, use
        sig_toggle_view_changed. For an example, please see
        `spyder/plugins/ipythonconsole/plugin.py`
        """
        if not self.dockwidget:
            return

        # To check if the plugin needs to be undocked at the end
        undock = False

        if checked:
            self.dockwidget.show()
            self.dockwidget.raise_()
            self.is_visible = True

            # We need to undock the plugin if that was its state before
            # toggling its visibility.
            if (
                # Don't run this while the window is being created to not
                # affect setting up the layout at startup.
                not self._plugin.main.is_setting_up
                and self.get_conf(
                    'window_was_undocked_before_hiding', default=False
                )
            ):
                undock = True
        else:
            if self.windowwidget is not None:
                logger.debug(f"Closing window of plugin {self._name}")

                # This avoids trying to close the window twice: once when
                # calling _close_window below and the other when Qt calls the
                # closeEvent of windowwidget
                self.windowwidget.blockSignals(True)

                # Dock plugin if it's undocked before hiding it.
                self._close_window(switch_to_plugin=False)

                # Save undocked state to restore it afterwards.
                self.set_conf('window_was_undocked_before_hiding', True)

            self.dockwidget.hide()
            self.is_visible = False

        # Update toggle view status, if needed, without emitting signals.
        if self.toggle_view_action.isChecked() != checked:
            self.blockSignals(True)
            self.toggle_view_action.setChecked(checked)
            self.blockSignals(False)

        self.sig_toggle_view_changed.emit(checked)

        logger.debug(
            f"Plugin {self._name} is now {'visible' if checked else 'hidden'}"
        )

        if undock:
            # We undock the plugin at this point so that the Window menu is
            # updated correctly.
            self.create_window()

    def create_dockwidget(self, mainwindow):
        """
        Add to parent QMainWindow as a dock widget.
        """
        # Creating dock widget
        title = self.get_title()
        self.dockwidget = dock = SpyderDockWidget(title, mainwindow)

        # Setup
        dock.setObjectName(self.__class__.__name__ + '_dw')
        dock.setWidget(self)

        # Signals
        dock.visibilityChanged.connect(self.change_visibility)
        dock.topLevelChanged.connect(self._on_top_level_change)
        dock.sig_title_bar_shown.connect(self._on_title_bar_shown)

        return (dock, dock.LOCATION)

    @Slot()
    def close_dock(self):
        """
        Close the dockwidget.
        """
        logger.debug(f"Hiding plugin {self._name}")
        self.toggle_view_action.setChecked(False)

    def lock_unlock_position(self):
        """
        Show/hide title bar to move/lock position.
        """
        if isinstance(self.dockwidget.titleBarWidget(), DockTitleBar):
            self.dockwidget.remove_title_bar()
        else:
            self.dockwidget.set_title_bar()

    def get_maximized_state(self):
        """Get dockwidget's maximized state."""
        return self._is_maximized

    def set_maximized_state(self, state):
        """
        Set internal attribute that holds dockwidget's maximized state.

        Parameters
        ----------
        state: bool
            True if the plugin is maximized, False otherwise.
        """
        self._is_maximized = state

        # This is necessary for old API plugins interacting with new ones.
        self._plugin._ismaximized = state

    # ---- API: methods to define or override
    # ------------------------------------------------------------------------
    def get_title(self):
        """
        Return the title that will be displayed on dockwidget or window title.
        """
        raise NotImplementedError('PluginMainWidget must define `get_title`!')

    def set_ancestor(self, ancestor):
        """
        Needed to update the ancestor/parent of child widgets when undocking.
        """
        pass

    def setup(self):
        """
        Create widget actions, add to menu and other setup requirements.
        """
        raise NotImplementedError(
            f'{type(self)} must define a `setup` method!')

    def update_actions(self):
        """
        Update the state of exposed actions.

        Exposed actions are actions created by the self.create_action method.
        """
        raise NotImplementedError(
            'A PluginMainWidget subclass must define an `update_actions` '
            f'method! Hint: {type(self)} should implement `update_actions`')

    def on_close(self):
        """
        Perform actions before the widget is closed.

        This method **must** only operate on local attributes.
        """
        pass

    def on_focus_in(self):
        """Perform actions when the widget receives focus."""
        pass

    def on_focus_out(self):
        """Perform actions when the widget loses focus."""
        pass


def run_test():
    # Third party imports
    from qtpy.QtWidgets import QHBoxLayout, QTableWidget, QMainWindow

    # Local imports
    from spyder.utils.qthelpers import qapplication

    app = qapplication()
    main = QMainWindow()
    widget = PluginMainWidget('test', main)
    widget.get_title = lambda x=None: 'Test title'
    widget._setup()
    layout = QHBoxLayout()
    layout.addWidget(QTableWidget())
    widget.setLayout(layout)
    widget.start_spinner()
    dock, location = widget.create_dockwidget(main)
    main.addDockWidget(location, dock)
    main.setStyleSheet(str(APP_STYLESHEET))
    main.show()
    app.exec_()


if __name__ == '__main__':
    run_test()
