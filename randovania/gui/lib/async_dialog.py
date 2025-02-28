import asyncio

from PySide6 import QtWidgets

from randovania.gui.lib import common_qt_lib


async def execute_dialog(dialog: QtWidgets.QDialog) -> QtWidgets.QDialog.DialogCode:
    """
    An async version of dialog.exec_, internally using QDialog.show
    :param dialog:
    :return:
    """
    future = asyncio.get_event_loop().create_future()

    def set_result(result: QtWidgets.QDialog.DialogCode):
        future.set_result(result)

    dialog.finished.connect(set_result)
    try:
        dialog.show()
        return await future
    finally:
        dialog.finished.disconnect(set_result)


async def message_box(parent: QtWidgets.QWidget | None,
                      icon: QtWidgets.QMessageBox.Icon,
                      title: str, text: str,
                      buttons: QtWidgets.QMessageBox.StandardButtons = QtWidgets.QMessageBox.Ok,
                      default_button: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.NoButton,
                      ) -> QtWidgets.QMessageBox.StandardButton:
    box = QtWidgets.QMessageBox(icon, title, text, buttons, parent)
    box.setDefaultButton(default_button)
    common_qt_lib.set_default_window_icon(box)
    return await execute_dialog(box)


async def warning(parent: QtWidgets.QWidget | None,
                  title: str, text: str,
                  buttons: QtWidgets.QMessageBox.StandardButtons = QtWidgets.QMessageBox.Ok,
                  default_button: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.NoButton,
                  ) -> QtWidgets.QMessageBox.StandardButton:
    return await message_box(parent, QtWidgets.QMessageBox.Warning, title, text, buttons, default_button)
