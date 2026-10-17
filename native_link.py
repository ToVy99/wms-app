"""Native Messaging relay. No WMS credentials or HTTP requests enter this module."""
import json, os, socket, struct, sys, threading
from pathlib import Path
HOST_NAME='vn.intracity.wms_bridge'
EXTENSION_ID='fkfapobeolpmccgpboplmlfoffddoipd'
MAX_FRAME=1024*1024

def state_dir():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home())/'IntraCity'/'ChromeBridge'

def encode_frame(value):
    data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(data)>MAX_FRAME:raise ValueError('Bridge message too large')
    return struct.pack('<I',len(data))+data

def read_exact(reader,n):
    parts=[]
    while n:
        data=reader(n)
        if not data:raise EOFError()
        parts.append(data);n-=len(data)
    return b''.join(parts)

def read_frame(reader):
    n=struct.unpack('<I',read_exact(reader,4))[0]
    if n>MAX_FRAME:raise ValueError('Bridge message too large')
    result=json.loads(read_exact(reader,n))
    if not isinstance(result,dict):raise ValueError('Invalid bridge message')
    return result

def native_streams():
    if os.name!='nt':return sys.stdin.buffer.read,sys.stdout.buffer.write,sys.stdout.buffer.flush
    # PyInstaller --windowed has no sys.stdin/stdout, but Chrome provides pipe handles.
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetStdHandle.argtypes=[wintypes.DWORD];kernel.GetStdHandle.restype=wintypes.HANDLE
    kernel.ReadFile.argtypes=[wintypes.HANDLE,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
    kernel.WriteFile.argtypes=[wintypes.HANDLE,wintypes.LPCVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),wintypes.LPVOID]
    inp=kernel.GetStdHandle(-10 & 0xffffffff);out=kernel.GetStdHandle(-11 & 0xffffffff)
    def read(n):
        buf=ctypes.create_string_buffer(n);count=wintypes.DWORD()
        if not kernel.ReadFile(inp,buf,n,ctypes.byref(count),None):return b''
        return buf.raw[:count.value]
    def write(data):
        while data:
            count=wintypes.DWORD();buf=ctypes.create_string_buffer(data)
            if not kernel.WriteFile(out,buf,len(data),ctypes.byref(count),None) or not count.value:raise EOFError()
            data=data[count.value:]
    return read,write,lambda:None

def relay(origin):
    if origin!='chrome-extension://'+EXTENSION_ID+'/':return 2
    read,write,flush=native_streams()
    try:
        info=json.loads((state_dir()/'endpoint.json').read_text(encoding='utf-8'))
        sock=socket.create_connection(('127.0.0.1',int(info['port'])),timeout=4);sock.settimeout(None)
        sock.sendall(encode_frame({'kind':'hello','token':info['token'],'extension':EXTENSION_ID}))
        def inbound():
            try:
                while True:write(encode_frame(read_frame(sock.recv)));flush()
            except (OSError,EOFError,ValueError):
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                # Chrome owns this relay; exiting closes both native pipes.
                os._exit(0)
        threading.Thread(target=inbound,daemon=True).start()
        try:
            while True:sock.sendall(encode_frame(read_frame(read)))
        finally:sock.close()
    except (OSError,EOFError,ValueError,KeyError):return 1
    return 0

if __name__=='__main__':
    raise SystemExit(relay(sys.argv[1] if len(sys.argv)>1 else ''))
