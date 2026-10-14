"""Local table selection and sliding order panel; no WMS transport."""
from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QKeySequence, QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget, QTableWidget, QAbstractItemView, QApplication, QLabel

class LoadingSpinner(QWidget):
    """Small local animation; its timer only repaints and never requests data."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(22,22);self.angle=0
        self.timer=QTimer(self);self.timer.setInterval(60)
        self.timer.timeout.connect(self.advance)
        self.setAccessibleName('Đang tải dữ liệu')
    def advance(self):
        self.angle=(self.angle+24)%360;self.update()
    def set_running(self,running):
        if running:self.timer.start()
        else:self.timer.stop()
        self.setVisible(running)
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=QRectF(3,3,16,16)
        painter.setPen(QPen(QColor('#a7c9eb'),2.5));painter.drawEllipse(rect)
        pen=QPen(QColor('#2389ef'),2.5);pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen);painter.drawArc(rect,-self.angle*16,105*16)

class CopyTable(QTableWidget):
    def __init__(self, *args):
        super().__init__(*args)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.horizontalHeader().setSectionsClickable(True)
        self.horizontalHeader().sectionClicked.connect(self.selectColumn)
        self.setStyleSheet('QTableWidget {selection-background-color:#ffd45c; selection-color:#242000;} QTableWidget::item:selected {background:#ffd45c; color:#242000;}')

    def copy_selection(self):
        cells={(i.row(),i.column()):str(i.data() or '') for i in self.selectedIndexes()}
        if not cells:return
        rows=sorted({r for r,c in cells});cols=sorted({c for r,c in cells})
        QApplication.clipboard().setText('\n'.join('\t'.join(cells.get((r,c),'') for c in cols) for r in rows))

    def keyPressEvent(self,event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection();event.accept();return
        super().keyPressEvent(event)

class DragHandle(QLabel):
    moved=Signal(int)
    released=Signal()
    def __init__(self,parent=None):
        super().__init__('━━━━  Kéo lên / xuống để mở rộng bảng đơn  ━━━━',parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setFixedHeight(22)
        self.setStyleSheet('background:#313244; color:#a6adc8; border-radius:5px; font-size:11px;')
        self.anchor=None
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.anchor=int(event.globalPosition().y());event.accept()
    def mouseMoveEvent(self,event):
        if self.anchor is not None:
            pos=int(event.globalPosition().y());self.moved.emit(pos-self.anchor);self.anchor=pos;event.accept()
    def mouseReleaseEvent(self,event):
        if self.anchor is not None:
            self.anchor=None;self.released.emit();event.accept()

class SlidingOrders(QWidget):
    """The upper panel never resizes vertically; the lower panel covers it."""
    positionChanged=Signal(int)
    def __init__(self,config,save_config,parent=None):
        super().__init__(parent)
        self.config=config;self.save_config=save_config;self.upper_height=228
        saved=config.get('cot_panel_reveal',self.upper_height)
        self.reveal=max(0,min(self.upper_height,saved)) if isinstance(saved,int) else self.upper_height
        self.expanded_reveal=self.reveal or self.upper_height
        self.upper=QWidget(self)
        self.lower=QWidget(self);self.lower.setObjectName('ordersOverlay')
        self.lower.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.lower.setStyleSheet('QWidget#ordersOverlay {background:#1e1e2e;}')
        self.handle=DragHandle(self.lower)
        self.handle.moved.connect(lambda delta:self.set_reveal(self.reveal+delta))
        self.handle.released.connect(self.persist)
        self.setMinimumHeight(270)
    def set_reveal(self,value):
        self.reveal=max(0,min(self.upper_height,int(value)))
        self.arrange();self.positionChanged.emit(self.reveal)
    def arrange(self):
        self.upper.setGeometry(0,0,self.width(),self.upper_height)
        # Clamp only the visible position on short windows, not the saved preference.
        y=min(self.reveal,max(0,self.height()-240))
        self.lower.setGeometry(0,y,self.width(),max(0,self.height()-y));self.lower.raise_()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.arrange()
    def toggle(self):
        if self.reveal:
            self.expanded_reveal=self.reveal;self.set_reveal(0)
        else:self.set_reveal(self.expanded_reveal)
        self.persist()
    def persist(self):
        self.config['cot_panel_reveal']=self.reveal
        if not self.save_config(self.config):self.handle.setToolTip('Chưa lưu được vị trí kéo cho lần mở sau.')
