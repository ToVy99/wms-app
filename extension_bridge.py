"""Opt-in Chrome extension transport; loopback only, authenticated native relay."""
import copy,json,os,queue,secrets,select,socket,sys,time
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QMessageBox
from native_link import HOST_NAME,EXTENSION_ID,MAX_FRAME,encode_frame,read_frame,state_dir

ASSETS={'manifest.json':'wms_bridge_manifest.json','background.js':'wms_bridge_background.js','content.js':'wms_bridge_content.js','popup.html':'wms_bridge_popup.html','popup.js':'wms_bridge_popup.js','icon.png':'wms_bridge_icon.png'}

def install_host():
    if os.name!='nt' or not getattr(sys,'frozen',False):
        raise RuntimeError('Thiết lập tiện ích bằng bản EXE Windows đã đóng gói.')
    import winreg
    dest=state_dir();dest.mkdir(parents=True,exist_ok=True)
    folder=dest/'extension';folder.mkdir(exist_ok=True)
    base=Path(__file__).resolve().parent
    for name,source in ASSETS.items(): (folder/name).write_bytes((base/source).read_bytes())
    manifest={'name':HOST_NAME,'description':'IntraCity WMS bridge','path':sys.executable,'type':'stdio','allowed_origins':['chrome-extension://'+EXTENSION_ID+'/']}
    path=dest/'native-host.json';path.write_text(json.dumps(manifest),encoding='utf-8')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Google\Chrome\NativeMessagingHosts'+'\\'+HOST_NAME) as key:
        winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(path))
    return folder

class ExtensionWorker(QThread):
    result=Signal(str,str);state=Signal(bool,str);skuProgress=Signal(str,str)
    def __init__(self,folder=None):
        super().__init__();self.folder=Path(folder) if folder else state_dir()
        self.commands=queue.Queue();self.cancelled=set();self.control=queue.Queue()
        self.network_requests=0;self.token=secrets.token_hex(32)
    def enqueue(self,rid,msg):self.commands.put((rid,copy.deepcopy(msg)))
    def cancel_sku(self,rid):self.control.put(rid)
    def cancel_all_sku(self):self.control.put('*')
    def run(self):
        listener=socket.socket();conn=None;active=None;ready=False;buffer=b'';chunks=None;size=0;last=time.monotonic();seq=0
        pending_path=self.folder/'endpoint.json'
        try:
            listener.bind(('127.0.0.1',0));listener.listen(2);listener.setblocking(False)
            self.folder.mkdir(parents=True,exist_ok=True)
            pending_path.write_text(json.dumps({'port':listener.getsockname()[1],'token':self.token}),encoding='utf-8')
            try:pending_path.chmod(0o600)
            except OSError:pass
            self.state.emit(False,'Mở tiện ích IntraCity trên Chrome, chọn tab WMS và bấm Kết nối.')
            while not self.isInterruptionRequested():
                if conn is None:
                    if not select.select([listener],[],[],.1)[0]:continue
                    candidate,_=listener.accept();candidate.settimeout(3)
                    try:
                        hello=read_frame(candidate.recv)
                        if hello.get('kind')!='hello' or hello.get('extension')!=EXTENSION_ID or not secrets.compare_digest(str(hello.get('token','')),self.token):raise ValueError('Unauthorized relay')
                        candidate.settimeout(5);conn=candidate;buffer=b'';last=time.monotonic()
                        conn.sendall(encode_frame({'kind':'ready'}))
                    except (OSError,ValueError,EOFError):candidate.close()
                    continue
                try:
                    while not self.control.empty():
                        rid=self.control.get_nowait()
                        if rid=='*':
                            if active and active[1].get('type')=='WMS_SKU_SEARCH':rid=active[0]
                            else:continue
                        self.cancelled.add(rid)
                        conn.sendall(encode_frame({'kind':'cancel','id':rid}))
                    if active is None and ready:
                        try:
                            rid,msg=self.commands.get_nowait()
                            if rid in self.cancelled:
                                self.cancelled.discard(rid);self.result.emit(rid,json.dumps({'success':False,'cancelled':True}));continue
                            active=(rid,msg,time.monotonic());chunks=None;size=0;seq=0
                            conn.sendall(encode_frame({'kind':'request','id':rid,'message':msg}))
                        except queue.Empty:pass
                    if time.monotonic()-last>65 or (active and time.monotonic()-active[2]>900):raise OSError('Tiện ích không phản hồi; hãy kết nối lại.')
                    if not select.select([conn],[],[],.05)[0]:continue
                    data=conn.recv(65536)
                    if not data:raise EOFError()
                    buffer+=data
                    while len(buffer)>=4:
                        n=int.from_bytes(buffer[:4],'little')
                        if n>MAX_FRAME:raise ValueError('Bridge frame too large')
                        if len(buffer)<n+4:break
                        message=json.loads(buffer[4:n+4]);buffer=buffer[n+4:];last=time.monotonic()
                        kind=message.get('kind');rid=message.get('id')
                        if kind=='state':
                            ready=bool(message.get('connected'));self.state.emit(ready,str(message.get('text','Tiện ích Chrome'))[:500])
                            if not ready and active:raise OSError('Tab WMS đã ngắt kết nối. Hãy chọn tab rồi kết nối lại.')
                        elif kind=='progress' and active and rid==active[0]:self.skuProgress.emit(rid,str(message.get('text',''))[:500])
                        elif kind=='result_start' and active and rid==active[0]:chunks=[];size=0;seq=0
                        elif kind=='result_chunk' and active and rid==active[0]:
                            if chunks is None or message.get('seq')!=seq:raise ValueError('Mất đoạn dữ liệu từ tiện ích')
                            value=message.get('text')
                            if not isinstance(value,str):raise ValueError('Dữ liệu tiện ích không hợp lệ')
                            size+=len(value.encode('utf-8'));seq+=1
                            if size>512*1024*1024:raise ValueError('Report vượt 512 MB; đã dừng')
                            chunks.append(value)
                        elif kind=='result_end' and active and rid==active[0]:
                            if chunks is None or message.get('count')!=seq:raise ValueError('Report chưa nhận đủ')
                            raw=''.join(chunks);parsed=json.loads(raw)
                            if not isinstance(parsed,dict):raise ValueError('Phản hồi không hợp lệ')
                            self.network_requests+=int(parsed.get('requests',1))
                            self.cancelled.discard(rid);active=None;chunks=None
                            self.result.emit(rid,raw)
                except (OSError,EOFError,ValueError,TypeError,KeyError) as exc:
                    if active:self.result.emit(active[0],json.dumps({'success':False,'error':str(exc) or 'Tiện ích đã ngắt kết nối.'}))
                    active=None;chunks=None;ready=False;conn.close();conn=None
                    self.state.emit(False,'Tiện ích Chrome đã ngắt · Kết nối lại hoặc chọn mở Chrome riêng.')
                    self.drain('Tiện ích đã ngắt kết nối.')
        except Exception as exc:self.state.emit(False,'Không mở được cầu nối: '+str(exc))
        finally:
            if conn:
                try:conn.sendall(encode_frame({'kind':'disconnect'}))
                except OSError:pass
                conn.close()
            listener.close()
            if active:self.result.emit(active[0],json.dumps({'success':False,'error':'Đã đóng cầu nối.'}))
            self.drain('Đã đóng cầu nối.')
            try:
                if json.loads(pending_path.read_text(encoding='utf-8')).get('token')==self.token:pending_path.unlink()
            except (OSError,ValueError):pass
    def drain(self,error):
        while not self.commands.empty():
            rid,_=self.commands.get_nowait();self.result.emit(rid,json.dumps({'success':False,'error':error}))

def show_extension_setup(window,bridge):
    try:
        folder=install_host()
        bridge.connect_extension()
    except Exception as exc:
        QMessageBox.warning(window,'Kết nối tiện ích',str(exc));return
    dialog=QDialog(window);dialog.setWindowTitle('Dùng Chrome đang mở · IntraCity 3.4');dialog.resize(540,300)
    layout=QVBoxLayout(dialog)
    label=QLabel('Thiết lập lần đầu:\n1. Mở chrome://extensions trong Chrome → bật Chế độ dành cho nhà phát triển.\n2. Chọn Tải tiện ích đã giải nén → chọn thư mục bên dưới.\n3. Mở tiện ích IntraCity, chọn đúng tab WMS / kho rồi bấm Kết nối.\n\nNhững lần sau: chọn cách kết nối này trong app, rồi bấm Kết nối trong tiện ích.\nKhông cần đóng Chrome hoặc đăng nhập lại tab WMS.');label.setWordWrap(True);layout.addWidget(label)
    location=QLabel(str(folder));location.setWordWrap(True);location.setTextInteractionFlags(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.TextSelectableByMouse);layout.addWidget(location)
    button=QPushButton('Mở thư mục tiện ích');button.clicked.connect(lambda:os.startfile(folder));layout.addWidget(button)
    state=QLabel('Đang chờ tiện ích kết nối…');state.setWordWrap(True);layout.addWidget(state)
    def update(connected,text):state.setText(text)
    bridge.sessionChanged.connect(update)
    dialog.finished.connect(lambda _:bridge.sessionChanged.disconnect(update))
    close=QPushButton('Đóng');close.clicked.connect(dialog.accept);layout.addWidget(close)
    if hasattr(window,'theme_controller'):window.theme_controller.apply()
    dialog.exec()
