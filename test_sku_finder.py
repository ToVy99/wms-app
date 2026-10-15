import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,QRect
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from sku_task_finder import TaskSearch,SkuTaskDialog,time_window,URL_ORDER,URL_TASK
from chrome_cot import validate_request
from window_layout import fit_window
import intra_2_3_COT_Dashboard_loginfix as intra
from release_notes import VERSION

class Bridge(QObject):
    completed=Signal(str,str)
    connected=True
    def __init__(self):super().__init__();self.calls=[]
    def request(self,rid,raw):self.calls.append((rid,json.loads(raw)))
    def reply(self,data=None,error=None):
        rid=self.calls[-1][0]
        self.completed.emit(rid,json.dumps({'success':not bool(error),'data':data,'error':error}))

class FinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):self.bridge=Bridge();self.search=TaskSearch(self.bridge);self.results=[];self.errors=[];self.search.completed.connect(self.results.append);self.search.failed.connect(self.errors.append)
    def tearDown(self):self.search.cancel();self.search.timer.stop()
    def send(self):self.search.timer.stop();self.search._send()
    def test_payload_pagination_dedup_tasks_and_baskets(self):
        self.search.start(' 00 123 ');self.send();body=self.bridge.calls[-1][1]['body'];self.assertEqual(body,{'sku_upc_code':'00123','order_status_list':'3','pageno':1,'count':20,'is_get_total':1})
        self.bridge.reply({'total':21,'list':[{'order_number':'OB1','shopee_order_sn':['SN1','SN2']}]});self.send()
        self.assertEqual(self.bridge.calls[-1][1]['body']['is_get_total'],0)
        self.bridge.reply({'list':[{'order_number':'OB1','shopee_order_sn':['SN1','SN2']},{'order_number':'OB2','shopee_order_sn':'SN1'}]});self.send()
        self.assertEqual(self.bridge.calls[-1][1]['url'],URL_TASK)
        task={'sub_pickup_id':'TASK1','device_id_list':['B1','B2'],'order_structure_list':[1,2],'sku_qty':2,'sku_item_qty':4}
        self.bridge.reply({'total':21,'list':[task]});self.send();self.assertEqual(self.bridge.calls[-1][1]['body']['pageno'],2)
        self.bridge.reply({'total':21,'list':[task]});self.send();self.assertEqual(self.bridge.calls[-1][1]['body']['search_key_two'],'SN2')
        self.bridge.reply({'total':1,'list':[task]})
        result=self.results[0];self.assertEqual(result['orders'],2);self.assertEqual(len(result['tasks']),1);self.assertEqual(result['tasks']['TASK1']['sns'],{'SN1','SN2'})
        self.assertEqual(len(self.bridge.calls),5);self.assertFalse(self.search.busy)
        dlg=SkuTaskDialog(self.bridge);dlg.render(result);dlg.copy_all.click();self.assertEqual(self.app.clipboard().text(),'B1\nB2');self.assertEqual(dlg.table.item(0,1).text(),'SSSQ / SSAQ');self.assertEqual(dlg.table.item(0,5).text(),'2');dlg.close()
    def test_cancel_ignores_inflight_and_stops_followups(self):
        self.search.start('A');self.send();self.search.cancel();self.search.start('B');self.assertEqual(len(self.bridge.calls),1)
        self.bridge.reply({'total':40,'list':[]});self.assertFalse(self.search.busy);self.assertFalse(self.search.timer.isActive());self.assertFalse(self.results)
        self.search.start('B');self.send();self.bridge.reply({'total':0,'list':[]});self.assertEqual(self.results[0]['upc'],'B')
    def test_transient_error_retries_twice_then_fails_stage_one(self):
        self.search.start('A');self.send()
        first=self.bridge.calls[-1][1]
        for attempt in range(3):
            self.bridge.reply(error='HTTP 503')
            if attempt<2:
                self.assertEqual(self.search.timer.interval(),200*(attempt+1));self.send()
                self.assertEqual(self.bridge.calls[-1][1],first)
        self.assertEqual(len(self.bridge.calls),3);self.assertFalse(self.search.busy)
        self.assertEqual(self.errors,['HTTP 503']);self.assertFalse(self.results)
    def test_missing_null_lists_and_partial_task_errors(self):
        self.search.start('A');self.send()
        self.bridge.reply({'total':3,'list':[{'order_number':str(i),'shopee_order_sn':'SN'+str(i)} for i in range(3)]})
        self.send();self.bridge.reply({'total':0,'list':None})
        self.send();self.bridge.reply({'total':21,'list':[{'sub_pickup_id':'DISCARD'}]})
        self.send()
        for attempt in range(3):
            self.bridge.reply(error='HTTP 500')
            self.send()
        self.assertEqual(self.bridge.calls[-1][1]['body']['search_key_two'],'SN2')
        self.bridge.reply({'total':1,'list':[{'sub_pickup_id':'KEEP'}]})
        result=self.results[-1];self.assertEqual(result['failed'],['SN1'])
        self.assertEqual(result['not_found'],['SN0']);self.assertEqual(list(result['tasks']),['KEEP'])
        self.assertFalse(self.errors)
        self.search.start('B');self.send();self.bridge.reply({'total':0})
        self.assertEqual(self.results[-1]['orders'],0)
    def test_auth_stops_immediately_and_retry_can_be_cancelled(self):
        self.search.start('A');self.send();rid=self.bridge.calls[-1][0]
        self.bridge.completed.emit(rid,json.dumps({'success':False,'auth':True,'error':'Chưa đăng nhập WMS!'}))
        self.assertEqual(len(self.bridge.calls),1);self.assertFalse(self.search.busy);self.assertEqual(len(self.errors),1)
        self.search.start('A');self.send();self.bridge.reply(error='HTTP 503')
        self.assertTrue(self.search.timer.isActive());self.search.cancel();self.send()
        self.assertFalse(self.search.busy);self.assertFalse(self.search.timer.isActive());self.assertEqual(len(self.bridge.calls),2)
    def test_recovered_request_and_empty_task_list(self):
        self.search.start('A');self.send();self.bridge.reply(error='HTTP 502');self.send()
        self.bridge.reply({'total':1,'list':[{'order_number':'O','shopee_order_sn':'S'}]})
        self.send();self.bridge.reply({'total':0})
        self.assertFalse(self.errors);self.assertEqual(self.results[-1]['not_found'],['S'])
    def test_limits_and_no_task(self):
        self.search.start('A');self.send();self.bridge.reply({'total':2001,'list':[]});self.assertIn('2000',self.errors[-1]);self.assertFalse(self.search.busy)
        self.search.start('A');self.send();self.bridge.reply({'total':1,'list':[{'order_number':'OB','shopee_order_sn':'SN'}]})
        for _ in range(5):self.send();self.bridge.reply({'total':101,'list':[{'sub_pickup_id':'TASK'}]})
        self.assertEqual(self.results[-1]['truncated'],['SN'])
        self.search.start('A');self.send();self.bridge.reply({'total':1,'list':[{'order_number':'OB','shopee_order_sn':'SN'}]});self.send();self.bridge.reply({'total':0,'list':[]})
        self.assertEqual(self.results[-1]['not_found'],['SN'])
    def test_timezone_and_endpoint_validation(self):
        now=datetime(2026,12,31,18,tzinfo=timezone.utc);win=time_window(now.timestamp());vn=timezone(timedelta(hours=7))
        self.assertEqual(datetime.fromtimestamp(win['end_time'],vn).isoformat(),'2027-01-01T23:59:59+07:00');self.assertEqual(win['end_time']-win['start_time']+1,7*86400)
        validate_request({'type':'WMS_POST','url':URL_TASK,'body':{}})
        with self.assertRaises(ValueError):validate_request({'type':'WMS_POST','url':URL_TASK.replace('search_sales_sub_picking_task','delete_task'),'body':{}})
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
