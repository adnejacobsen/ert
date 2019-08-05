import sys

try:
  from PyQt4.QtCore import Qt, pyqtSignal, QObject
  from PyQt4.QtGui import QDialog, QVBoxLayout, QLayout, QTabWidget, QHBoxLayout, QPushButton, QToolButton, QMenu, QWidgetAction, QListWidget
except ImportError:
  from PyQt5.QtCore import Qt, pyqtSignal, QObject
  from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLayout, QTabWidget, QHBoxLayout, QPushButton, QToolButton, QMenu, QWidgetAction, QListWidget


from ert_gui import ERT
from ert_gui.tools.plot.widgets import CopyStyleToDialog
from ert_gui.ertwidgets import resourceIcon
from ert_gui.plottery import PlotConfig, PlotConfigHistory
from ert_gui.tools.plot.customize import DefaultCustomizationView, StyleCustomizationView, \
    StatisticsCustomizationView, LimitsCustomizationView


class PlotCustomizer(QObject):

    settingsChanged = pyqtSignal()

    def __init__(self, parent, default_plot_settings=None):
        super(PlotCustomizer, self).__init__()

        self._plot_config_key = None
        self._previous_key = None
        self.default_plot_settings = default_plot_settings
        self._plot_configs = {
            None: PlotConfigHistory(
                "No_Key_Selected",
                PlotConfig(plot_settings=default_plot_settings, title=None))
        }

        self._plotConfigCreator = self._defaultPlotConfigCreator

        self._customization_dialog = CustomizePlotDialog("Customize", parent, key=self._plot_config_key)

        self._customization_dialog.addTab("general", "General", DefaultCustomizationView())
        self._customization_dialog.addTab("style", "Style", StyleCustomizationView())
        self._customization_dialog.addTab("statistics", "Statistics", StatisticsCustomizationView())

        self._customize_limits = LimitsCustomizationView()
        self._customization_dialog.addTab("limits", "Limits", self._customize_limits)

        self._customization_dialog.applySettings.connect(self.applyCustomization)
        self._customization_dialog.undoSettings.connect(self.undoCustomization)
        self._customization_dialog.redoSettings.connect(self.redoCustomization)
        self._customization_dialog.resetSettings.connect(self.resetCustomization)
        self._customization_dialog.copySettings.connect(self.copyCustomization)
        self._customization_dialog.copySettingsToOthers.connect(self.copyCustomizationTo)
        self._revertCustomization(self.getPlotConfig())


    def _getPlotConfigHistory(self):
        """ @rtype: PlotConfigHistory """
        return self._plot_configs[self._plot_config_key]

    def undoCustomization(self):
        history = self._getPlotConfigHistory()
        history.undoChanges()
        self._revertCustomization(history.getPlotConfig())

    def redoCustomization(self):
        history = self._getPlotConfigHistory()
        history.redoChanges()
        self._revertCustomization(history.getPlotConfig())

    def resetCustomization(self):
        history = self._getPlotConfigHistory()
        history.resetChanges()
        self._revertCustomization(history.getPlotConfig())


    def applyCustomization(self):
        history = self._getPlotConfigHistory()
        plot_config = history.getPlotConfig()
        if self._customization_dialog is not None:
            for customization_view in self._customization_dialog:
                customization_view.applyCustomization(plot_config)

        history.applyChanges(plot_config)

        self._emitChangedSignal()


    def _revertCustomization(self, plot_config, emit=True):
        if self._customization_dialog is not None:
            for customization_view in self._customization_dialog:
                customization_view.revertCustomization(plot_config)

        self._emitChangedSignal(emit)

    def _emitChangedSignal(self, emit=True):
        history = self._getPlotConfigHistory()
        self._customization_dialog.setUndoRedoCopyState(history.isUndoPossible(), history.isRedoPossible(), self.isCopyPossible())

        if emit:
            self.settingsChanged.emit()

    def isCopyPossible(self):
        """ @rtype: bool """
        return len(self._plot_configs) > 2

    def copyCustomizationTo(self, keys):
        """ copies the plotconfig of the current key, to a set of other keys"""
        history = self._getPlotConfigHistory()

        for key in keys:
            if key not in self._plot_configs:
                self._plot_configs[key] = PlotConfigHistory("No_Key_Selected",
                                                            PlotConfig(self.default_plot_settings, title=None))
            source_config = history.getPlotConfig()
            source_config.setTitle(key)

            self._plot_configs[key].applyChanges(source_config)

            self._customization_dialog.addCopyableKey(key)

        self._emitChangedSignal(emit=True)


    def copyCustomization(self, key):
        key = str(key)
        if self.isCopyPossible():
            source_config = self._plot_configs[key].getPlotConfig()
            source_config.setTitle(None)

            history = self._getPlotConfigHistory()
            history.applyChanges(source_config)

            self._revertCustomization(history.getPlotConfig())

    def toggleCustomizationDialog(self):
        if self._customization_dialog.isVisible():
            self._customization_dialog.hide()
        else:
            self._customization_dialog.show()

    def _defaultPlotConfigCreator(self, title):
        return PlotConfig(title)

    def _selectiveCopyOfCurrentPlotConfig(self, title):
        return self._plotConfigCreator(title)

    def switchPlotConfigHistory(self, key):
        if key != self._plot_config_key:
            if not key in self._plot_configs:
                self._plot_configs[key] = PlotConfigHistory(key, self._selectiveCopyOfCurrentPlotConfig(key))
                self._customization_dialog.addCopyableKey(key)
            self._customization_dialog.currentPlotKeyChanged(key)
            self._previous_key = self._plot_config_key
            self._plot_config_key = key
            self._revertCustomization(self.getPlotConfig(), emit=False)

    def getPlotConfig(self):
        """ @rtype: PlotConfig """
        return self._getPlotConfigHistory().getPlotConfig()

    def setAxisTypes(self, x_axis_type, y_axis_type):
        self._customize_limits.setAxisTypes(x_axis_type, y_axis_type)

    def setPlotConfigCreator(self, func):
        self._plotConfigCreator = func


class CustomizePlotDialog(QDialog):
    applySettings = pyqtSignal()
    undoSettings = pyqtSignal()
    redoSettings = pyqtSignal()
    resetSettings = pyqtSignal()
    copySettings = pyqtSignal(str)
    copySettingsToOthers = pyqtSignal(list)

    def __init__(self, title, parent=None, key=''):
        QDialog.__init__(self, parent)
        self.setWindowTitle(title)

        self._ert = ERT.ert

        """:type: res.enkf.enkf_main.EnKFMain"""

        self.key_manager = self._ert.getKeyManager()
        """:type: res.enkf.key_manager.KeyManager """

        self.current_key = key

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self._tab_map = {}
        self._tab_order = []

        layout = QVBoxLayout()

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        layout.setSizeConstraint(QLayout.SetFixedSize) # not resizable!!!

        self._button_layout = QHBoxLayout()

        self._reset_button = QToolButton()
        self._reset_button.setIcon(resourceIcon("update.png"))
        self._reset_button.setToolTip("Reset all settings back to default")
        self._reset_button.clicked.connect(self.resetSettings)

        self._undo_button = QToolButton()
        self._undo_button.setIcon(resourceIcon("undo.png"))
        self._undo_button.setToolTip("Undo")
        self._undo_button.clicked.connect(self.undoSettings)

        self._redo_button = QToolButton()
        self._redo_button.setIcon(resourceIcon("redo.png"))
        self._redo_button.setToolTip("Redo")
        self._redo_button.clicked.connect(self.redoSettings)
        self._redo_button.setEnabled(False)

        self._copy_from_button = QToolButton()
        self._copy_from_button.setIcon(resourceIcon("copy_from.png"))
        self._copy_from_button.setToolTip("Copy settings from another key")
        self._copy_from_button.setPopupMode(QToolButton.InstantPopup)
        self._copy_from_button.setEnabled(False)

        self._copy_to_button = QToolButton()
        self._copy_to_button.setIcon(resourceIcon("copy_to.png"))
        self._copy_to_button.setToolTip("Copy current plot settings to other keys")
        self._copy_to_button.setPopupMode(QToolButton.InstantPopup)
        self._copy_to_button.clicked.connect(self.initiateCopyStyleToDialog)
        self._copy_to_button.setEnabled(True)

        tool_menu = QMenu(self._copy_from_button)
        self._popup_list = QListWidget(tool_menu)
        self._popup_list.setSortingEnabled(True)
        self._popup_list.itemClicked.connect(self.keySelected)
        action = QWidgetAction(tool_menu)
        action.setDefaultWidget(self._popup_list)
        tool_menu.addAction(action)
        self._copy_from_button.setMenu(tool_menu)

        self._apply_button = QPushButton("Apply")
        self._apply_button.setToolTip("Apply the new settings")
        self._apply_button.clicked.connect(self.applySettings)
        self._apply_button.setDefault(True)

        self._close_button = QPushButton("Close")
        self._close_button.setToolTip("Hide this dialog")
        self._close_button.clicked.connect(self.hide)

        self._button_layout.addWidget(self._reset_button)
        self._button_layout.addStretch()
        self._button_layout.addWidget(self._undo_button)
        self._button_layout.addWidget(self._redo_button)
        self._button_layout.addWidget(self._copy_from_button)
        self._button_layout.addWidget(self._copy_to_button)
        self._button_layout.addStretch()
        self._button_layout.addWidget(self._apply_button)
        self._button_layout.addWidget(self._close_button)

        layout.addStretch()
        layout.addLayout(self._button_layout)

        self.setLayout(layout)

    def initiateCopyStyleToDialog(self):
        all_other_keys = [k for k in self.key_manager.allDataTypeKeys() if k != self.current_key]
        dialog = CopyStyleToDialog(self, self.current_key, all_other_keys)
        if dialog.exec_():
            self.copySettingsToOthers.emit(dialog.getSelectedKeys())

    def addCopyableKey(self, key):
        self._popup_list.addItem(key)

    def keySelected(self, list_widget_item):
        self.copySettings.emit(str(list_widget_item.text()))

    def currentPlotKeyChanged(self, new_key):
        self.current_key = new_key

    def keyPressEvent(self, q_key_event):
        if q_key_event.key() == Qt.Key_Escape:
            self.hide()
        else:
            QDialog.keyPressEvent(self, q_key_event)

    def addTab(self, attribute_name, title, widget):
        self._tabs.addTab(widget, title)
        self._tab_map[attribute_name] = widget
        self._tab_order.append(attribute_name)

    def __getitem__(self, item):
        """ @rtype: ert_gui.tools.plot.customize.customization_view.CustomizationView """
        return self._tab_map[item]

    def __iter__(self):
        for attribute_name in self._tab_order:
            yield self._tab_map[attribute_name]

    def setUndoRedoCopyState(self, undo, redo, copy=False):
        self._undo_button.setEnabled(undo)
        self._redo_button.setEnabled(redo)
        self._copy_from_button.setEnabled(copy)
