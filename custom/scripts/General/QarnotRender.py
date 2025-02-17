from System.IO import *

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QObject, pyqtSignal, QThreadPool, QRunnable, pyqtSlot, Qt

from Deadline.Scripting import *
from DeadlineUI.Controls.Scripting.DeadlineScriptDialog import DeadlineScriptDialog

import ThinkboxUI

import qarnot_render_deadline

import os, traceback, sys

########################################################################
## Globals
########################################################################
script_dialog = None
q_render_deadline = None

########################################################################
## Main Function Called By Deadline
########################################################################
def __main__():
    global script_dialog

    script_dialog = DeadlineScriptDialog()
    script_dialog.SetTitle("Qarnot Render")

    script_dialog.AddTabControl("Example Tab Control", 0, 0)

    script_dialog.AddTabPage("Manage")
    grid = script_dialog.AddGrid()

    script_dialog.AddControlToGrid(
        "StartInstancesSeparator",
        "SeparatorControl",
        "Start instances",
        0,
        0,
        colSpan=2,
    )

    script_dialog.AddControlToGrid(
        "QarnotProfileLabel", "LabelControl", "Qarnot profile", 1, 0, expand=False
    )
    profile_list = script_dialog.AddComboControlToGrid(
        "QarnotProfileCombo",
        "ComboControl",
        "",
        ["No deadline profiles availabe"],
        1,
        1,
    )
    # set a default config message in italic
    profile_list_font = profile_list.font()
    profile_list_font.setItalic(True)
    profile_list.setFont(profile_list_font)

    script_dialog.AddControlToGrid(
        "QarnotInstancesNumberLabel",
        "LabelControl",
        "Number of instances to start",
        2,
        0,
        "Specify the number of workers to start.",
        expand=False,
    )
    script_dialog.AddRangeControlToGrid(
        "QarnotInstancesNumberBox", "RangeControl", 1, 1, 1000000, 0, 1, 2, 1
    )

    submit_button = script_dialog.AddControlToGrid(
        "SubmitButton", "ButtonControl", "Submit", 3, 0, colSpan=2
    )
    submit_button.ValueModified.connect(submit_button_pressed)
    # disable the submit button by default
    # it will be enabled when the profile list is populated
    script_dialog.SetEnabled("SubmitButton", False)

    script_dialog.AddControlToGrid(
        "QarnotConsoleSeparator",
        "SeparatorControl",
        "Qarnot Console",
        4,
        0,
        colSpan=2,
    )

    console_button = script_dialog.AddControlToGrid(
        "ConsoleButton", "ButtonControl", "Open Qarnot Console", 5, 0, colSpan=2
    )
    console_button.ValueModified.connect(console_button_pressed)

    script_dialog.AddControlToGrid(
        "PoolsSeparator",
        "SeparatorControl",
        "Active pools",
        6,
        0,
        colSpan=2,
    )

    pool_model = PoolModel()

    pool_view = QtWidgets.QTableView()
    pool_view.setObjectName("PoolView")
    pool_view.setModel(pool_model)
    # hide the UUID column (but the data needs to stay to launch actions against
    # the selected pools)
    pool_view.setColumnHidden(2, True)
    # auto adjust column width based on content
    pool_view.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
    pool_view.resizeColumnsToContents()
    # automatically resize columns when the model changes
    pool_model.layoutChanged.connect(pool_view.resizeColumnsToContents)
    # select row with one click
    pool_view.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
    # automatically enable/disable the pool close button
    pool_model.layoutChanged.connect(update_pool_close_button)

    grid.addWidget(pool_view, 7, 0, 1, 2)

    pool_close_button = script_dialog.AddControlToGrid(
        "PoolCloseButton", "ButtonControl", "Close pool", 8, 0, colSpan=1
    )
    # disable the close button by default
    # it will be enabled when the pool table is populated
    script_dialog.SetEnabled("PoolCloseButton", False)
    pool_close_button.ValueModified.connect(pool_close_button_pressed)

    script_dialog.EndGrid()
    script_dialog.EndTabPage()

    script_dialog.AddTabPage("Configuration")
    script_dialog.AddGrid()

    script_dialog.AddControlToGrid(
        "APIConfigurationSeparator",
        "SeparatorControl",
        "API Configuration",
        0,
        0,
        colSpan=2,
    )

    script_dialog.AddControlToGrid(
        "ClusterAPIURLLabel", "LabelControl", "Cluster API URL", 1, 0, expand=False
    )
    cluster_api_url_box = script_dialog.AddControlToGrid(
        "ClusterAPIURLBox", "TextControl", "https://api.qarnot.com", 1, 1
    )
    cluster_api_url_box.ValueModified.connect(update_qarnot_account_url)

    script_dialog.AddControlToGrid(
        "APITokenLabel",
        "LabelControl",
        "API Token",
        2,
        0,
        expand=False,
    )
    # create a clickable link to the account page
    update_qarnot_account_url()
    script_dialog.SetToolTip(
        "APITokenLabel",
        "Click this link to access your API token on your Qarnot account page",
    )
    script_dialog.AddControlToGrid("APITokenBox", "PasswordControl", "", 2, 1)

    save_button = script_dialog.AddControlToGrid(
        "SaveButton", "ButtonControl", "Save", 3, 0, colSpan=2
    )
    save_button.ValueModified.connect(save_button_pressed)

    script_dialog.EndGrid()
    script_dialog.EndTabPage()

    script_dialog.EndTabControl()

    script_dialog.AddGrid()

    script_dialog.AddHorizontalSpacerToGrid("DummyHorizontalSpacer", 0, 0)
    close_button = script_dialog.AddControlToGrid(
        "CloseButton", "ButtonControl", "Close", 0, 1, expand=False
    )
    close_button.ValueModified.connect(close_button_pressed)

    script_dialog.EndGrid()

    # load settings and refresh some controls accordingly
    script_dialog.LoadSettings(
        os.path.join(ClientUtils.GetUsersSettingsDirectory(), "QarnotRender.ini"),
        ["ClusterAPIURLBox", "APITokenBox"],
    )

    refresh_qarnot_profiles_combo()
    refresh_qarnot_pools()

    script_dialog.ShowDialog(True)


########################################################################
## Helper Functions
########################################################################
def refresh_qarnot_profiles_combo():
    """
    Refresh the profiles combo box.
    """
    global script_dialog
    global q_render_deadline

    # TODO: move first connection and q_render_deadline initialization in its
    # own function
    cluster_api_url = script_dialog.GetValue("ClusterAPIURLBox")
    api_token = script_dialog.GetValue("APITokenBox")
    if cluster_api_url and api_token:
        q_render_deadline = qarnot_render_deadline.QarnotRenderDeadline(
            cluster_url=cluster_api_url,
            client_token=api_token,
        )
        # fetch profiles in a worker thread
        worker = Worker(fetch_qarnot_profiles)
        worker.signals.result.connect(update_combo)
        worker.signals.error.connect(display_invalid_conf)
        QThreadPool.globalInstance().start(worker)
    else:
        error_message = (
            "Qarnot API URL and token are not set, check the configuration tab"
        )
        script_dialog.SetItems("QarnotProfileCombo", [error_message])
        script_dialog.ShowMessageBox(
            error_message,
            "Configuration issue",
        )


def fetch_qarnot_profiles():
    """
    Fetch deadline profiles via the Qarnot API.

    Returns:
        qarnot_profiles: list of available Qarnot deadline profiles
    """
    global script_dialog

    # disable submit button
    script_dialog.SetEnabled("SubmitButton", False)
    # display loading message
    script_dialog.SetItems("QarnotProfileCombo", ["Loading profiles..."])
    profile_list = script_dialog.findChild(
        ThinkboxUI.Controls.Scripting.ComboControl.ComboControl,
        "QarnotProfileCombo",
    )
    # set italic font
    profile_list_font = profile_list.font()
    profile_list_font.setItalic(True)
    profile_list.setFont(profile_list_font)

    # fetch profiles
    q_render_deadline.refresh_connection()
    qarnot_profiles = q_render_deadline.get_available_profiles()

    return qarnot_profiles


def update_combo(profiles):
    """
    Update profiles ComboControl widget

    Args:
        profiles: list of Qarnot profiles
    """
    global script_dialog

    # populate the ComboControl widget
    qarnot_profiles_names = [x.name for x in profiles]
    script_dialog.SetItems("QarnotProfileCombo", qarnot_profiles_names)
    profile_list = script_dialog.findChild(
        ThinkboxUI.Controls.Scripting.ComboControl.ComboControl,
        "QarnotProfileCombo",
    )
    # remove italic font
    profile_list_font = profile_list.font()
    profile_list_font.setItalic(False)
    profile_list.setFont(profile_list_font)
    # enable the Submit button
    script_dialog.SetEnabled("SubmitButton", True)


def display_invalid_conf():
    global script_dialog

    error_message = "Qarnot API credentials are invalid, check the configuration tab"
    script_dialog.SetItems("QarnotProfileCombo", [error_message])
    script_dialog.ShowMessageBox(
        error_message,
        "Configuration issue",
    )


def refresh_qarnot_pools():
    # fetch pools in a worker thread
    worker = Worker(fetch_qarnot_pools)
    worker.signals.result.connect(update_pool_view)
    QThreadPool.globalInstance().start(worker)


def fetch_qarnot_pools():

    # display loading message
    pool_view = script_dialog.findChild(
        QtWidgets.QTableView,
        "PoolView",
    )
    pool_model = pool_view.model()
    pool_model.display_loading_message()

    # fetch active pools
    q_render_deadline.refresh_connection()
    active_pools = q_render_deadline.get_active_pools()

    return active_pools


def update_pool_view(active_pools):
    global script_dialog

    pool_view = script_dialog.findChild(
        QtWidgets.QTableView,
        "PoolView",
    )
    pool_model = pool_view.model()

    pool_model.pools = active_pools


def submit_button_pressed(*args):
    global script_dialog
    global q_render_deadline

    profile = script_dialog.GetValue("QarnotProfileCombo")
    instance_number = script_dialog.GetValue("QarnotInstancesNumberBox")
    q_render_deadline.create_instances(profile, instance_number)
    script_dialog.ShowMessageBox(
        "Pool submitted, open the Qarnot Console for more information",
        "Submit confirmation",
    )
    refresh_qarnot_pools()


def console_button_pressed(*args):
    global script_dialog

    url = script_dialog.GetValue("ClusterAPIURLBox").replace("api", "console")
    script_dialog.OpenUrl(url)


def update_pool_close_button(*args):
    global script_dialog

    pool_view = script_dialog.findChild(
        QtWidgets.QTableView,
        "PoolView",
    )
    pool_model = pool_view.model()

    # check pool uuid value of first line
    pool_uuid = pool_model.data(pool_model.index(0, 2), Qt.DisplayRole)

    if pool_uuid:
        script_dialog.SetEnabled("PoolCloseButton", True)
    else:
        script_dialog.SetEnabled("PoolCloseButton", False)


def pool_close_button_pressed(*args):
    global script_dialog
    global q_render_deadline

    pool_view = script_dialog.findChild(
        QtWidgets.QTableView,
        "PoolView",
    )
    indexes = pool_view.selectionModel().selectedRows()

    for index in indexes:
        pool_uuid = index.child(index.row(), 2).data()
        q_render_deadline.stop_instances(pool_uuid)

    refresh_qarnot_pools()


def update_qarnot_account_url(*args):
    global script_dialog

    url = script_dialog.GetValue("ClusterAPIURLBox").replace("api", "account")
    # TODO: get the default text color from the Qt palette (instead of assuming it is "white")
    api_token_link = (
        '<a href="' + url + '"><span style="color: white">API Token</span></a>'
    )
    script_dialog.SetValue("APITokenLabel", api_token_link)


def save_button_pressed(*args):
    global script_dialog

    script_dialog.SaveSettings(
        os.path.join(ClientUtils.GetUsersSettingsDirectory(), "QarnotRender.ini"),
        ["ClusterAPIURLBox", "APITokenBox"],
    )
    refresh_qarnot_profiles_combo()


def close_button_pressed(*args):
    global script_dialog
    script_dialog.CloseDialog()


########################################################################
## Helper Classes
########################################################################
class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Source: https://www.mfitzp.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    """

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class Worker(QRunnable):
    """
    Worker thread
    Source: https://www.mfitzp.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.setAutoDelete(True)
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialize the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class PoolModel(QtCore.QAbstractTableModel):
    def __init__(self, pools=None):
        super(QtCore.QAbstractTableModel, self).__init__()
        self._pools = pools
        self._data = []
        self._columns = ["Pool name", "Instances", "UUID"]

        self._set_table_data()

    def _set_table_data(self):
        if self._pools:
            self._data = [(x.name, x.instancecount, x.uuid) for x in self._pools]
        else:
            self._data = [["No active pools", None, None]]
        self.layoutChanged.emit()

    @property
    def pools(self):
        """
        Returns the pools list.

        Returns:
            pools: list of pool objects
        """
        return self._pools

    @pools.setter
    def pools(self, value):
        """Setter for pools"""
        self._pools = value
        self._set_table_data()

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data[index.row()][index.column()]

        if role == Qt.TextAlignmentRole:
            value = self._data[index.row()][index.column()]

            # right-align numbers
            if isinstance(value, int):
                return Qt.AlignVCenter + Qt.AlignRight

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._columns[section])

            if orientation == Qt.Vertical:
                # return str(self._data.index[section])
                return section + 1

    def display_loading_message(self):
        self._data = [["Loading pools...", None, None]]
        self.layoutChanged.emit()
