import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,QRect
from PySide6.QtWidgets import QApplication
from sku_task_finder import TaskSearch,SkuTaskDialog,URL_ORDER
from sku_search_engine import SKU_SEARCH_JS
from chrome_cot import validate_request,ChromeWorker
from window_layout import fit_window
import intra_2_3_COT_Dashboard_loginfix as intra
from release_notes import VERSION
class Bridge(QObject):
    completed=Signal(str,str)
    skuProgress=Signal(str,str)
    connected=True
    def __init__(self):super().__init__();self.calls=[];self.cancelled=[]
    def request(self,rid,raw):self.calls.append((rid,json.loads(raw)))
    def cancel_sku(self,rid):self.cancelled.append(rid)
class FinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_parallel_engine(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js required only for engine tests')
        r=subprocess.run([node,str(Path(__file__).with_name('test_sku_engine.js'))],input=SKU_SEARCH_JS,text=True,capture_output=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
    def test_controller_no_duplicate_calls_cancel_and_stale_results(self):
        b=Bridge();s=TaskSearch(b);results=[];progress=[];s.completed.connect(results.append);s.progress.connect(progress.append)
        s.start(' 00 123 ');rid,msg=b.calls[0];self.assertEqual(msg,{'type':'WMS_SKU_SEARCH','url':URL_ORDER,'upc':'00123'})
        s.start('B');self.assertEqual(len(b.calls),1)
        b.skuProgress.emit(rid,'2/8 SN');self.assertEqual(progress[-1],'2/8 SN')
        s.cancel();self.assertEqual(b.cancelled,[rid]);b.completed.emit(rid,json.dumps({'success':True,'data':{}}));self.assertFalse(results);self.assertFalse(s.busy)
        s.start('B');new=b.calls[-1][0];b.completed.emit(rid,'{}');self.assertTrue(s.busy)
        b.completed.emit(new,json.dumps({'success':True,'data':{'tasks':{'T':{'sns':['S']}}}}));self.assertEqual(results[0]['tasks']['T']['sns'],{'S'})
    def test_errors_and_empty_input_do_not_start(self):
        b=Bridge();s=TaskSearch(b);errors=[];s.failed.connect(errors.append)
        s.start(' ');b.connected=False;s.start('A');self.assertFalse(b.calls);self.assertEqual(len(errors),2)
        b.connected=True;s.start('A');b.completed.emit(b.calls[-1][0],json.dumps({'success':False,'error':'Chưa đăng nhập WMS!','auth':True}));self.assertEqual(errors[-1],'Chưa đăng nhập WMS!');self.assertFalse(s.busy)
    def test_cancel_queued_worker_and_validation(self):
        w=ChromeWorker();msg={'type':'WMS_SKU_SEARCH','url':URL_ORDER,'upc':'A'};validate_request(msg)
        w.enqueue('sku-1',msg);self.assertFalse(w.sku_cancelled('sku-1'));w.cancel_sku('sku-1');self.assertTrue(w.sku_cancelled('sku-1'))
        w.enqueue('sku-2',msg);w.cancel_all_sku();self.assertTrue(w.sku_cancelled('sku-2'))
        for bad in [{**msg,'url':'https://example.com/api'},{**msg,'upc':''},{**msg,'url':URL_ORDER.replace('search_order','delete_order')}]:
            with self.assertRaises(ValueError):validate_request(bad)
    def test_dialog_copy_and_close(self):
        b=Bridge();d=SkuTaskDialog(b)
        d.render({'upc':'A','orders':2,'total_api':2,'sns':['S1','S2'],'tasks':{'T':{'task':{'sub_pickup_id':'T','device_id_list':['B1','B2'],'order_structure_list':[1]},'sns':{'S1','S2'}}},'not_found':[],'failed':[],'truncated':[]})
        d.copy_all.click();self.assertEqual(self.app.clipboard().text(),'B1\nB2');d.input.setText('A');d.start();d.reject();self.assertEqual(b.cancelled,[b.calls[-1][0]])
    def test_laptop_window_and_dialog_are_local_and_fit(self):
        with patch.object(intra,'load_config',return_value={'seen_release':VERSION}),patch.object(intra,'save_config',return_value=True),patch.object(intra.WMSDashboard,'start_folder_watcher'),patch.object(intra.WMSDashboard,'check_for_updates'):
            w=intra.WMSDashboard();w.show();self.app.processEvents()
        try:
            for rect in [QRect(0,0,1366,728),QRect(0,0,1093,582),QRect(-1280,0,1280,720)]:
                fit_window(w,available=rect);self.app.processEvents();self.assertTrue(rect.contains(w.frameGeometry()),(rect,w.frameGeometry()))
                w.mainTabs.setCurrentIndex(1);self.app.processEvents();self.assertLessEqual(w.width(),rect.width())
            with patch.object(w.cotTab.bridge,'request') as request:
                w.btnSkuTask.click();self.app.processEvents();self.assertTrue(w.sku_dialog.isVisible());self.assertFalse(w.sku_dialog.searcher.busy)
                for mode in ['light','dark']:w.theme_controller.choose(mode)
                request.assert_not_called();self.assertIs(w.sku_dialog.searcher.bridge,w.cotTab.bridge)
            w.sku_dialog.close();w.showMaximized();self.app.processEvents();self.assertTrue(w.isMaximized())
        finally:w.close();w.theme_controller.disconnect_signals()
if __name__=='__main__':unittest.main()
