"""Native UI for the supplied WMS SKU -> Picking Task extension.

Uses the existing signed-in Chrome bridge. Searches are user initiated,
with the original extension's parallel searches, bounded retries and partial results. No separate browser or credentials.
"""
import json
import math
import time
import uuid
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidgetItem, QApplication, QHeaderView)
from cot_widgets import CopyTable, LoadingSpinner
from window_layout import fit_window

URL_ORDER='https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/salesorder/search_order'
URL_TASK='https://wms.ssc.shopee.vn/api/v2/apps/process/taskcenter/pickingtask/search_sales_sub_picking_task'
PAGE_SIZE=20
MAX_ORDER_PAGES=100
MAX_TASK_PAGES=5
STRUCT={1:'SSSQ',2:'SSAQ',3:'MSAQ'}

def time_window(now=None):
    now=time.time() if now is None else now
    day_start=math.floor((now+7*3600)/86400)*86400-7*3600
    return {'start_time':day_start-6*86400,'end_time':day_start+86400-1}

def device_codes(task):
    values=task.get('device_id_list')
    if not isinstance(values,list) or not values:values=[task.get('device_id')]
    return list(dict.fromkeys(str(v) for v in values if v and v!='-'))

class TaskSearch(QObject):
    progress=Signal(str)
    completed=Signal(dict)
    failed=Signal(str)
    busyChanged=Signal(bool)
    def __init__(self,bridge,parent=None):
        super().__init__(parent);self.bridge=bridge;self.busy=False
        self.prefix='sku-'+uuid.uuid4().hex+'-';self.counter=0;self.pending=None;self.cancelled=False
        self.bridge.completed.connect(self._reply)
        self.bridge.skuProgress.connect(self._progress)
    def start(self,upc):
        if self.busy:return
        upc=''.join(upc.split())
        if not upc:self.failed.emit('Nhập hoặc quét mã SKU/UPC trước.');return
        if not self.bridge.connected:self.failed.emit('Bấm Đăng nhập WMS và chọn kho trong Chrome trước.');return
        self.counter+=1;self.pending=self.prefix+str(self.counter)
        self.cancelled=False;self.busy=True;self.busyChanged.emit(True)
        self.progress.emit(upc+' · Đang tìm đơn Picked…')
        self.bridge.request(self.pending,json.dumps({'type':'WMS_SKU_SEARCH','url':URL_ORDER,'upc':upc}))
    def cancel(self):
        if not self.busy:return
        self.cancelled=True;self.bridge.cancel_sku(self.pending)
        self.progress.emit('Đang dừng tìm…')
    def _progress(self,rid,message):
        if rid==self.pending and self.busy and not self.cancelled:self.progress.emit(message)
    def _reply(self,rid,raw):
        if rid!=self.pending:return
        self.pending=None;self.busy=False;self.busyChanged.emit(False)
        try:
            result=json.loads(raw)
            if self.cancelled or result.get('cancelled'):
                self.progress.emit('Đã dừng tìm. Kết quả lần trước vẫn được giữ.');return
            if not result.get('success'):raise ValueError(result.get('error') or 'Lỗi WMS')
            data=result['data']
            for entry in data['tasks'].values():entry['sns']=set(entry['sns'])
            self.completed.emit(data)
        except Exception as exc:self.failed.emit(str(exc))

class SkuTaskDialog(QDialog):
    def __init__(self,bridge,parent=None,embedded=False):
        super().__init__(parent)
        if embedded:self.setWindowFlags(Qt.Widget)
        self.setWindowTitle('Tìm Task theo SKU / UPC')
        self.searcher=TaskSearch(bridge,self);self.baskets=[];self.result=None
        layout=QVBoxLayout(self)
        title=QLabel('SKU / UPC → Đơn Picked → Picking Task');title.setStyleSheet('font-size:16px; font-weight:700; color:#89b4fa;');layout.addWidget(title)
        hint=QLabel('Dùng kho đang chọn trong Chrome. Tra task trong hôm nay và 6 ngày trước (giờ Việt Nam).');hint.setWordWrap(True);layout.addWidget(hint)
        row=QHBoxLayout();layout.addLayout(row)
        self.input=QLineEdit();self.input.setPlaceholderText('Quét / nhập SKU ID hoặc UPC rồi Enter');row.addWidget(self.input,1)
        self.find=QPushButton('Tìm Task');row.addWidget(self.find)
        self.stop=QPushButton('Dừng');self.stop.setEnabled(False);row.addWidget(self.stop)
        self.spinner=LoadingSpinner();self.spinner.hide();row.addWidget(self.spinner)
        self.status=QLabel('Chưa tìm. Chỉ gọi WMS khi bấm Tìm Task hoặc Enter.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.table=CopyTable(0,7);self.table.setHorizontalHeaderLabels(['Task ID','Order Structure','Device ID / BSK','SKU Qty','Item Qty','SN khớp','Copy BSK'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        for col,width in enumerate([165,120,180,75,75,80,90]):self.table.setColumnWidth(col,width)
        layout.addWidget(self.table,1)
        self.copy_all=QPushButton('Copy tất cả BSK');self.copy_all.setEnabled(False);layout.addWidget(self.copy_all)
        self.find.clicked.connect(self.start);self.input.returnPressed.connect(self.start)
        self.stop.clicked.connect(self.searcher.cancel);self.copy_all.clicked.connect(lambda:self.copy(self.baskets))
        self.searcher.progress.connect(self.status.setText)
        self.searcher.failed.connect(lambda msg:self.status.setText('Lỗi: '+msg+' · Kết quả trước được giữ.'))
        self.searcher.completed.connect(self.render);self.searcher.busyChanged.connect(self.set_busy)
        if not embedded:fit_window(self,980,620)
    def start(self):
        if self.searcher.busy:return
        self.searcher.start(self.input.text())
    def set_busy(self,busy):
        self.input.setEnabled(not busy);self.find.setEnabled(not busy);self.stop.setEnabled(busy)
        self.spinner.set_running(busy);self.find.setText('Đang tìm…' if busy else 'Tìm Task')
        if not busy:self.input.setFocus();self.input.selectAll()
    def copy(self,values):
        QApplication.clipboard().setText('\n'.join(values))
        self.copy_all.setToolTip(f'Đã copy {len(values)} mã rổ')
    def render(self,result):
        self.result=result;entries=sorted(result['tasks'].items());self.table.setRowCount(len(entries));self.baskets=[]
        for row,(_,entry) in enumerate(entries):
            task=entry['task'];codes=device_codes(task);self.baskets.extend(codes)
            structure=' / '.join(STRUCT.get(int(v),f'?{v}') if str(v).isdigit() else f'?{v}' for v in (task.get('order_structure_list') or [])) or '-'
            values=[task.get('sub_pickup_id',''),structure,', '.join(codes) or '-',task.get('sku_qty','-'),task.get('sku_item_qty','-'),len(entry['sns'])]
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.table.setItem(row,col,item)
            button=QPushButton('Copy');button.setEnabled(bool(codes));button.clicked.connect(lambda _,v=codes:self.copy(v));self.table.setCellWidget(row,6,button)
        self.baskets=list(dict.fromkeys(self.baskets));self.copy_all.setEnabled(bool(self.baskets));self.copy_all.setText(f'Copy tất cả BSK ({len(self.baskets)})')
        self.summary.setText(f"UPC {result['upc']} · Đơn: {result['orders']} · SN: {len(result['sns'])} · Task: {len(entries)}")
        warnings=[]
        if result['orders']!=result['total_api']:warnings.append(f"Lấy {result['orders']}/{result['total_api']} đơn")
        if result['not_found']:warnings.append(f"{len(result['not_found'])} SN không có task")
        if result.get('failed'):warnings.append(f"{len(result['failed'])} SN lỗi gọi API (tìm lại để thử lại)")
        if result['truncated']:warnings.append(f"{len(result['truncated'])} SN vượt giới hạn 100 task; kết quả chưa đầy đủ")
        self.status.setText(' · '.join(warnings) if warnings else ('Không có đơn Picked khớp mã.' if not result['sns'] else 'Đã tìm xong. Chọn ô/cột rồi Ctrl+C để sao chép.'))
    def closeEvent(self,event):
        self.searcher.cancel();super().closeEvent(event)
    def reject(self):
        self.searcher.cancel();super().reject()
