"""Regression: every Check Prod tab must request the selected Vietnam-local time window."""
import os
import unittest
from datetime import datetime
from PySide6.QtCore import QObject, Signal, QDate, QTime
from PySide6.QtWidgets import QApplication
from productivity_tab import CheckProdTab, VN_TZ
import prod_native_core as core

class FakeBridge(QObject):
    completed=Signal(str,str)
    sessionChanged=Signal(bool,str)
    connected=False
    session_message='Offline tests'
    def request(self,*args):raise AssertionError('Tests may not contact WMS')

class SelectedTimeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.w=CheckProdTab(FakeBridge(),{},lambda _:True)
        self.w.show();self.app.processEvents()
        self.w.date.setDate(QDate(2026,10,21))
        self.w.from_time.setTime(QTime(8,0))
        index=self.w.to_time.findData('19:00')
        self.assertGreaterEqual(index,0)
        self.w.to_time.setCurrentIndex(index)
        self.app.processEvents()
        self.now=int(datetime(2026,10,21,22,30,tzinfo=VN_TZ).timestamp())
        self.start=int(datetime(2026,10,21,8,0,tzinfo=VN_TZ).timestamp())
        self.end=int(datetime(2026,10,21,18,59,59,tzinfo=VN_TZ).timestamp())
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents()
    def test_every_tab_uses_exact_selected_window(self):
        for tab,task,dim in (('Sort',43,'individual'),('Check',41,'individual'),
                             ('Check Station',41,'station'),('Check&Pack',41,'station'),
                             ('Pack',42,'individual')):
            with self.subTest(tab=tab):
                req=next(self.w._load(tab,'order_count' if tab=='Pack' else 'item_count',self.now,''))
                self.assertEqual(req['body']['from_time'],self.start)
                self.assertEqual(req['body']['to_time'],self.end)
                self.assertEqual(req['body']['task_type'],task)
                self.assertEqual(req['body']['dim_type'],dim)
    def test_pack_order_queries_match_selected_window(self):
        task=self.w._load('Pack','order_count',self.now,'')
        first=next(task)
        self.assertEqual(first['body']['query_column'],'item_count')
        second=task.send({'success':True,'data':{'list':[{'staff_email':'one@wms','productivity':10,'man_hour':2,'sum_count':21}],'total':1}})
        self.assertEqual(second['body']['query_column'],'order_count')
        self.assertEqual(second['body']['from_time'],self.start)
        self.assertEqual(second['body']['to_time'],self.end)
    def test_window_switch_hides_stale_results(self):
        self.w.cache_key=self.w._view_key()
        self.w.rows=[{'name':'Test','email':'a@wms','productivity':20,'items':100,'manHour':5}]
        self.w._render()
        self.assertEqual(self.w.table.rowCount(),1)
        self.w.from_time.setTime(QTime(9,0))
        self.app.processEvents()
        self.assertEqual(self.w.table.rowCount(),0)
        self.assertFalse(self.w.cache_key==self.w._view_key())
    def test_exact_api_quantities_avoid_rounded_prod_loss(self):
        rows=core.merge_rows([{'staff_email':'x@wms','productivity':83.11,'man_hour':3.28,'sum_count':274}],
                             [{'staff_email':'x@wms','productivity':80.11,'sum_count':273}],{},None,{'PS':{},'SS':{},'CS':{}})
        result=core.summary(rows,'Pack','order_count',0)
        self.assertEqual(result['qty'],273)
        self.assertAlmostEqual(result['manHour'],3.28)
        self.assertAlmostEqual(result['weighted'],273/3.28)
if __name__=='__main__':unittest.main()
