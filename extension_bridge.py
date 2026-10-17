"""Opt-in Chrome extension transport; loopback only, authenticated native relay."""
import copy,json,os,queue,secrets,select,socket,sys,time,tempfile,zipfile
from pathlib import Path
from PySide6.QtCore import QThread,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QMessageBox,QFileDialog
from native_link import HOST_NAME,EXTENSION_ID,MAX_FRAME,encode_frame,read_frame,state_dir

ASSETS={'manifest.json':'wms_bridge_manifest.json','background.js':'wms_bridge_background.js','content.js':'wms_bridge_content.js','popup.html':'wms_bridge_popup.html','popup.js':'wms_bridge_popup.js','icon.png':'wms_bridge_icon.png'}

def save_extension_zip(destination):
    destination=Path(destination);base=Path(__file__).resolve().parent
    fd,temp=tempfile.mkstemp(prefix='intracity-extension-',suffix='.zip',dir=destination.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,source in ASSETS.items():archive.write(base/source,'IntraCity_Chrome_Extension/'+name)
            archive.writestr('HUONG_DAN.txt','INTRACITY 3.4\n1. Trong app: Đăng nhập WMS > Dùng Chrome đang mở qua tiện ích.\n2. Giải nén ZIP. Mở chrome://extensions, bật Chế độ dành cho nhà phát triển.\n3. Chọn Tải tiện ích đã giải nén, chọn thư mục IntraCity_Chrome_Extension có manifest.json.\n4. Mở tiện ích, chọn tab WMS đã đăng nhập đúng kho và bấm Kết nối.\nNếu đã cài: cập nhật đúng thư mục tiện ích, rồi bấm Tải lại trong chrome://extensions.\n')
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.unlink(temp)

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
    def disconnect_session(self):self.control.put(None)
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
                while not self.control.empty():
                    rid=self.control.get_nowait()
                    if rid is None:
                        if conn:
                            try:conn.sendall(encode_frame({'kind':'disconnect'}))
                            except OSError:pass
                            conn.close();conn=None
                        ready=False;buffer=b'';chunks=None;self.cancelled.clear()
                        self.state.emit(False,'Đã ngắt kết nối tiện ích Chrome.')
                        if active:self.result.emit(active[0],json.dumps({'success':False,'error':'Đã ngắt kết nối tiện ích Chrome.'}))
                        active=None;self.drain('Đã ngắt kết nối tiện ích Chrome.')
                        continue
                    if rid=='*':
                        if active and active[1].get('type')=='WMS_SKU_SEARCH':rid=active[0]
                        else:continue
                    self.cancelled.add(rid)
                    if conn:
                        try:conn.sendall(encode_frame({'kind':'cancel','id':rid}))
                        except OSError:pass
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

class ExtensionSetupDialog(QDialog):
    def __init__(self,window,bridge,folder):
        super().__init__(window);self.bridge=bridge
        self.setWindowTitle('Dùng Chrome đang mở · IntraCity 3.4');self.resize(580,340)
        layout=QVBoxLayout(self)
        label=QLabel('Thiết lập lần đầu:\n1. Mở chrome://extensions → bật Chế độ dành cho nhà phát triển.\n2. Chọn Tải tiện ích đã giải nén → chọn thư mục bên dưới.\n3. Mở tiện ích IntraCity, chọn đúng tab WMS / kho rồi bấm Kết nối.\n\nApp đã chứa sẵn tiện ích. Có thể lưu ZIP để mang sang máy khác.\nSau khi cập nhật app: bấm Tải lại tiện ích trong chrome://extensions.');label.setWordWrap(True);layout.addWidget(label)
        location=QLabel(str(folder));location.setWordWrap(True);location.setTextInteractionFlags(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.TextSelectableByMouse);layout.addWidget(location)
        buttons=QHBoxLayout();layout.addLayout(buttons)
        button=QPushButton('Mở thư mục tiện ích');button.clicked.connect(lambda:os.startfile(folder));buttons.addWidget(button)
        self.save_button=QPushButton('Lưu tiện ích (.zip)');self.save_button.clicked.connect(self.save_zip);buttons.addWidget(self.save_button)
        self.state_label=QLabel();self.state_label.setWordWrap(True);layout.addWidget(self.state_label)
        self.disconnect_button=QPushButton('Ngắt kết nối');self.disconnect_button.clicked.connect(bridge.disconnect_extension);layout.addWidget(self.disconnect_button)
        bridge.sessionChanged.connect(self.update_state)
        self.finished.connect(lambda _:bridge.sessionChanged.disconnect(self.update_state))
        self.update_state(bridge.connected,bridge.session_message)
        close=QPushButton('Đóng');close.clicked.connect(self.accept);layout.addWidget(close)
    def update_state(self,connected,text):
        self.state_label.setText(('Đã kết nối · ' if connected else '')+text)
    def save_zip(self):
        path,_=QFileDialog.getSaveFileName(self,'Lưu tiện ích Chrome','IntraCity_3.4_Chrome_Extension.zip','ZIP (*.zip)')
        if not path:return
        if not path.lower().endswith('.zip'):path+='.zip'
        try:
            save_extension_zip(path)
            QMessageBox.information(self,'Đã lưu tiện ích','Đã lưu:\n'+path+'\n\nGiải nén rồi chọn thư mục có manifest.json khi cài trong Chrome.')
        except Exception as exc:QMessageBox.warning(self,'Không lưu được tiện ích',str(exc))

def show_extension_setup(window,bridge):
    try:
        folder=install_host()
        bridge.connect_extension()
    except Exception as exc:
        QMessageBox.warning(window,'Kết nối tiện ích',str(exc));return
    dialog=ExtensionSetupDialog(window,bridge,folder)
    if hasattr(window,'theme_controller'):window.theme_controller.apply()
    dialog.exec()
