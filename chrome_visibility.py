"""Keep the WMS browser running while its own window is hidden."""
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

def chrome_window_handles(profile_dir):
    if sys.platform != 'win32':
        return []
    import psutil
    target = os.path.normcase(os.path.abspath(str(profile_dir)))
    pids = set()
    for process in psutil.process_iter(['pid','name','cmdline']):
        try:
            if (process.info['name'] or '').lower() != 'chrome.exe':
                continue
            argv = process.info['cmdline'] or []
            for i,arg in enumerate(argv):
                if arg.startswith('--user-data-dir='):
                    directory = arg.partition('=')[2]
                elif arg == '--user-data-dir' and i+1<len(argv):
                    directory = argv[i+1]
                else:
                    continue
                if os.path.normcase(os.path.abspath(directory.strip('"'))) == target:
                    pids.add(process.info['pid'])
                    break
        except (psutil.Error, ValueError, OSError):
            continue
    if not pids:
        return []
    result=[]
    user32=ctypes.windll.user32
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback
    def visit(hwnd, _):
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value in pids:
            name=ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd,name,128)
            if name.value.startswith('Chrome_WidgetWin_'):
                result.append(hwnd)
        return True
    user32.EnumWindows(visit,0)
    return result

def set_chrome_visible(profile_dir, visible):
    if sys.platform!='win32':
        return False
    handles=chrome_window_handles(profile_dir)
    if not handles:
        return False
    for hwnd in handles:
        ctypes.windll.user32.ShowWindowAsync(hwnd,9 if visible else 0)
    return True
