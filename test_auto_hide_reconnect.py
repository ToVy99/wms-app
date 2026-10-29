"""Offline tests of login delay, safe auto-hide, and explicit reconnect."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from chrome_cot import ChromeWorker, ChromeCotTab, NativeBridge, AUTH_CHECK_JS
from cot_logic import URL_EXPORT_LIST
from sku_task_finder import TaskSearch

class FakeWorker(QObject):
    result=Signal(str,str)
    state=Signal(bool,str)
    skuProgress=Signal(str,str)
    def __init__(self):
        super().__init__()
        self.running=False
        self.calls=[]
        import queue
        self.commands=queue.Queue()
    def isRunning(self):return self.running
    def start(self):self.running=True
    def enqueue(self,rid,msg):self.calls.append((rid,msg))
class FakePage:
    url='https://wms.ssc.shopee.vn/home'
    def __init__(self,valid=True):self.valid=valid;self.calls=[]
    def evaluate(self,js,url):
        self.calls.append((js,url))
        return self.valid

class LoginAndReconnectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def flush(self):
        for _ in range(6):self.app.processEvents()

    def test_first_login_waits_ten_seconds_then_hides(self):
        w=ChromeWorker()
        w._needs_login=True
        w._profile=Path('fixture-profile')
        p=FakePage(True)
        hides=[];ready=[]
        w.workflowReady.connect(lambda:ready.append(True))
        with patch.object(w,'find_page',return_value=p),patch.object(w,'_visibility',side_effect=lambda visible:hides.append(visible) or True):
            w._auth_tick(None,100)
            self.assertEqual(w._hide_at,110)
            self.assertFalse(w._work_ready)
            w._auth_tick(None,109)
            self.assertEqual(hides,[])
            w._auth_tick(None,110)
        self.assertEqual(hides,[False])
        self.assertTrue(ready)
        self.assertEqual(p.calls,[(AUTH_CHECK_JS,URL_EXPORT_LIST)])

    def test_valid_saved_login_ready_immediately(self):
        w=ChromeWorker()
        w._needs_login=False
        p=FakePage(True)
        with patch.object(w,'find_page',return_value=p),patch.object(w,'_visibility',return_value=True) as hide:
            w._auth_tick(None,100)
            self.assertTrue(w._work_ready)
            self.assertEqual(w._hide_at,100)
            w._auth_tick(None,100.5)
            hide.assert_called_once_with(False)

    def test_expired_login_not_hidden_until_reauthenticated(self):
        w=ChromeWorker()
        w._needs_login=False
        p=FakePage(False)
        with patch.object(w,'find_page',return_value=p),patch.object(w,'_visibility') as hide:
            w._auth_tick(None,100)
            self.assertFalse(w._auth_valid)
            self.assertTrue(w._needs_login)
            hide.assert_not_called()
            p.valid=True
            w._auth_tick(None,106)
            self.assertTrue(w._auth_valid)
            self.assertEqual(w._hide_at,116)

    def test_manual_visible_or_disabled_mode_not_hidden(self):
        for enabled,hold in [(True,True),(False,False)]:
            w=ChromeWorker(auto_hide=enabled);w._needs_login=True
            w._hold_visible=hold
            with patch.object(w,'find_page',return_value=FakePage()),patch.object(w,'_visibility') as hide:
                w._auth_tick(None,100)
                w._auth_tick(None,150)
                hide.assert_not_called()

    def test_cot_click_reconnects_once_then_starts_one_get(self):
        tab=ChromeCotTab({},lambda c:True)
        worker=FakeWorker()
        try:
            with patch.object(tab.bridge,'connect_chrome',side_effect=lambda:tab.bridge._connect_mode('chrome',lambda:worker)) as opening:
                tab.fetch_dataset()
                tab.fetch_dataset()
                self.flush()
                self.assertEqual(opening.call_count,1)
                self.assertEqual(worker.calls,[])
                worker.state.emit(True,'WMS ready')
                self.flush()
                self.assertTrue(tab.busy)
                self.assertEqual(len(worker.calls),1)
                self.assertEqual(worker.calls[0][1],{'type':'WMS_GET','url':URL_EXPORT_LIST})
        finally:tab.close()

    def test_extension_mode_never_launches_chrome(self):
        tab=ChromeCotTab({},lambda c:True)
        try:
            tab.bridge.mode='extension'
            with patch.object(tab.bridge,'connect_chrome') as opening:
                tab.fetch_dataset()
                opening.assert_not_called()
        finally:tab.close()

    def test_sku_reconnect_and_cancel_prevent_duplicate_requests(self):
        bridge=NativeBridge({},lambda c:True)
        worker=FakeWorker()
        search=TaskSearch(bridge)
        with patch.object(bridge,'connect_chrome',side_effect=lambda:bridge._connect_mode('chrome',lambda:worker)):
            search.start('sku123')
            self.assertTrue(search.waiting_chrome)
            search.cancel()
            worker.state.emit(True,'ready')
            self.flush()
            self.assertEqual(worker.calls,[])
            bridge._state(False,'Chrome closed')
            worker.running=False
            search.start('sku456')
            self.assertTrue(search.waiting_chrome)
            worker.state.emit(True,'ready')
            self.flush()
            self.assertEqual(len(worker.calls),1)
            self.assertEqual(worker.calls[0][1]['upc'],'sku456')
            search.cancel()

    def test_only_intended_chrome_profile_is_targeted(self):
        import inspect
        from chrome_visibility import chrome_window_handles
        code=inspect.getsource(chrome_window_handles)
        self.assertIn('--user-data-dir',code)
        self.assertIn("chrome.exe",code)
        self.assertIn('Chrome_WidgetWin_',code)
if __name__=='__main__':unittest.main()
