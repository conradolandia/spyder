# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""
Figure browser widget

This is the main widget used in the Plots plugin
"""

# Standard library imports
import datetime
import math
import os.path as osp
import sys

# Third library imports
from qtconsole.svg import svg_to_clipboard, svg_to_image
from qtpy import PYSIDE2
from qtpy.compat import getexistingdirectory, getsavefilename
from qtpy.QtCore import (
    QEvent,
    QMimeData,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from qtpy.QtGui import QDrag, QPainter, QPixmap
from qtpy.QtWidgets import (QApplication, QFrame, QGridLayout, QLayout,
                            QScrollArea, QScrollBar, QSplitter, QStyle,
                            QVBoxLayout, QWidget)

# Local library imports
from spyder.api.config.mixins import SpyderConfigurationAccessor
from spyder.api.translations import _
from spyder.api.shellconnect.mixins import ShellConnectWidgetForStackMixin
from spyder.api.widgets.mixins import SpyderWidgetMixin
from spyder.utils.misc import getcwd_or_home
from spyder.utils.palette import SpyderPalette
from spyder.utils.stylesheet import AppStyle


# TODO:
# - [ ] Generalize style updates, handle dark_interface with widget option


def save_figure_tofile(fig, fmt, fname):
    """Save fig to fname in the format specified by fmt."""
    root, ext = osp.splitext(fname)
    if ext == '.png' and fmt == 'image/svg+xml':
        qimg = svg_to_image(fig)
        qimg.save(fname)
    else:
        if fmt == 'image/svg+xml' and isinstance(fig, str):
            fig = fig.encode('utf-8')

        with open(fname, 'wb') as f:
            f.write(fig)


def get_unique_figname(dirname, root, ext, start_at_zero=False):
    """
    Append a number to "root" to form a filename that does not already exist
    in "dirname".
    """
    i = 1
    figname = '{}{}'.format(root, ext)
    if start_at_zero:
        i = 0
        figname = '{} ({}){}'.format(root, i, ext)

    while True:
        if osp.exists(osp.join(dirname, figname)):
            figname = '{} ({}){}'.format(root, i, ext)
            i += 1
        else:
            return osp.join(dirname, figname)


class FigureBrowser(
    QWidget, SpyderWidgetMixin, ShellConnectWidgetForStackMixin
):
    """
    Widget to browse the figures that were sent by the kernel to the IPython
    console to be plotted inline.
    """

    sig_figure_loaded = Signal()
    """This signal is emitted when a new figure is loaded."""

    sig_figure_menu_requested = Signal(QPoint)
    """
    This signal is emitted to request a context menu on the main figure
    canvas.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    """

    sig_redirect_stdio_requested = Signal(bool)
    """
    This signal is emitted to request the main application to redirect
    standard output/error when using Open/Save/Browse dialogs within widgets.

    Parameters
    ----------
    redirect: bool
        Start redirect (True) or stop redirect (False).
    """

    sig_save_dir_changed = Signal(str)
    """
    This signal is emitted to inform that the current folder where images are
    saved has changed.

    Parameters
    ----------
    save_dir: str
        The new path where images are saved.
    """

    sig_thumbnail_menu_requested = Signal(QPoint, object)
    """
    This signal is emitted to request a context menu on the figure thumbnails.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    figure_thumbnail: spyder.plugins.plots.widget.figurebrowser.FigureThumbnail
        The clicked figure thumbnail.
    """

    sig_zoom_changed = Signal(int)
    """
    This signal is emitted when zoom has changed.

    Parameters
    ----------
    zoom_value: int
        The new value for the zoom property.
    """

    def __init__(self, parent=None, background_color=None):
        if not PYSIDE2:
            super().__init__(parent=parent, class_parent=parent)
        else:
            QWidget.__init__(self, parent)
            SpyderWidgetMixin.__init__(self, class_parent=parent)

        self.shellwidget = None
        self.figviewer = None
        self.setup_in_progress = False
        self.background_color = background_color
        self.mute_inline_plotting = None
        self.zoom_disp_value = None
        self._update_when_shown = True

        # Setup the figure viewer.
        self.figviewer = FigureViewer(parent=self,
                                      background_color=self.background_color)
        self.figviewer.sig_context_menu_requested.connect(
            self.sig_figure_menu_requested)
        self.figviewer.sig_figure_loaded.connect(self.sig_figure_loaded)
        self.figviewer.sig_zoom_changed.connect(self.sig_zoom_changed)
        self.figviewer.sig_zoom_changed.connect(self._update_zoom_value)

        # Setup the thumbnail scrollbar.
        self.thumbnails_sb = ThumbnailScrollBar(
            self.figviewer,
            parent=self,
            background_color=self.background_color,
        )
        self.thumbnails_sb.sig_context_menu_requested.connect(
            self.sig_thumbnail_menu_requested)
        self.thumbnails_sb.sig_save_dir_changed.connect(
            self.sig_save_dir_changed)
        self.thumbnails_sb.sig_redirect_stdio_requested.connect(
            self.sig_redirect_stdio_requested)

        # Create the layout.
        self.splitter = splitter = QSplitter(parent=self)
        splitter.addWidget(self.figviewer)
        splitter.addWidget(self.thumbnails_sb)
        splitter.setFrameStyle(QScrollArea().frameStyle())
        splitter.setContentsMargins(0, 0, 0, 0)
        splitter.setStyleSheet(
            f"border-radius: {SpyderPalette.SIZE_BORDER_RADIUS}"
        )
        self.splitter.setChildrenCollapsible(False)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        layout = QVBoxLayout()
        layout.addWidget(splitter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        self.setContentsMargins(0, 0, 0, 0)

    def _on_splitter_moved(self):
        total_width = self.splitter.width()
        min_width_percentage = 0.55
        min_width = int(total_width * min_width_percentage)
        self.figviewer.setMinimumWidth(min_width)

    def _update_zoom_value(self, value):
        """
        Used in testing.
        """
        self.zoom_disp_value = value

    def setup(self, options):
        """Setup the figure browser with provided options."""
        self.splitter.setContentsMargins(0, 0, 0, 0)
        for option, value in options.items():
            if option == 'mute_inline_plotting':
                self.mute_inline_plotting = value
                if self.shellwidget:
                    self.shellwidget.set_mute_inline_plotting(value)
            elif option == 'show_plot_outline':
                self.show_fig_outline_in_viewer(value)
            elif option == 'save_dir':
                self.thumbnails_sb.save_dir = value

    def set_pane_empty(self, empty):
        if empty:
            self.is_empty = True
            self.sig_show_empty_message_requested.emit(True)
        else:
            self.is_empty = False
            self.sig_show_empty_message_requested.emit(False)

    def update_splitter_widths(self, base_width):
        """
        Update the widths to provide the scrollbar with a fixed minimum width.

        Parameters
        ----------
        base_width: int
            The available splitter width.
        """
        min_sb_width = self.thumbnails_sb._min_scrollbar_width
        if base_width - min_sb_width > 0:
            self.splitter.setSizes([base_width - min_sb_width, min_sb_width])

    def show_fig_outline_in_viewer(self, state):
        """Draw a frame around the figure viewer if state is True."""
        if state is True:
            self.figviewer.figcanvas.setStyleSheet(
                "FigureCanvas{border: 2px solid %s;}" %
                SpyderPalette.COLOR_BACKGROUND_4
            )
        else:
            self.figviewer.figcanvas.setStyleSheet(
                "FigureCanvas{border: 0px;}")

    def set_shellwidget(self, shellwidget):
        """Bind the shellwidget instance to the figure browser"""
        self.shellwidget = shellwidget
        self.shellwidget.set_mute_inline_plotting(self.mute_inline_plotting)
        shellwidget.sig_new_inline_figure.connect(self.add_figure)
        shellwidget.executing.connect(self._handle_new_execution)

    def add_figure(self, fig, fmt):
        """
        Add a figure to the figure browser.

        This is called when a new figure is sent to the IPython console by the
        kernel, but can also be called directly.
        """
        self.thumbnails_sb.add_thumbnail(fig, fmt)

    def _handle_new_execution(self):
        """Handle a new execution in the console."""
        self.thumbnails_sb._first_thumbnail_shown = False

    # ---- Toolbar Handlers
    def zoom_in(self):
        """Zoom the figure in by a single step in the figure viewer."""
        self.figviewer.zoom_in()

    def zoom_out(self):
        """Zoom the figure out by a single step in the figure viewer."""
        self.figviewer.zoom_out()

    def go_previous_thumbnail(self):
        """
        Select the thumbnail previous to the currently selected one in the
        thumbnail scrollbar.
        """
        self.thumbnails_sb.go_previous_thumbnail()

    def go_next_thumbnail(self):
        """
        Select the thumbnail next to the currently selected one in the
        thumbnail scrollbar.
        """
        self.thumbnails_sb.go_next_thumbnail()

    def save_figure(self):
        """Save the currently selected figure in the thumbnail scrollbar."""
        self.thumbnails_sb.save_current_figure_as()

    def save_all_figures(self):
        """Save all the figures in a selected directory."""
        return self.thumbnails_sb.save_all_figures_as()

    def close_figure(self):
        """Close the currently selected figure in the thumbnail scrollbar."""
        self.thumbnails_sb.remove_current_thumbnail()

    def close_all_figures(self):
        """Close all the figures in the thumbnail scrollbar."""
        self.thumbnails_sb.remove_all_thumbnails()

    def copy_figure(self):
        """Copy figure from figviewer to clipboard."""
        if self.figviewer and self.figviewer.figcanvas.fig:
            self.figviewer.figcanvas.copy_figure()

    # ---- Qt methods
    def showEvent(self, event):
        """Adjustments when the widget is shown."""
        if self._update_when_shown:
            # We only do this the first time the widget is shown to not change
            # the splitter widths that users can set themselves.
            self.update_splitter_widths(self.width())
            self._update_when_shown = False

        super().showEvent(event)


class FigureViewer(QScrollArea, SpyderWidgetMixin):
    """
    A scrollarea that displays a single FigureCanvas with zooming and panning
    capability with CTRL + Mouse_wheel and Left-press mouse button event.
    """

    sig_zoom_changed = Signal(int)
    """
    This signal is emitted when zoom has changed.

    Parameters
    ----------
    zoom_value: int
        The new value for the zoom property.
    """

    sig_context_menu_requested = Signal(QPoint)
    """
    This signal is emitted to request a context menu.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    """

    sig_figure_loaded = Signal()
    """This signal is emitted when a new figure is loaded."""

    def __init__(self, parent=None, background_color=None):
        if not PYSIDE2:
            super().__init__(parent, class_parent=parent)
        else:
            QScrollArea.__init__(self, parent)
            SpyderWidgetMixin.__init__(self, class_parent=parent)

        self.setAlignment(Qt.AlignCenter)
        self.viewport().setObjectName("figviewport")
        self.viewport().setStyleSheet(
            "#figviewport {background-color:" + str(background_color) + "}")
        self.setFrameStyle(0)

        self.background_color = background_color
        self.current_thumbnail = None
        self.scalefactor = 0

        self._scalestep = 1.2
        self._sfmax = 10
        self._sfmin = -10

        self.setup_figcanvas()
        self.auto_fit_plotting = False

        # An internal flag that tracks when the figure is being panned.
        self._ispanning = False

        # To save scrollbar values in the current thumbnail
        self.verticalScrollBar().valueChanged.connect(
            self._set_vscrollbar_value
        )
        self.horizontalScrollBar().valueChanged.connect(
            self._set_hscrollbar_value
        )

    @property
    def auto_fit_plotting(self):
        """
        Return whether to automatically fit the plot to the scroll area size.
        """
        return self._auto_fit_plotting

    @auto_fit_plotting.setter
    def auto_fit_plotting(self, value):
        """
        Set whether to automatically fit the plot to the scroll area size.
        """
        self._auto_fit_plotting = value

        if self.current_thumbnail is not None:
            self.current_thumbnail.auto_fit = value

        if value:
            self.scale_image()
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    @property
    def scalefactor(self):
        """Return the current scale factor."""
        return self._scalefactor

    @scalefactor.setter
    def scalefactor(self, value):
        """Set the scale factor value."""
        self._scalefactor = value
        if self.current_thumbnail is not None:
            self.current_thumbnail.scalefactor = value

    def setup_figcanvas(self):
        """Setup the FigureCanvas."""
        self.figcanvas = FigureCanvas(parent=self,
                                      background_color=self.background_color)
        self.figcanvas.installEventFilter(self)
        self.figcanvas.customContextMenuRequested.connect(
            self.show_context_menu)
        self.setWidget(self.figcanvas)

    def show_context_menu(self, qpoint):
        """Only emit context menu signal if there is a figure."""
        if self.figcanvas and self.figcanvas.fig is not None:
            # Convert to global
            point = self.figcanvas.mapToGlobal(qpoint)
            self.sig_context_menu_requested.emit(point)

    def set_current_thumbnail(self, thumbnail):
        """Set the current thumbnail displayed in the viewer."""
        self.current_thumbnail = thumbnail

    def load_figure(self, fig, fmt):
        """Set a new figure in the figure canvas."""
        self.auto_fit_plotting = self.current_thumbnail.auto_fit

        # Let scale_image compute the scale factor for the thumbnail if it
        # hasn't one yet.
        if self.current_thumbnail.scalefactor is not None:
            self.scalefactor = self.current_thumbnail.scalefactor

        self.figcanvas.load_figure(fig, fmt)
        self.sig_figure_loaded.emit()
        self.scale_image()
        self.figcanvas.repaint()

        # Save the computed scale factor by scale_image in the thumbnail
        if self.current_thumbnail.scalefactor is None:
            self.current_thumbnail.scalefactor = self.scalefactor

        # Restore scrollbar values.
        # We need to use timers for this because trying to set those values
        # immediately after the figure is loaded doesn't work.
        QTimer.singleShot(
            20,
            self.update_scrollbars_values,
        )

    def update_scrollbars_values(self):
        self.verticalScrollBar().setValue(
            self.current_thumbnail.vscrollbar_value
        )
        self.horizontalScrollBar().setValue(
            self.current_thumbnail.hscrollbar_value
        )

    def eventFilter(self, widget, event):
        """A filter to control the zooming and panning of the figure canvas."""

        # ---- Zooming
        if event.type() == QEvent.Wheel and not self.auto_fit_plotting:
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
                return True
            else:
                return False

        # ---- Scaling
        elif event.type() == QEvent.Paint and self.auto_fit_plotting:
            self.scale_image()

        # ---- Panning
        # Set ClosedHandCursor:
        elif event.type() == QEvent.MouseButtonPress:
            if (
                event.button() == Qt.LeftButton
                and not self.auto_fit_plotting
                and (
                    self.verticalScrollBar().isVisible()
                    or self.horizontalScrollBar().isVisible()
                )
            ):
                self.setCursor(Qt.ClosedHandCursor)
                self._ispanning = True
                self.xclick = event.globalX()
                self.yclick = event.globalY()

        # Reset Cursor:
        elif event.type() == QEvent.MouseButtonRelease:
            self.setCursor(Qt.ArrowCursor)
            self._ispanning = False

        # Move  ScrollBar:
        elif event.type() == QEvent.MouseMove:
            if self._ispanning:
                dx = self.xclick - event.globalX()
                self.xclick = event.globalX()

                dy = self.yclick - event.globalY()
                self.yclick = event.globalY()

                scrollBarH = self.horizontalScrollBar()
                scrollBarH.setValue(scrollBarH.value() + dx)

                scrollBarV = self.verticalScrollBar()
                scrollBarV.setValue(scrollBarV.value() + dy)

        # Show in full size
        elif (
            event.type() == QEvent.MouseButtonDblClick
            and self.scalefactor != 0
        ):
            self.auto_fit_plotting = False
            self.zoom_in(to_full_size=True)

            # Necessary to correctly set the state of the fit_action button
            self.sig_figure_loaded.emit()

        return QWidget.eventFilter(self, widget, event)

    # ---- Figure Scaling Handlers
    def zoom_in(self, to_full_size=False):
        """Scale the image up by one scale step."""
        # This is necessary so that the scale factor becomes zero below
        if to_full_size:
            self.scalefactor = -1

        if self.scalefactor <= self._sfmax:
            self.scalefactor += 1
            self.scale_image()
            self._adjust_scrollbar(self._scalestep)

    def zoom_out(self):
        """Scale the image down by one scale step."""
        if self.scalefactor >= self._sfmin:
            self.scalefactor -= 1
            self.scale_image()
            self._adjust_scrollbar(1 / self._scalestep)

    def scale_image(self):
        """Scale the image size."""
        fwidth = self.figcanvas.fwidth
        fheight = self.figcanvas.fheight

        # Don't auto fit plotting
        if not self.auto_fit_plotting:
            new_width = int(fwidth * self._scalestep ** self.scalefactor)
            new_height = int(fheight * self._scalestep ** self.scalefactor)

        # Auto fit plotting
        # Scale the image to fit the figviewer size while respecting the ratio.
        else:
            size = self.size()
            style = self.style()
            width = (size.width() -
                     style.pixelMetric(QStyle.PM_LayoutLeftMargin) -
                     style.pixelMetric(QStyle.PM_LayoutRightMargin))
            height = (size.height() -
                      style.pixelMetric(QStyle.PM_LayoutTopMargin) -
                      style.pixelMetric(QStyle.PM_LayoutBottomMargin))

            self.figcanvas.setToolTip('')

            try:
                if (fwidth / fheight) > (width / height):
                    new_width = int(width)
                    new_height = int(width / fwidth * fheight)
                else:
                    new_height = int(height)
                    new_width = int(height / fheight * fwidth)
            except ZeroDivisionError:
                icon = self.create_icon('broken_image')
                self.figcanvas._qpix_orig = icon.pixmap(fwidth, fheight)
                self.figcanvas.setToolTip(
                    _('The image is broken, please try to generate it again')
                )
                new_width = fwidth
                new_height = fheight
                self.auto_fit_plotting = False

        if self.figcanvas.size() != QSize(new_width, new_height):
            self.figcanvas.setFixedSize(new_width, new_height)

            # Adjust the scale factor according to the scaling of the fitted
            # image. This is necessary so that zoom in/out increases/decreases
            # the image size in factors of of +1/-1 of the one computed below.
            if self.auto_fit_plotting:
                self.scalefactor = self.get_scale_factor()

            self.sig_zoom_changed.emit(self.get_scaling())

    def get_scaling(self):
        """Get the current scaling of the figure in percent."""
        width = self.figcanvas.width()
        fwidth = self.figcanvas.fwidth
        if fwidth != 0:
            return max(round(width / fwidth * 100), 1)
        else:
            return 100

    def get_scale_factor(self):
        """Get scale factor according to the current scaling."""
        return math.log(self.get_scaling() / 100) / math.log(self._scalestep)

    def reset_original_image(self):
        """Reset the image to its original size."""
        self.scalefactor = 0
        self.scale_image()

    def _adjust_scrollbar(self, f):
        """
        Adjust the scrollbar position to take into account the zooming of
        the figure.
        """
        # Adjust horizontal scrollbar :
        hb = self.horizontalScrollBar()
        hb.setValue(int(f * hb.value() + ((f - 1) * hb.pageStep()/2)))

        # Adjust the vertical scrollbar :
        vb = self.verticalScrollBar()
        vb.setValue(int(f * vb.value() + ((f - 1) * vb.pageStep()/2)))

    def _set_vscrollbar_value(self, value):
        """Save vertical scrollbar value in current thumbnail."""
        if self.current_thumbnail is not None:
            self.current_thumbnail.vscrollbar_value = value

    def _set_hscrollbar_value(self, value):
        """Save horizontal scrollbar value in current thumbnail."""
        if self.current_thumbnail is not None:
            self.current_thumbnail.hscrollbar_value = value


class ThumbnailScrollBar(QFrame):
    """
    A widget that manages the display of the FigureThumbnails that are
    created when a figure is sent to the IPython console by the kernel and
    that controls what is displayed in the FigureViewer.
    """
    _min_scrollbar_width = 130

    # Signals
    sig_redirect_stdio_requested = Signal(bool)
    """
    This signal is emitted to request the main application to redirect
    standard output/error when using Open/Save/Browse dialogs within widgets.

    Parameters
    ----------
    redirect: bool
        Start redirect (True) or stop redirect (False).
    """

    sig_save_dir_changed = Signal(str)
    """
    This signal is emitted to inform that the current folder where images are
    saved has changed.

    Parameters
    ----------
    save_dir: str
        The new path where images are saved.
    """

    sig_context_menu_requested = Signal(QPoint, object)
    """
    This signal is emitted to request a context menu.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    """

    def __init__(self, figure_viewer, parent=None, background_color=None):
        super().__init__(parent)
        self._thumbnails = []

        self.background_color = background_color
        self.save_dir = getcwd_or_home()
        self.current_thumbnail = None
        self.set_figureviewer(figure_viewer)
        self.setup_gui()

        # Because the range of Qt scrollareas is not updated immediately
        # after a new item is added to it, setting the scrollbar's value
        # to its maximum value after adding a new item will scroll down to
        # the penultimate item instead of the last.
        # So to scroll programmatically to the latest item after it
        # is added to the scrollarea, we need to do it instead in a slot
        # connected to the scrollbar's rangeChanged signal.
        # See spyder-ide/spyder#10914 for more details.
        self._scroll_to_last_thumbnail = False
        self._first_thumbnail_shown = False
        self.scrollarea.verticalScrollBar().rangeChanged.connect(
            self._scroll_to_newest_item)

        # To reorganize thumbnails with drag and drop
        self.setAcceptDrops(True)

    def setup_gui(self):
        """Setup the main layout of the widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.setup_scrollarea())

    def setup_scrollarea(self):
        """Setup the scrollarea that will contain the FigureThumbnails."""
        self.view = QWidget(self)

        self.scene = QVBoxLayout(self.view)
        self.scene.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scene.setContentsMargins(
            0, AppStyle.MarginSize, 0, AppStyle.MarginSize
        )

        # The vertical spacing between the thumbnails.
        # Note that we need to set this value explicitly or else the tests
        # are failing on macOS. See spyder-ide/spyder#11576.
        self.scene.setSpacing(2 * AppStyle.MarginSize)

        self.scrollarea = QScrollArea(self)
        self.scrollarea.setWidget(self.view)
        self.scrollarea.setWidgetResizable(True)
        self.scrollarea.setFrameStyle(0)
        self.scrollarea.setViewportMargins(
            AppStyle.MarginSize, 0, AppStyle.MarginSize, 0
        )
        self.scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollarea.setMinimumWidth(self._min_scrollbar_width)

        # Set the vertical scrollbar explicitly.
        # This is required to avoid a "RuntimeError: no access to protected
        # functions or signals for objects not created from Python" in Linux.
        self.scrollarea.setVerticalScrollBar(QScrollBar())

        # Install an event filter on the scrollbar.
        self.scrollarea.installEventFilter(self)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        return self.scrollarea

    def set_figureviewer(self, figure_viewer):
        """Set the namespace for the FigureViewer."""
        self.figure_viewer = figure_viewer

    def eventFilter(self, widget, event):
        """
        An event filter to trigger an update of the thumbnails size so that
        their width fit that of the scrollarea and to remap some key press
        events to mimick navigational behaviour of a Qt widget list.
        """
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Up:
                self.go_previous_thumbnail()
                return True
            elif key == Qt.Key_Down:
                self.go_next_thumbnail()
                return True
        if event.type() == QEvent.Resize:
            self._update_thumbnail_size()
        return super().eventFilter(widget, event)

    def dragEnterEvent(self, event):
        """Enable drag events on this widget."""
        event.accept()

    def dropEvent(self, event):
        """
        Handle drop events.

        Solution adapted from
        https://www.pythonguis.com/faq/pyqt-drag-drop-widgets
        """
        # Event variables
        pos = event.pos()
        dropped_thumbnail = event.source()

        # Avoid accepting drops from other widgets
        if not isinstance(dropped_thumbnail, FigureThumbnail):
            return

        # Main variables
        scrollbar_pos = self.scrollarea.verticalScrollBar().value()
        n_thumbnails = self.scene.count()
        last_thumbnail = self.scene.itemAt(n_thumbnails - 1).widget()

        # Move thumbnail
        if (pos.y() + scrollbar_pos) > last_thumbnail.y():
            # This allows to move a thumbnail to the last position
            self.scene.insertWidget(n_thumbnails - 1, dropped_thumbnail)
        else:
            # This works for any other position, including the first one
            for i in range(n_thumbnails):
                w = self.scene.itemAt(i).widget()

                if (
                    (pos.y() + scrollbar_pos)
                    < (w.y() + w.size().height() // 5)
                ):
                    self.scene.insertWidget(i - 1, dropped_thumbnail)
                    break

        # Recreate thumbnails list to take into account the new order
        # Fixes spyder-ide/spyder#22458
        self._thumbnails = []
        for i in range(n_thumbnails):
            self._thumbnails.append(self.scene.itemAt(i).widget())

        event.accept()

    # ---- Save Figure
    def save_all_figures_as(self):
        """Save all the figures to a file."""
        self.sig_redirect_stdio_requested.emit(False)
        dirname = getexistingdirectory(self, 'Save all figures',
                                       self.save_dir)
        self.sig_redirect_stdio_requested.emit(True)

        if dirname:
            self.sig_save_dir_changed.emit(dirname)
            return self.save_all_figures_todir(dirname)

    def save_all_figures_todir(self, dirname):
        """Save all figure in dirname."""
        fignames = []
        figname_root = ('Figure ' +
                        datetime.datetime.now().strftime('%Y-%m-%d %H%M%S'))
        for thumbnail in self._thumbnails:
            fig = thumbnail.canvas.fig
            fmt = thumbnail.canvas.fmt
            fext = {'image/png': '.png',
                    'image/jpeg': '.jpg',
                    'image/svg+xml': '.svg'}[fmt]

            figname = get_unique_figname(dirname, figname_root, fext,
                                         start_at_zero=True)
            save_figure_tofile(fig, fmt, figname)
            fignames.append(figname)
        return fignames

    def save_current_figure_as(self):
        """Save the currently selected figure."""
        if self.current_thumbnail is not None:
            self.save_figure_as(self.current_thumbnail.canvas.fig,
                                self.current_thumbnail.canvas.fmt)

    def save_thumbnail_figure_as(self, thumbnail):
        """Save the currently selected figure."""
        self.save_figure_as(thumbnail.canvas.fig, thumbnail.canvas.fmt)

    def save_figure_as(self, fig, fmt):
        """Save the figure to a file."""
        fext, ffilt = {
            'image/png': ('.png', 'PNG (*.png)'),
            'image/jpeg': ('.jpg', 'JPEG (*.jpg;*.jpeg;*.jpe;*.jfif)'),
            'image/svg+xml': ('.svg', 'SVG (*.svg);;PNG (*.png)')}[fmt]

        figname = get_unique_figname(
            self.save_dir,
            'Figure ' + datetime.datetime.now().strftime('%Y-%m-%d %H%M%S'),
            fext)

        self.sig_redirect_stdio_requested.emit(False)
        fname, fext = getsavefilename(
            parent=self.parent(), caption='Save Figure',
            basedir=figname, filters=ffilt,
            selectedfilter='', options=None)
        self.sig_redirect_stdio_requested.emit(True)

        if fname:
            self.sig_save_dir_changed.emit(osp.dirname(fname))
            save_figure_tofile(fig, fmt, fname)

    # ---- Thumbails Handlers
    def _calculate_figure_canvas_width(self):
        """
        Calculate the width the thumbnails need to have to fit the scrollarea.
        """
        extra_padding = 10 if sys.platform == 'darwin' else 0
        figure_canvas_width = (
            self.scrollarea.width() -
            2 * self.lineWidth() -
            self.scrollarea.viewportMargins().left() -
            self.scrollarea.viewportMargins().right() -
            extra_padding -
            self.scrollarea.verticalScrollBar().sizeHint().width()
            )
        figure_canvas_width = figure_canvas_width - 6
        return figure_canvas_width

    def _setup_thumbnail_size(self, thumbnail):
        """
        Scale the thumbnail's canvas size so that it fits the thumbnail
        scrollbar's width.
        """
        max_canvas_size = self._calculate_figure_canvas_width()
        thumbnail.scale_canvas_size(max_canvas_size)

    def _update_thumbnail_size(self):
        """
        Update the thumbnails size so that their width fit that of
        the scrollarea.
        """
        # NOTE: We hide temporarily the thumbnails to prevent a repaint of
        # each thumbnail as soon as their size is updated in the loop, which
        # causes some flickering of the thumbnail scrollbar resizing animation.
        # Once the size of all the thumbnails has been updated, we show them
        # back so that they are repainted all at once instead of one after the
        # other. This is just a trick to make the resizing animation of the
        # thumbnail scrollbar look smoother.
        self.view.hide()
        for thumbnail in self._thumbnails:
            self._setup_thumbnail_size(thumbnail)
        self.view.show()

    def show_context_menu(self, point, thumbnail):
        """
        Emit global positioned point and thumbnail for context menu request.
        """
        point = thumbnail.canvas.mapToGlobal(point)
        self.sig_context_menu_requested.emit(point, thumbnail)

    def add_thumbnail(self, fig, fmt):
        """
        Add a new thumbnail to that thumbnail scrollbar.
        """
        # Always stick at end for the first thumbnail
        is_first = not self._first_thumbnail_shown

        # Stick at end if we are already at the end
        stick_at_end = False
        sb = self.scrollarea.verticalScrollBar()
        if sb.value() == sb.maximum():
            stick_at_end = True

        thumbnail = FigureThumbnail(
            parent=self, background_color=self.background_color
        )
        thumbnail.canvas.load_figure(fig, fmt)
        thumbnail.sig_canvas_clicked.connect(self.set_current_thumbnail)
        thumbnail.sig_remove_figure_requested.connect(self.remove_thumbnail)
        thumbnail.sig_save_figure_requested.connect(self.save_figure_as)
        thumbnail.sig_context_menu_requested.connect(
            lambda point: self.show_context_menu(point, thumbnail))
        self._thumbnails.append(thumbnail)
        self.scene.addWidget(thumbnail)

        self._scroll_to_last_thumbnail = True
        self._first_thumbnail_shown = True

        # Only select a new thumbnail if the last one was selected
        select_last = (
            len(self._thumbnails) < 2
            or self.current_thumbnail == self._thumbnails[-2]
            or is_first
        )
        if select_last:
            self.set_current_thumbnail(thumbnail)

        thumbnail.show()
        self._setup_thumbnail_size(thumbnail)

        if not is_first and (not stick_at_end or not select_last):
            self._scroll_to_last_thumbnail = False

    def remove_current_thumbnail(self):
        """Remove the currently selected thumbnail."""
        if self.current_thumbnail is not None:
            self.remove_thumbnail(self.current_thumbnail)

    def remove_all_thumbnails(self):
        """Remove all thumbnails."""
        for thumbnail in self._thumbnails:
            thumbnail.sig_canvas_clicked.disconnect()
            thumbnail.sig_remove_figure_requested.disconnect()
            thumbnail.sig_save_figure_requested.disconnect()
            self.layout().removeWidget(thumbnail)
            thumbnail.setParent(None)
            thumbnail.hide()
            thumbnail.close()

        self._thumbnails = []
        self.current_thumbnail = None
        self.figure_viewer.auto_fit_plotting = False
        self.figure_viewer.figcanvas.clear_canvas()

    def remove_thumbnail(self, thumbnail):
        """Remove thumbnail."""
        if thumbnail in self._thumbnails:
            index = self._thumbnails.index(thumbnail)

        # Disconnect signals
        try:
            thumbnail.sig_canvas_clicked.disconnect()
            thumbnail.sig_remove_figure_requested.disconnect()
            thumbnail.sig_save_figure_requested.disconnect()
        except TypeError:
            pass

        if thumbnail in self._thumbnails:
            self._thumbnails.remove(thumbnail)

        # Select a new thumbnail, if any
        if thumbnail == self.current_thumbnail:
            if len(self._thumbnails) > 0:
                self.set_current_index(
                    min(index, len(self._thumbnails) - 1)
                )
            else:
                self.figure_viewer.figcanvas.clear_canvas()
                self.current_thumbnail = None

        # Hide and close thumbnails
        self.layout().removeWidget(thumbnail)
        thumbnail.hide()
        thumbnail.close()

        # See: spyder-ide/spyder#12459
        QTimer.singleShot(
            150, lambda: self._remove_thumbnail_parent(thumbnail))

    def _remove_thumbnail_parent(self, thumbnail):
        try:
            thumbnail.setParent(None)
        except RuntimeError:
            # Omit exception in case the thumbnail has been garbage-collected
            pass

    def set_current_index(self, index):
        """Set the currently selected thumbnail by its index."""
        self.set_current_thumbnail(self._thumbnails[index])

    def get_current_index(self):
        """Return the index of the currently selected thumbnail."""
        try:
            return self._thumbnails.index(self.current_thumbnail)
        except ValueError:
            return -1

    def set_current_thumbnail(self, thumbnail):
        """Set the currently selected thumbnail."""
        if self.current_thumbnail == thumbnail:
            return
        if self.current_thumbnail is not None:
            self.current_thumbnail.highlight_canvas(False)
        self.current_thumbnail = thumbnail
        self.figure_viewer.set_current_thumbnail(thumbnail)
        self.figure_viewer.load_figure(
            thumbnail.canvas.fig, thumbnail.canvas.fmt
        )
        self.current_thumbnail.highlight_canvas(True)

    def go_previous_thumbnail(self):
        """Select the thumbnail previous to the currently selected one."""
        if self.current_thumbnail is not None:
            index = self._thumbnails.index(self.current_thumbnail) - 1
            index = index if index >= 0 else len(self._thumbnails) - 1
            self.set_current_index(index)
            self.scroll_to_item(index)

    def go_next_thumbnail(self):
        """Select thumbnail next to the currently selected one."""
        if self.current_thumbnail is not None:
            index = self._thumbnails.index(self.current_thumbnail) + 1
            index = 0 if index >= len(self._thumbnails) else index
            self.set_current_index(index)
            self.scroll_to_item(index)

    def scroll_to_item(self, index):
        """Scroll to the selected item of ThumbnailScrollBar."""
        spacing_between_items = self.scene.spacing()
        height_view = self.scrollarea.viewport().height()
        height_item = self.scene.itemAt(index).sizeHint().height()
        height_view_excluding_item = max(0, height_view - height_item)

        height_of_top_items = spacing_between_items
        for i in range(index):
            item = self.scene.itemAt(i)
            height_of_top_items += item.sizeHint().height()
            height_of_top_items += spacing_between_items

        pos_scroll = height_of_top_items - height_view_excluding_item // 2

        vsb = self.scrollarea.verticalScrollBar()
        vsb.setValue(pos_scroll)

    def _scroll_to_newest_item(self, vsb_min, vsb_max):
        """
        Scroll to the newest item added to the thumbnail scrollbar.

        Note that this method is called each time the rangeChanged signal
        is emitted by the scrollbar.
        """
        if self._scroll_to_last_thumbnail:
            self._scroll_to_last_thumbnail = False
            self.scrollarea.verticalScrollBar().setValue(vsb_max)

    # ---- ScrollBar Handlers
    def go_up(self):
        """Scroll the scrollbar of the scrollarea up by a single step."""
        vsb = self.scrollarea.verticalScrollBar()
        vsb.setValue(int(vsb.value() - vsb.singleStep()))

    def go_down(self):
        """Scroll the scrollbar of the scrollarea down by a single step."""
        vsb = self.scrollarea.verticalScrollBar()
        vsb.setValue(int(vsb.value() + vsb.singleStep()))



class FigureThumbnail(QWidget):
    """
    A widget that consists of a FigureCanvas, a side toolbar, and a context
    menu that is used to show preview of figures in the ThumbnailScrollBar.
    """

    sig_canvas_clicked = Signal(object)
    """
    This signal is emitted when the figure canvas is clicked.

    Parameters
    ----------
    figure_thumbnail: spyder.plugins.plots.widget.figurebrowser.FigureThumbnail
        The clicked figure thumbnail.
    """

    sig_remove_figure_requested = Signal(object)
    """
    This signal is emitted to request the removal of a figure thumbnail.

    Parameters
    ----------
    figure_thumbnail: spyder.plugins.plots.widget.figurebrowser.FigureThumbnail
        The figure thumbnail to remove.
    """

    sig_save_figure_requested = Signal(object, str)
    """
    This signal is emitted to request the saving of a figure thumbnail.

    Parameters
    ----------
    figure_thumbnail: spyder.plugins.plots.widget.figurebrowser.FigureThumbnail
        The figure thumbnail to save.
    format: str
        The image format to use when saving the image. One of "image/png",
        "image/jpeg" and "image/svg+xml".
    """

    sig_context_menu_requested = Signal(QPoint)
    """
    This signal is emitted to request a context menu.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    """

    def __init__(self, parent=None, background_color=None, auto_fit=True):
        super().__init__(parent)

        self.auto_fit = auto_fit
        self.scalefactor = None
        self.vscrollbar_value = 0
        self.hscrollbar_value = 0

        self.canvas = FigureCanvas(
            parent=self,
            background_color=background_color
        )
        self.canvas.sig_context_menu_requested.connect(
            self.sig_context_menu_requested)
        self.canvas.installEventFilter(self)
        self.setup_gui()

    def setup_gui(self):
        """Setup the main layout of the widget."""
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 0, 0, Qt.AlignCenter)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def highlight_canvas(self, highlight):
        """
        Set a colored frame around the FigureCanvas if highlight is True.
        """
        if highlight:
            # See spyder-ide/spyder#21598 for choice of styling.
            self.canvas.setStyleSheet(
                "FigureCanvas{border: 3px solid %s;}" %
                SpyderPalette.COLOR_ACCENT_3
            )
        else:
            self.canvas.setStyleSheet("FigureCanvas{}")

    def scale_canvas_size(self, max_canvas_size):
        """
        Scale this thumbnail canvas size, while respecting its associated
        figure dimension ratio.
        """
        fwidth = self.canvas.fwidth
        fheight = self.canvas.fheight
        if fheight != 0:
            if fwidth / fheight > 1:
                canvas_width = max_canvas_size
                canvas_height = canvas_width / fwidth * fheight
            else:
                canvas_height = max_canvas_size
                canvas_width = canvas_height / fheight * fwidth
            self.canvas.setFixedSize(int(canvas_width), int(canvas_height))
        self.layout().setColumnMinimumWidth(0, max_canvas_size)

    def eventFilter(self, widget, event):
        """
        A filter that is used to send a signal when the figure canvas is
        clicked.
        """
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.sig_canvas_clicked.emit(self)

        return super().eventFilter(widget, event)

    def mouseMoveEvent(self, event):
        """
        Enable drags to reorganize thumbnails with the mouse in the scrollbar.

        Solution taken from:
        https://www.pythonguis.com/faq/pyqt-drag-drop-widgets/
        """
        if event.buttons() == Qt.LeftButton:
            # Create drag
            drag = QDrag(self)
            mime = QMimeData()
            drag.setMimeData(mime)

            # Show pixmap of the thumbnail while it's being moved.
            pixmap = QPixmap(self.size())
            self.render(pixmap)
            drag.setPixmap(pixmap)

            # Execute drag's event loop
            drag.exec_(Qt.MoveAction)


class FigureCanvas(QFrame, SpyderConfigurationAccessor):
    """
    A basic widget on which can be painted a custom png, jpg, or svg image.
    """

    sig_context_menu_requested = Signal(QPoint)
    """
    This signal is emitted to request a context menu.

    Parameters
    ----------
    point: QPoint
        The QPoint in global coordinates where the menu was requested.
    """

    def __init__(self, parent=None, background_color=None):
        super().__init__(parent)
        self.setLineWidth(2)
        self.setMidLineWidth(1)
        self.setObjectName("figcanvas")
        self.setStyleSheet(
            "#figcanvas {background-color:" + str(background_color) + "}")

        self.fig = None
        self.fmt = None
        self.fwidth, self.fheight = 200, 200
        self._blink_flag = False

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            self.sig_context_menu_requested)

    @Slot()
    def copy_figure(self):
        """Copy figure to clipboard."""
        if self.fmt in ['image/png', 'image/jpeg']:
            qpixmap = QPixmap()
            qpixmap.loadFromData(self.fig, self.fmt.upper())
            QApplication.clipboard().setImage(qpixmap.toImage())
        elif self.fmt == 'image/svg+xml':
            svg_to_clipboard(self.fig)
        else:
            return

        self.blink_figure()

    def blink_figure(self):
        """Blink figure once."""
        if self.fig:
            self._blink_flag = not self._blink_flag
            self.repaint()
            if self._blink_flag:
                timer = QTimer()
                timer.singleShot(40, self.blink_figure)

    def clear_canvas(self):
        """Clear the figure that was painted on the widget."""
        self.fig = None
        self.fmt = None
        self._qpix_scaled = None
        self.repaint()

    def load_figure(self, fig, fmt):
        """
        Load the figure from a png, jpg, or svg image, convert it in
        a QPixmap, and force a repaint of the widget.
        """
        self.fig = fig
        self.fmt = fmt

        if fmt in ['image/png', 'image/jpeg']:
            self._qpix_orig = QPixmap()
            self._qpix_orig.loadFromData(fig, fmt.upper())
        elif fmt == 'image/svg+xml':
            self._qpix_orig = QPixmap(svg_to_image(fig))

        self._qpix_scaled = self._qpix_orig
        self.fwidth = self._qpix_orig.width()
        self.fheight = self._qpix_orig.height()

    def paintEvent(self, event):
        """Qt method override to paint a custom image on the Widget."""
        super().paintEvent(event)

        if self.get_conf('high_dpi_custom_scale_factor', section='main'):
            scale_factors = self.get_conf(
                'high_dpi_custom_scale_factors',
                section='main'
            )
            scale_factor = float(scale_factors.split(":")[0])
        else:
            scale_factor = 1

        # Prepare the rect on which the image is going to be painted.
        fw = self.frameWidth()
        rect = QRect(0 + fw, 0 + fw,
                     self.size().width() - 2 * fw,
                     self.size().height() - 2 * fw)

        if self.fig is None or self._blink_flag:
            return

        # Prepare the scaled qpixmap to paint on the widget.
        if (self._qpix_scaled is None or
                self._qpix_scaled.size().width() != rect.width()):
            if self.fmt in ['image/png', 'image/jpeg']:
                if scale_factor == 1:
                    target_width = rect.width()
                else:
                    target_width = int(self._qpix_orig.width() * scale_factor)
                self._qpix_scaled = self._qpix_orig.scaledToWidth(
                    target_width,
                    mode=Qt.SmoothTransformation
                )
            elif self.fmt == 'image/svg+xml':
                self._qpix_scaled = QPixmap(svg_to_image(
                    self.fig, rect.size()))

        if self._qpix_scaled is not None:
            # Paint the image on the widget.
            qp = QPainter()
            qp.begin(self)
            qp.drawPixmap(rect, self._qpix_scaled)
            qp.end()
