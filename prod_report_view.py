"""Presentation-only helpers. Never infer quantities from rounded productivity."""
from datetime import datetime

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QTableWidget, QTableView, QStyledItemDelegate, QStyle

import prod_native_core as core


def hourly_windows(interval):
    start, end = interval['from'], interval['to']
    windows = []
    while start <= end:
        stop = min((start // 3600 + 1) * 3600 - 1, end)
        label = (datetime.fromtimestamp(start, core.VN_TZ).strftime('%H:%M') + '–' +
                 datetime.fromtimestamp(stop, core.VN_TZ).strftime('%H:%M'))
        windows.append({'from': start, 'to': stop, 'label': label})
        start = stop + 1
    return windows


def raw_totals(rows, station=False):
    """Keep API zero, missing and duplicate rows distinct; sum exact fields only."""
    result = {}
    for row in rows:
        key = core.norm_id(row.get('station_id')) if station else core.norm(row.get('staff_email'))
        if not key:
            continue
        values = {name: core.num(row.get(source)) for name, source in
                  (('qty', 'sum_count'), ('hours', 'man_hour'))}
        if key not in result:
            result[key] = values
        else:
            for name, value in values.items():
                previous = result[key][name]
                result[key][name] = previous + value if previous is not None and value is not None else None
    return result


class EmployeeDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        text = index.data() or '—'
        name, _, email = text.partition('\n')
        self.initStyleOption(option, index)
        option.text = ''
        style = option.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)
        painter.save()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        color = option.palette.color(QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text)
        painter.setPen(color)
        font = option.font; font.setBold(True); painter.setFont(font)
        rect = option.rect.adjusted(12, 5, -10, -5)
        painter.drawText(QRect(rect.x(), rect.y(), rect.width(), 23), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(name, Qt.ElideRight, rect.width()))
        font.setBold(False); font.setPointSize(max(8, font.pointSize() - 1)); painter.setFont(font)
        if not selected:
            color.setAlpha(180)
        painter.setPen(color)
        painter.drawText(QRect(rect.x(), rect.y()+23, rect.width(), 20), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(email, Qt.ElideRight, rect.width()))
        painter.restore()


class EmployeeTable(QTableWidget):
    """One shared model, with STT and employee columns frozen while scrolling."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(56)
        self.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.frozen = QTableView(self)
        self.frozen.setModel(self.model())
        self.frozen.setSelectionModel(self.selectionModel())
        self.frozen.verticalHeader().hide()
        self.frozen.setFocusPolicy(Qt.NoFocus)
        self.frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frozen.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.frozen.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.frozen.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.frozen.setAlternatingRowColors(True)
        self.frozen.clicked.connect(lambda index: self.cellClicked.emit(index.row(), index.column()))
        self.verticalScrollBar().valueChanged.connect(self.frozen.verticalScrollBar().setValue)
        self.frozen.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)
        self.horizontalHeader().sectionResized.connect(self._resize_column)
        self.frozen.horizontalHeader().sectionResized.connect(lambda c, old, size: self.setColumnWidth(c, size))
        self.verticalHeader().sectionResized.connect(lambda row, old, size: self.frozen.setRowHeight(row, size))
        self.setItemDelegateForColumn(1, EmployeeDelegate(self))
        self.frozen.setItemDelegateForColumn(1, EmployeeDelegate(self.frozen))

    def _resize_column(self, column, old, size):
        if column < 2:
            self.frozen.setColumnWidth(column, size)
            self._position_frozen()

    def sync_frozen(self):
        for column in range(self.columnCount()):
            self.frozen.setColumnHidden(column, column >= 2)
        for column in range(min(2, self.columnCount())):
            self.frozen.setColumnWidth(column, self.columnWidth(column))
        for row in range(self.rowCount()):
            self.frozen.setRowHeight(row, self.rowHeight(row))
        self._position_frozen()
        self.frozen.raise_()

    def _position_frozen(self):
        # Hourly headers span two lines; both views must share the same row origin.
        self.frozen.horizontalHeader().setFixedHeight(self.horizontalHeader().height())
        width = sum(self.columnWidth(c) for c in range(min(2, self.columnCount())))
        self.frozen.setGeometry(self.frameWidth(), self.frameWidth(), width,
                               self.viewport().height() + self.horizontalHeader().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'frozen'):
            self._position_frozen()
