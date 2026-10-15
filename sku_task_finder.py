"""Native UI for the supplied WMS SKU -> Picking Task extension.

Uses the existing signed-in Chrome bridge. Searches are user initiated,
serial, and never automatically retried. No separate browser or credentials.
"""
import json
import math
import time
import uuid
from PySide6.QtCore import QObject, Signal, QTimer
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
        self.prefix='sku-'+uuid.uuid4().hex+'-';self.counter=0;self.pending=None
        self.cancelled=False;self.timer=QTimer(self);self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._send);self.next_request=None
        self.bridge.completed.connect(self._reply)
    def start(self,upc):
        if self.busy:return
        upc=''.join(upc.split())
        if not upc:self.failed.emit('Nhập hoặc quét mã SKU/UPC trước.');return
        if not self.bridge.connected:self.failed.emit('Bấm Đăng nhập WMS và chọn kho trong Chrome trước.');return
        self.upc=upc;self.orders={};self.tasks={};self.sns=[];self.not_found=[];self.truncated=[]
        self.order_page=1;self.sn_index=0;self.task_page=1;self.sn_found=False
        self.win=time_window();self.cancelled=False;self.busy=True;self.busyChanged.emit(True)
        self._orders()
    def cancel(self):
        if not self.busy:return
        self.cancelled=True;self.timer.stop();self.next_request=None
        if self.pending:self.progress.emit('Đang dừng · chờ yêu cầu đã gửi kết thúc…')
        else:self._stop_cancelled()
    def _stop_cancelled(self):
        self._finish();self.progress.emit('Đã dừng tìm. Kết quả lần trước vẫn được giữ.')
    def _finish(self):
        self.timer.stop();self.next_request=None;self.busy=False;self.busyChanged.emit(False)
    def _request(self,url,body,callback):
        self.next_request=(url,body,callback)
        # A single request in flight, with a pause between pages/SNs.
        self.timer.start(0 if self.counter==0 else 300)
    def _send(self):
        if not self.busy or self.cancelled or self.next_request is None:return
        url,body,callback=self.next_request;self.next_request=None
        self.counter+=1;rid=self.prefix+str(self.counter);self.pending=(rid,callback)
        self.bridge.request(rid,json.dumps({'type':'WMS_POST','url':url,'body':body}))
    def _reply(self,rid,raw):
        if not self.pending or rid!=self.pending[0]:return
        callback=self.pending[1];self.pending=None
        if self.cancelled:self._stop_cancelled();return
        try:
            result=json.loads(raw)
            if not result.get('success'):raise ValueError(result.get('error') or 'Lỗi WMS')
            data=result.get('data')
            if not isinstance(data,dict) or not isinstance(data.get('list'),list):
                raise ValueError('WMS trả dữ liệu không đúng định dạng; chưa thay kết quả cũ.')
            callback(data)
        except Exception as exc:
            self._finish();self.failed.emit(str(exc))
    def _orders(self):
        self.progress.emit(f'{self.upc} · Đang tìm đơn Picked · trang {self.order_page}…')
        self._request(URL_ORDER,{'sku_upc_code':self.upc,'order_status_list':'3',
            'pageno':self.order_page,'count':PAGE_SIZE,'is_get_total':int(self.order_page==1)},self._got_orders)
    def _got_orders(self,data):
        if self.order_page==1:
            self.total=int(data.get('total') or 0);self.order_pages=max(1,math.ceil(self.total/PAGE_SIZE))
            if self.order_pages>MAX_ORDER_PAGES:raise ValueError(f'Quá nhiều đơn ({self.total}), vượt giới hạn {MAX_ORDER_PAGES*PAGE_SIZE} của tiện ích.')
        for order in data['list']:
            if not isinstance(order,dict) or not order.get('order_number'):raise ValueError('Đơn WMS thiếu mã order_number.')
            self.orders[str(order['order_number'])]=order
        if self.order_page<self.order_pages:
            self.order_page+=1;self._orders();return
        sns={}
        for order in self.orders.values():
            values=order.get('shopee_order_sn');values=values if isinstance(values,list) else [values]
            for sn in values:
                if sn and str(sn).strip():sns[str(sn).strip()]=None
        self.sns=list(sns)
        if not self.sns:self._done();return
        self._task()
    def _task(self):
        self.progress.emit(f'{self.upc} · Tra Picking Task · {self.sn_index}/{len(self.sns)} SN · trang {self.task_page}…')
        self._request(URL_TASK,{'search_key_two':self.sns[self.sn_index],**self.win,
            'fulfillment_chain_dest_zone_list':[],'pageno':self.task_page,'count':PAGE_SIZE},self._got_tasks)
    def _got_tasks(self,data):
        sn=self.sns[self.sn_index]
        for task in data['list']:
            if not isinstance(task,dict) or not task.get('sub_pickup_id'):raise ValueError('Task WMS thiếu sub_pickup_id.')
            key=str(task['sub_pickup_id'])
            entry=self.tasks.setdefault(key,{'task':task,'sns':set()});entry['sns'].add(sn)
            self.sn_found=True
        more=self.task_page*PAGE_SIZE<int(data.get('total') or 0)
        if more and self.task_page<MAX_TASK_PAGES:
            self.task_page+=1;self._task();return
        if more:self.truncated.append(sn)
        if not self.sn_found:self.not_found.append(sn)
        self.sn_index+=1;self.task_page=1;self.sn_found=False
        if self.sn_index<len(self.sns):self._task()
        else:self._done()
    def _done(self):
        result={'upc':self.upc,'total_api':self.total,'orders':len(self.orders),
            'sns':self.sns,'tasks':self.tasks,'not_found':self.not_found,'truncated':self.truncated}
        self._finish();self.completed.emit(result)

class SkuTaskDialog(QDialog):
    def __init__(self,bridge,parent=None):
        super().__init__(parent);self.setWindowTitle('Tìm Task theo SKU / UPC')
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
        fit_window(self,980,620)
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
            values=[task['sub_pickup_id'],structure,', '.join(codes) or '-',task.get('sku_qty','-'),task.get('sku_item_qty','-'),len(entry['sns'])]
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.table.setItem(row,col,item)
            button=QPushButton('Copy');button.setEnabled(bool(codes));button.clicked.connect(lambda _,v=codes:self.copy(v));self.table.setCellWidget(row,6,button)
        self.baskets=list(dict.fromkeys(self.baskets));self.copy_all.setEnabled(bool(self.baskets));self.copy_all.setText(f'Copy tất cả BSK ({len(self.baskets)})')
        self.summary.setText(f"UPC {result['upc']} · Đơn: {result['orders']} · SN: {len(result['sns'])} · Task: {len(entries)}")
        warnings=[]
        if result['orders']!=result['total_api']:warnings.append(f"Lấy {result['orders']}/{result['total_api']} đơn")
        if result['not_found']:warnings.append(f"{len(result['not_found'])} SN không có task")
        if result['truncated']:warnings.append(f"{len(result['truncated'])} SN vượt giới hạn 100 task; kết quả chưa đầy đủ")
        self.status.setText(' · '.join(warnings) if warnings else ('Không có đơn Picked khớp mã.' if not result['sns'] else 'Đã tìm xong. Chọn ô/cột rồi Ctrl+C để sao chép.'))
    def closeEvent(self,event):
        self.searcher.cancel();super().closeEvent(event)
    def reject(self):
        self.searcher.cancel();super().reject()
