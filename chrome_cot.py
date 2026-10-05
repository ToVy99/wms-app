"""Web v1.4 renderer with a Chrome-owned, same-origin WMS transport.

All Playwright objects live on one worker thread. No cookies are copied into
Python requests, and no browser/API operation starts at application startup.
"""
import json
import os
import queue
import time
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QThread, Signal, Slot, QUrl, QTemporaryDir
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from playwright.sync_api import sync_playwright
from cot_web_assets import COT_WEB_FILES

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


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, main_frame):
        return url.scheme() in ('file','qrc','about')

    def javaScriptAlert(self, origin, text):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self.view_parent, 'COT', text)


class ChromeCotTab(QWidget):
    def __init__(self, config, save_config, parent=None):
        super().__init__(parent)
        self.bridge = NativeBridge(config, save_config, self)
        self.view = QWebEngineView(self)
        page = LocalPage(self.view)
        page.view_parent = self
        self.view.setPage(page)
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject('native', self.bridge)
        self.view.page().setWebChannel(self.channel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.view)
        self.assets_dir = QTemporaryDir()
        if not self.assets_dir.isValid():
            raise RuntimeError('Không tạo được thư mục tạm cho tab COT.')
        for name, content in COT_WEB_FILES.items():
            (Path(self.assets_dir.path()) / name).write_text(content, encoding='utf-8')
        self.view.load(QUrl.fromLocalFile(str(Path(self.assets_dir.path()) / 'dashboard.html')))
