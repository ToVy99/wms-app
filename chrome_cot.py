"""Native COT controls with web v1.4 logic and Chrome-owned WMS transport.

All Playwright objects live on one worker thread. No cookies are copied into
Python requests, and no browser/API operation starts at application startup.
"""
import json
import os
import queue
import time
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer, QDate, Qt
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QDialog, QDialogButtonBox, QTimeEdit, QLineEdit, QTextEdit, QMessageBox, QGridLayout)
from playwright.sync_api import sync_playwright
from cot_logic import DEFAULT_CONFIG, time_range, export_body, choose_job, parse_report, status_name, progress, URL_EXPORT_LIST, URL_EXPORT, URL_ORDER
import base64
import copy
from collections import Counter

ORIGIN = 'https://wms.ssc.shopee.vn'
API_PATHS = {
    '/api/v2/apps/process/outbound/salesorder/search_order',
    '/api/v2/apps/basic/reportcenter/create_export_task',
    '/api/v2/apps/basic/reportcenter/search_export_task',
}


def validate_request(msg):
    kind = msg.get('type')
    parts = urlsplit(str(msg.get('url', '')))
    if parts.scheme != 'https' or parts.netloc != 'wms.ssc.shopee.vn':
        raise ValueError('Chỉ gọi WMS trong phiên Chrome.')
    if kind == 'WMS_DOWNLOAD':
        if not parts.path.startswith('/oss_downloads_v2/'):
            raise ValueError('Link tải không phải report WMS.')
    elif kind in ('WMS_GET', 'WMS_POST'):
        if parts.path not in API_PATHS:
            raise ValueError('API không thuộc luồng COT v1.4.')
        if kind == 'WMS_POST' and not isinstance(msg.get('body'), dict):
            raise ValueError('Nội dung yêu cầu không hợp lệ.')
    else:
        raise ValueError('Yêu cầu không được hỗ trợ.')


# Executed inside the signed-in WMS tab, not in Qt's local renderer.
FETCH_JS = r'''async ({url, method, body, binary}) => {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), binary ? 90000 : 25000);
  try {
    const opt = {method, credentials:'include', signal:ctrl.signal};
    if (!binary) opt.headers = {'Content-Type':'application/json;charset=UTF-8','X-CCTV-Tenant-Id':'WMS'};
    if (method === 'POST') opt.body = JSON.stringify(body);
    const resp = await fetch(url, opt);
    if (!resp.ok) throw new Error('HTTP '+resp.status+(resp.status===429?' · WMS giới hạn yêu cầu; đã dừng.':''));
    if (binary) {
      const bytes = new Uint8Array(await resp.arrayBuffer());
      let text='';
      for(let i=0;i<bytes.length;i+=32768) text+=String.fromCharCode(...bytes.subarray(i,i+32768));
      return {success:true,data:btoa(text)};
    }
    let res;
    try {res=await resp.json()} catch {return {success:false,error:'WMS không trả JSON. Hãy kiểm tra đăng nhập trong Chrome.',auth:true}}
    if(res && res.retcode===0) return {success:true,data:res.data??{}};
    return {success:false,error:res?.message||'Lỗi WMS',auth:res?.retcode===10001};
  } catch(e) {return {success:false,error:e.name==='AbortError'?'WMS phản hồi quá lâu; đã dừng, không tự thử lại.':e.message}}
  finally {clearTimeout(timer)}
}'''


class ChromeWorker(QThread):
    result = Signal(str, str)
    state = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.commands = queue.Queue()
        self.network_requests = 0

    def enqueue(self, request_id, msg):
        self.commands.put((request_id, msg))

    @staticmethod
    def find_page(context):
        # The user may navigate to another warehouse or open a new WMS tab.
        for page in reversed(context.pages):
            if page.is_closed():
                continue
            p = urlsplit(page.url)
            if p.scheme == 'https' and p.netloc == 'wms.ssc.shopee.vn':
                return page
        raise RuntimeError('Không còn tab WMS. Bấm Đăng nhập WMS để mở lại Chrome.')

    def run(self):
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='chrome', headless=False, timeout=15000)
                try:
                    context = browser.new_context()
                    page = context.new_page()
                    try:
                        page.goto(ORIGIN, wait_until='domcontentloaded', timeout=20000)
                    except Exception:
                        if not browser.is_connected():
                            raise RuntimeError('Chrome đã đóng.')
                    self.state.emit(True, 'Chrome đang mở · Đăng nhập và chọn kho, rồi bấm Tải dữ liệu.')
                    while not self.isInterruptionRequested() and browser.is_connected():
                        try:
                            request_id, msg = self.commands.get_nowait()
                        except queue.Empty:
                            try:
                                pages = [p for p in context.pages if not p.is_closed()]
                                if not pages:
                                    break
                                pages[-1].wait_for_timeout(100)
                            except Exception:
                                if not browser.is_connected():
                                    break
                            continue
                        try:
                            validate_request(msg)
                            target = self.find_page(context)
                            # Refuse a login page; the user completes login themselves.
                            if any(x in urlsplit(target.url).path.lower().split('/') for x in ('login','signin','sso','auth')):
                                raise RuntimeError('Hãy đăng nhập và chọn kho trong Chrome trước khi tải COT.')
                            self.network_requests += 1
                            response = target.evaluate(FETCH_JS, {
                                'url': msg['url'],
                                'method': 'POST' if msg['type'] == 'WMS_POST' else 'GET',
                                'body': msg.get('body'), 'binary': msg['type'] == 'WMS_DOWNLOAD',
                            })
                        except Exception as exc:
                            response = {'success':False,'error':str(exc)}
                        self.result.emit(request_id, json.dumps(response, ensure_ascii=False))
                finally:
                    browser.close()
        except Exception as exc:
            self.state.emit(False, f'Không mở/giữ được Chrome: {exc}')
        finally:
            while True:
                try:
                    request_id, _ = self.commands.get_nowait()
                except queue.Empty:
                    break
                self.result.emit(request_id, json.dumps({'success':False,'error':'Phiên Chrome đã đóng.'}))
            self.state.emit(False, 'Chrome đã đóng · Bấm Đăng nhập WMS để kết nối lại.')


class NativeBridge(QObject):
    completed = Signal(str, str)
    sessionChanged = Signal(bool, str)

    def __init__(self, config, save_config, parent=None):
        super().__init__(parent)
        self.config = config
        self.save_config = save_config
        self.worker = None
        self.connected = False

    def connect_chrome(self):
        if self.worker and self.worker.isRunning():
            self.sessionChanged.emit(self.connected, 'Chrome đang mở · Bạn có thể đổi kho trực tiếp trong Chrome.')
            return
        self.worker = ChromeWorker()
        self.worker.result.connect(self.completed)
        self.worker.state.connect(self._state)
        self.worker.start()

    @Slot(bool, str)
    def _state(self, connected, message):
        self.connected = connected
        self.sessionChanged.emit(connected, message)

    @Slot(str, str)
    def request(self, request_id, raw):
        try:
            msg = json.loads(raw)
            kind = msg.get('type')
            if kind == 'STORAGE_GET':
                data = self.config.get('cot_web_v14', {})
                self.completed.emit(request_id, json.dumps({'success':True,'data':data}))
                return
            if kind == 'STORAGE_SET':
                self.config['cot_web_v14'] = msg['value']
                if not self.save_config(self.config):
                    raise RuntimeError('Không lưu được cài đặt COT.')
                self.completed.emit(request_id, '{"success":true}')
                return
            if kind == 'COPY':
                QApplication.clipboard().setText(str(msg.get('text', '')))
                self.completed.emit(request_id, '{"success":true}')
                return
            validate_request(msg)
            if not self.connected or not self.worker or not self.worker.isRunning():
                raise RuntimeError('Bấm Đăng nhập WMS, đăng nhập và chọn kho trong Chrome trước.')
            if self.worker.commands.qsize() >= 20:
                raise RuntimeError('Đang có tác vụ WMS; chờ tác vụ hiện tại hoàn tất.')
            self.worker.enqueue(request_id, msg)
        except Exception as exc:
            self.completed.emit(request_id, json.dumps({'success':False,'error':str(exc)}, ensure_ascii=False))

    def stop(self, timeout=1500):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            return self.worker.wait(timeout)
        return True

class ReportParser(QThread):
    ready = Signal(object)
    failed = Signal(str)
    def __init__(self, data, name, key, parent):
        super().__init__(parent)
        self.data,self.name,self.key = data,name,key
    def run(self):
        try: self.ready.emit(parse_report(self.data,self.name,self.key))
        except Exception as exc: self.failed.emit(str(exc))


class ChromeCotTab(QWidget):
    def __init__(self, config, save_config, parent=None):
        super().__init__(parent)
        self.bridge = NativeBridge(config, save_config, self)
        saved = config.get('cot_web_v14',{}).get('intracityConfigV11')
        self.config = copy.deepcopy(saved or DEFAULT_CONFIG)
        self.orders=[]; self.selected=set(); self.area_loaded=set()
        self.active_status=None; self.active_area=None; self.active_wave=None
        self.pending={}; self.counter=0; self.busy=False; self.parser=None
        self.bridge.completed.connect(self.completed)
        self.bridge.sessionChanged.connect(lambda _,text: self.message.setText(text))
        layout=QVBoxLayout(self); layout.setContentsMargins(8,8,8,8); layout.setSpacing(6)
        top=QHBoxLayout(); layout.addLayout(top)
        self.carrier=QComboBox()
        for k,c in self.config.items(): self.carrier.addItem(c['name'],k)
        self.date=QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.date.setDisplayFormat('dd/MM/yyyy')
        self.load=QPushButton('Tải dữ liệu'); self.load.clicked.connect(self.fetch_dataset)
        self.settings=QPushButton('Khung giờ'); self.settings.clicked.connect(self.open_settings)
        for w in (QLabel('Nhóm'),self.carrier,QLabel('Ngày'),self.date,self.load,self.settings): top.addWidget(w)
        top.addStretch()
        self.cot_row=QHBoxLayout(); layout.addLayout(self.cot_row); self.cot_buttons=[]; self.cot_id=None
        self.range_label=QLabel(); layout.addWidget(self.range_label)
        self.summary=QLabel('Tổng 0 đơn · Outbound 0 / 0 · 0.0%'); layout.addWidget(self.summary)
        self.status_row=QGridLayout(); layout.addLayout(self.status_row)
        filters=QHBoxLayout(); layout.addLayout(filters)
        self.area=QComboBox(); self.wave=QComboBox()
        filters.addWidget(QLabel('Area')); filters.addWidget(self.area); filters.addWidget(QLabel('Wave Type')); filters.addWidget(self.wave); filters.addStretch()
        self.area.currentIndexChanged.connect(self.filter_changed); self.wave.currentIndexChanged.connect(self.filter_changed)
        actions=QHBoxLayout(); layout.addLayout(actions)
        for label,fn in [('Chọn các đơn đang hiện',self.select_visible),('Bỏ chọn',self.clear_selection),('Copy OBVN',self.copy_obvn),('Picking ID / BSK',self.show_tasks)]:
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        self.visible_label=QLabel(); actions.addWidget(self.visible_label); actions.addStretch()
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(['Chọn','OBVN','Order SN','Trạng thái','Area','Create Time','Cut off Time'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0,45)
        for col,width in [(1,180),(2,190),(3,120),(4,80),(5,160)]: self.table.setColumnWidth(col,width)
        self.table.itemChanged.connect(self.check_changed); layout.addWidget(self.table,1)
        self.message=QLabel('Chọn COT và bấm Tải dữ liệu. Chưa gọi WMS.'); self.message.setWordWrap(True); layout.addWidget(self.message)
        self.carrier.currentIndexChanged.connect(self.fill_cots)
        self.date.dateChanged.connect(self.scope_changed)
        self.fill_cots()

    @staticmethod
    def empty_row(row):
        while row.count():
            item=row.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def fill_cots(self):
        self.empty_row(self.cot_row); self.cot_buttons=[]
        carrier=self.config[self.carrier.currentData()]
        self.cot_id=carrier['cots'][0]['id']
        for cot in carrier['cots']:
            suffix=' hôm trước → hôm nay' if carrier.get('previous') else (' (+1)' if cot['end']<=cot['start'] else '')
            b=QPushButton(f"{cot['name']} · {cot['start']}–{cot['end']}{suffix}"); b.setCheckable(True)
            b.clicked.connect(lambda _,cid=cot['id']: self.select_cot(cid))
            self.cot_row.addWidget(b); self.cot_buttons.append((cot['id'],b))
        self.cot_row.addStretch(); self.scope_changed()

    def select_cot(self,cid):
        if self.busy: return
        self.cot_id=cid; self.scope_changed()

    def current_range(self):
        key=self.carrier.currentData(); c=self.config[key]; cot=next(x for x in c['cots'] if x['id']==self.cot_id)
        beg,end=time_range(self.date.date().toString('yyyy-MM-dd'),c,cot)
        return key,c,beg,end

    def scope_changed(self,*_):
        for cid,b in self.cot_buttons: b.setChecked(cid==self.cot_id)
        _,c,beg,end=self.current_range()
        self.range_label.setText(f"{c['name']} · Create Time · {beg:%d/%m/%Y %H:%M} → {end:%d/%m/%Y %H:%M}")
        self.orders=[]; self.selected.clear(); self.area_loaded.clear(); self.active_status=None; self.active_area=self.active_wave=None
        self.render_all(); self.message.setText('Chọn COT và bấm Tải dữ liệu. Chưa gọi WMS.')

    def set_busy(self,busy):
        self.busy=busy
        for w in [self.load,self.carrier,self.date,self.settings,*[b for _,b in self.cot_buttons]]: w.setEnabled(not busy)
        for i in range(self.status_row.count()):
            w=self.status_row.itemAt(i).widget()
            if w: w.setEnabled(not busy)

    def request(self,msg,callback):
        self.counter+=1; rid=str(self.counter); self.pending[rid]=callback
        self.bridge.request(rid,json.dumps(msg))

    @Slot(str,str)
    def completed(self,rid,raw):
        callback=self.pending.pop(rid,None)
        if callback:
            try:
                response=json.loads(raw)
                if not response.get('success'): raise RuntimeError(response.get('error','Lỗi WMS'))
                callback(response.get('data'))
            except Exception as exc: self.fail(str(exc))

    def fail(self,text):
        self.message.setText('Lỗi: '+text); self.set_busy(False)

    def fetch_dataset(self):
        if self.busy: return
        if not self.bridge.connected:
            self.message.setText('Bấm Đăng nhập WMS, đăng nhập và chọn kho trong Chrome trước.'); return
        self.scope_changed(); self.set_busy(True); self.message.setText('Đang tạo Export WMS…')
        self.scope=self.current_range(); self.poll_count=0
        self.request(dict(type='WMS_GET',url=URL_EXPORT_LIST),self.got_old_jobs)

    def got_old_jobs(self,data):
        self.old_ids={str(j.get('task_id')) for j in (data or {}).get('list',[])}
        self.started=int(time.time())
        self.request(dict(type='WMS_POST',url=URL_EXPORT,body=export_body(self.scope[2],self.scope[3])),self.created)

    def created(self,data):
        self.task_id=(data or {}).get('task_id') or (data or {}).get('export_task_id')
        self.poll_export()

    def poll_export(self):
        if self.poll_count>=60: self.fail('Export quá 3 phút chưa hoàn tất. Đã dừng kiểm tra.'); return
        self.poll_count+=1
        self.request(dict(type='WMS_GET',url=URL_EXPORT_LIST),self.got_job)

    def got_job(self,data):
        job=choose_job((data or {}).get('list',[]),self.old_ids,self.started,self.task_id)
        if job:
            self.message.setText(f"Đang tạo Excel… {job.get('processed_percentage',0)}% · {job.get('task_id')}")
            if int(job.get('task_status') or 0)==2 and job.get('download_link'):
                self.report_name=str(job.get('export_file_name') or 'report.xlsx')
                self.message.setText('Export xong · đang tải '+self.report_name)
                self.request(dict(type='WMS_DOWNLOAD',url=job['download_link']),self.got_bytes); return
        QTimer.singleShot(3000,self.poll_export)

    def got_bytes(self,data):
        self.message.setText('Đang đọc Excel và gom theo OBVN…')
        self.parser=ReportParser(base64.b64decode(data,validate=True),self.report_name,self.scope[0],self)
        self.parser.ready.connect(self.parsed); self.parser.failed.connect(self.fail); self.parser.start()

    def parsed(self,data):
        self.orders=data['orders']; self.render_all(); self.set_busy(False)
        self.message.setText(f"✓ {self.report_name} · {data['rawRows']} dòng · lọc {data['filteredRows']} dòng · {len(self.orders)} đơn hợp lệ (đã loại Cancel)")

    def status_orders(self):
        return [o for o in self.orders if self.active_status is None or str(o['order_status'])==str(self.active_status)]

    def visible(self):
        return [o for o in self.status_orders() if (self.active_area is None or (o['area'] or '-')==self.active_area) and (self.active_wave is None or (o['wave_type'] or '-')==self.active_wave)]

    def render_all(self):
        done,total,pct=progress(self.orders); self.summary.setText(f'Tổng {total} đơn · Outbound {done} / {total} · {pct:.1f}%')
        self.empty_row(self.status_row)
        counts=Counter(o['order_status'] for o in self.orders)
        for ix,(code,label,count) in enumerate([(None,'Tổng',total)]+[(s,status_name(s),n) for s,n in counts.most_common()]):
            b=QPushButton(f'{label} ({count})'); b.setCheckable(True); b.setChecked(self.active_status==code); b.setEnabled(not self.busy)
            b.clicked.connect(lambda _,s=code: self.select_status(s)); self.status_row.addWidget(b,ix//8,ix%8)
        src=self.status_orders()
        for combo,field,active in [(self.area,'area',self.active_area),(self.wave,'wave_type',self.active_wave)]:
            combo.blockSignals(True); combo.clear(); combo.addItem(f'Tất cả ({len(src)})',None)
            for value,n in Counter((o[field] or '-') for o in src).most_common():
                pct=n/len(src)*100 if src else 0
                combo.addItem(f'{value} ({n})'+(f' · {pct:.2f}%' if field=='wave_type' else ''),value)
            idx=combo.findData(active); combo.setCurrentIndex(max(0,idx)); combo.blockSignals(False)
        self.render_table()

    def select_status(self,code):
        if self.busy: return
        self.active_status=code; self.active_area=self.active_wave=None; self.render_all()
        if code is not None and str(code) not in self.area_loaded and any(o['area']=='-' for o in self.status_orders()):
            self.set_busy(True); self.area_map={}; self.area_page=1; self.area_code=code
            _,c,beg,end=self.current_range()
            self.area_body=dict(order_status_list=str(code),beg_ctime=int(beg.timestamp()),end_ctime=int(end.timestamp()),pageno=1,count=200,is_get_total=1)
            if c['channels']: self.area_body['channel_id_list']=c['channels']
            self.message.setText('Đang nạp Area · '+status_name(code)); self.fetch_area_page()

    def fetch_area_page(self):
        body=dict(self.area_body,pageno=self.area_page,is_get_total=1 if self.area_page==1 else 0)
        self.request(dict(type='WMS_POST',url=URL_ORDER,body=body),self.got_area)

    def got_area(self,data):
        if self.area_page==1:
            self.area_total=int(data.get('total') or 0); self.area_pages=min(10,(self.area_total+199)//200)
        for o in data.get('list',[]):
            self.area_map[o.get('order_number')]=str(o.get('pre_hit_zone_list') or '-') if not isinstance(o.get('pre_hit_zone_list'),list) else ','.join(map(str,o['pre_hit_zone_list'])) or '-'
        if self.area_page<self.area_pages:
            self.area_page+=1; QTimer.singleShot(1000,self.fetch_area_page); return
        for o in self.orders:
            if str(o['order_status'])==str(self.area_code) and o['order_number'] in self.area_map: o['area']=self.area_map[o['order_number']]
        self.area_loaded.add(str(self.area_code)); self.set_busy(False); self.render_all()
        self.message.setText('Đã nạp Area · '+status_name(self.area_code)+(f' · {self.area_total} đơn, WMS chỉ cho đọc Area tối đa 2000' if self.area_total>2000 else ''))

    def filter_changed(self,*_):
        self.active_area=self.area.currentData(); self.active_wave=self.wave.currentData(); self.render_table()

    def render_table(self):
        self.table.blockSignals(True); self.table.setUpdatesEnabled(False)
        rows=self.visible(); self.table.setRowCount(len(rows))
        for i,o in enumerate(rows):
            cb=QTableWidgetItem(); cb.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
            cb.setData(Qt.ItemDataRole.UserRole,o['order_number']); cb.setCheckState(Qt.CheckState.Checked if o['order_number'] in self.selected else Qt.CheckState.Unchecked); self.table.setItem(i,0,cb)
            for j,value in enumerate([o['order_number'],', '.join(sorted(o['sns'])),status_name(o['order_status']),o['area'],o['ctime_text'],o['cutoff_text']],1): self.table.setItem(i,j,QTableWidgetItem(str(value)))
        self.table.setUpdatesEnabled(True); self.table.blockSignals(False)
        self.visible_label.setText(f'Hiện {len(rows)} · Chọn {len(self.selected)}')

    def check_changed(self,item):
        if item.column()!=0:return
        ob=item.data(Qt.ItemDataRole.UserRole)
        if item.checkState()==Qt.CheckState.Checked:self.selected.add(ob)
        else:self.selected.discard(ob)
        self.visible_label.setText(f'Hiện {self.table.rowCount()} · Chọn {len(self.selected)}')

    def select_visible(self):
        self.selected.update(o['order_number'] for o in self.visible()); self.render_table()
    def clear_selection(self): self.selected.clear(); self.render_table()
    def target_orders(self):
        return [o for o in self.orders if o['order_number'] in self.selected] or self.visible()
    def copy_obvn(self): QApplication.clipboard().setText('\n'.join(o['order_number'] for o in self.target_orders()))

    def show_tasks(self):
        tasks={}
        for o in self.target_orders():
            for pick in o['picking']:
                t=tasks.setdefault(pick,dict(bsks=set(),sns=set())); t['bsks'].update(o['bsks']); t['sns'].update(o['sns'])
        dialog=QDialog(self); dialog.setWindowTitle(f'{len(tasks)} Picking ID · từ Excel'); dialog.resize(650,450)
        layout=QVBoxLayout(dialog); text=QTextEdit(); text.setReadOnly(True)
        text.setPlainText('\n\n'.join(f"Picking ID: {p}\nBSK: {', '.join(sorted(t['bsks'])) or '-'}\nOrder SN: {', '.join(sorted(t['sns']))}" for p,t in tasks.items()) or 'Các đơn này chưa có Picking ID trong Excel.')
        layout.addWidget(text); row=QHBoxLayout(); layout.addLayout(row)
        for label,value in [('Copy Picking ID','\n'.join(tasks)),('Copy BSK','\n'.join(sorted({b for t in tasks.values() for b in t['bsks']})))]:
            btn=QPushButton(label); btn.clicked.connect(lambda _,v=value:QApplication.clipboard().setText(v)); row.addWidget(btn)
        close=QPushButton('Đóng'); close.clicked.connect(dialog.accept); row.addWidget(close); dialog.exec()

    def open_settings(self):
        dialog=QDialog(self); dialog.setWindowTitle('Khung giờ COT'); layout=QVBoxLayout(dialog); entries=[]
        for key,c in self.config.items():
            layout.addWidget(QLabel(c['name']))
            for cot in c['cots']:
                row=QHBoxLayout(); layout.addLayout(row)
                nm=QLineEdit(cot['name']); a=QTimeEdit(); b=QTimeEdit()
                from PySide6.QtCore import QTime
                for w,hm in [(a,cot['start']),(b,cot['end'])]: w.setDisplayFormat('HH:mm'); w.setTime(QTime.fromString(hm,'HH:mm'))
                for w in (nm,a,b): row.addWidget(w)
                entries.append((key,cot['id'],nm,a,b))
        reset=QPushButton('Khôi phục khung giờ mặc định'); layout.addWidget(reset)
        def reset_values():
            for key,cid,nm,a,b in entries:
                cot=next(x for x in DEFAULT_CONFIG[key]['cots'] if x['id']==cid)
                nm.setText(cot['name']); a.setTime(QTime.fromString(cot['start'],'HH:mm')); b.setTime(QTime.fromString(cot['end'],'HH:mm'))
        reset.clicked.connect(reset_values)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        updated=copy.deepcopy(self.config)
        for key,cid,nm,a,b in entries:
            cot=next(x for x in updated[key]['cots'] if x['id']==cid)
            cot.update(name=nm.text().strip() or cot['name'],start=a.time().toString('HH:mm'),end=b.time().toString('HH:mm'))
        old=self.bridge.config.get('cot_web_v14',{})
        self.bridge.config['cot_web_v14']=dict(old,intracityConfigV11=updated)
        if not self.bridge.save_config(self.bridge.config):
            self.bridge.config['cot_web_v14']=old; QMessageBox.warning(self,'COT','Không lưu được cài đặt.');return
        self.config=updated; self.fill_cots()
