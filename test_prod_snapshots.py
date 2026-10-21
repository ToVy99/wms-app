"""Offline Windows Qt tests: explicit reload, per-tab snapshots and exact hourly API data."""
import copy
import os
import unittest
from datetime import datetime
from unittest.mock import patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from productivity_tab import CheckProdTab, TABS, VN_TZ
from prod_report_view import hourly_windows, raw_totals
from test_prod_time_range import FakeBridge
import prod_native_api as api


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.bridge=FakeBridge()
        self.w=CheckProdTab(self.bridge,{},lambda _:True)
        self.w.resize(1200,720);self.w.show();self.app.processEvents()
        self.now=int(datetime(2026,10,22,12,tzinfo=VN_TZ).timestamp())

    def tearDown(self):
        self.w.close();self.w.deleteLater();self.app.processEvents()

    def interval(self,start='07:00',end='18:59'):
        self.w.date.setDate(QDate(2026,10,20))
        self.w.from_time.setText(start);self.w.to_time.setText(end)

    def seed(self,tab,qty=12):
        w=self.w;w.tab_select.setCurrentIndex(TABS.index(tab));self.interval()
        station=500 if tab=='Check&Pack' else 1
        w.rows=[dict(name=f'Nhân viên {i}',email=f'person{i}@example.com',
                     operatorName=f'Nhân viên {i}',operatorEmail=f'person{i}@example.com',
                     stationId=f'CS{station+i:05d}',stationName=f'Station {i}',
                     productivity=100+i,items=100+i,orders=40+i,prod=100+i,staffProd=100+i,
                     manHour=2,hPrev=100,hCur=100,
                     apiTotals={'item_count':{'qty':qty,'hours':2},'order_count':{'qty':5,'hours':2}},
                     hourly=[{'item_count':{'qty':qty,'hours':1},'order_count':{'qty':5,'hours':1}}]*12)
                for i in range(45)]
        w.hour_windows=hourly_windows(w._interval(self.now));w.cache_key=w._view_key();w.loaded_unit=w.unit
        w.show_all.setChecked(True);w._render();self.app.processEvents()

    def snapshot(self):
        w=self.w
        return (w._draft(),copy.deepcopy(w.rows),[v.text() for v in w.metric_values.values()],
                w.show_all.isChecked(),w.sort_ascending,w.table.horizontalScrollBar().value(),
                w.table.verticalScrollBar().value(),w.table.columnWidth(1),w._highlighted_employee)

    def test_blank_manual_times_and_no_preset_side_effects(self):
        w=self.w
        self.assertEqual(w.from_time.text(),'');self.assertEqual(w.to_time.text(),'')
        with self.assertRaises(ValueError):w._interval(self.now)
        self.interval('07:13','18:59')
        w._set_mode('CP');w._set_shift(2)
        self.assertEqual((w.from_time.text(),w.to_time.text()),('07:13','18:59'))
        w.tab_select.setCurrentIndex(0)
        self.assertEqual(w.from_time.text(),'')

    def test_all_tabs_keep_kpi_rows_draft_filter_sort_scroll_and_highlight(self):
        saved={}
        for i,tab in enumerate(TABS):
            self.seed(tab,i+10);w=self.w
            if i%2:w._flip()
            w.from_time.setText(f'{i+7:02d}:13')
            w.table.setColumnWidth(1,270+i)
            w._employee_clicked(i,1)
            w.table.horizontalScrollBar().setValue(300+i*10)
            w.table.verticalScrollBar().setValue(100+i*10)
            self.app.processEvents();saved[tab]=self.snapshot()
        for tab in reversed(TABS):
            self.w.tab_select.setCurrentIndex(TABS.index(tab));self.app.processEvents()
            self.assertEqual(self.snapshot(),saved[tab],tab)

    def test_frozen_employee_real_click_and_vertical_sync(self):
        self.seed('Check');w=self.w
        w.table.horizontalScrollBar().setValue(900)
        w.table.verticalScrollBar().setValue(120);self.app.processEvents()
        frozen=w.table.frozen
        self.assertEqual(frozen.columnViewportPosition(1),w.table.columnWidth(0))
        self.assertEqual(frozen.verticalScrollBar().value(),w.table.verticalScrollBar().value())
        self.assertEqual(frozen.horizontalHeader().height(),w.table.horizontalHeader().height())
        self.assertEqual(frozen.rowViewportPosition(4),w.table.rowViewportPosition(4))
        index=w.table.model().index(4,1)
        QTest.mouseClick(frozen.viewport(),Qt.LeftButton,pos=frozen.visualRect(index).center())
        self.assertIsNotNone(w._highlighted_employee)
        self.assertIn('\n',w.table.item(4,1).text())

    def test_unit_draft_never_relabels_loaded_kpi_and_target_draft_survives(self):
        self.seed('Check');w=self.w;metrics=[v.text() for v in w.metric_values.values()]
        w._set_unit('order_count');w.target.setText('321')
        w.tab_select.setCurrentIndex(0);w.tab_select.setCurrentIndex(1)
        self.assertEqual(w.unit,'order_count');self.assertEqual(w.loaded_unit,'item_count')
        self.assertEqual(w.target.text(),'321')
        self.assertEqual([v.text() for v in w.metric_values.values()],metrics)
        self.assertTrue(w.count.text().endswith('Item'))

    def test_end_minute_overnight_and_partial_hour_boundaries(self):
        for start,end,count in [('07:00','18:59',12),('23:15','01:14',3),('00:00','00:00',1)]:
            self.interval(start,end);interval=self.w._interval(self.now);windows=hourly_windows(interval)
            self.assertEqual(len(windows),count)
            self.assertEqual(windows[0]['from'],interval['from']);self.assertEqual(windows[-1]['to'],interval['to'])
            self.assertEqual(sum(w['to']-w['from']+1 for w in windows),interval['to']-interval['from']+1)
            for a,b in zip(windows,windows[1:]):self.assertEqual(a['to']+1,b['from'])
        self.w.to_time.setText('24:00')
        with self.assertRaises(ValueError):self.w._interval(self.now)
        self.w.to_time.setText('7:30')
        with self.assertRaises(ValueError):self.w._interval(self.now)

    def test_exact_raw_fields_keep_zero_and_missing_without_reverse_calculation(self):
        rows=[{'staff_email':'a','sum_count':0,'man_hour':0,'productivity':999},
              {'staff_email':'b','man_hour':2,'productivity':999},
              {'staff_email':'c','sum_count':13,'man_hour':0.25},
              {'staff_email':' C ','sum_count':17,'man_hour':0.5}]
        totals=raw_totals(rows)
        self.assertEqual(totals['a'],{'qty':0,'hours':0})
        self.assertIsNone(totals['b']['qty'])
        self.assertEqual(totals['c'],{'qty':30,'hours':0.75})

    def test_all_tabs_hourly_requests_use_raw_item_order_and_correct_dimension(self):
        w=self.w
        for tab in TABS:
            self.interval('07:13','08:12');requests=[]
            def fetch(start,end,task,column='item_count',dim='individual',email=''):
                requests.append((start,end,task,column,dim))
                if False:yield
                return [{'staff_email':'a','station_id':'CS00500','sum_count':17 if column=='item_count' else 9,
                         'man_hour':0.5,'productivity':999}]
            def base(*args):
                if False:yield
                return [{'email':'a','stationId':'CS00500','productivity':123}]
            with patch.object(api,'fetch_productivity',fetch),patch.object(w,'_load_base',base):
                gen=w._load(tab,'item_count',self.now,'')
                with self.assertRaises(StopIteration) as done:next(gen)
            row=done.exception.value[0]
            self.assertEqual(row['productivity'],123)
            self.assertEqual(row['apiTotals']['item_count']['qty'],17)
            self.assertEqual([h['order_count']['qty'] for h in row['hourly']],[9,9])
            self.assertEqual(len(requests),6)
            for start,end,task,column,dim in requests:
                self.assertGreaterEqual(start,w._interval(self.now)['from'])
                self.assertLessEqual(end,w._interval(self.now)['to'])
                self.assertEqual(task,43 if tab=='Sort' else 42 if tab=='Pack' else 41)
                self.assertEqual(dim,'station' if tab in ('Check Station','Check&Pack') else 'individual')

    def test_failed_refresh_keeps_old_snapshot_and_success_targets_originating_tab(self):
        self.seed('Check',17);w=self.w;before=copy.deepcopy(w.rows)
        self.bridge.connected=True
        def pending(*args):
            yield {'type':'test'}
            raise api.WMSRequestError('do not display response contents')
        with patch.object(w,'_load',pending),patch.object(w,'_send_request'):
            w._start();w.tab_select.setCurrentIndex(0);w._advance({})
        self.assertEqual(w.tab,'Sort');self.assertEqual(w.table.rowCount(),0)
        w.tab_select.setCurrentIndex(1);self.assertEqual(w.rows,before)
        self.assertNotIn('response contents',w.message.text())
        def success(*args):
            yield {'type':'test'}
            return [dict(before[0],name='New snapshot')]
        with patch.object(w,'_load',success),patch.object(w,'_send_request'):
            w._start();w.tab_select.setCurrentIndex(4);w._advance({})
        self.assertEqual(w.tab,'Pack');self.assertEqual(w.table.rowCount(),0)
        w.tab_select.setCurrentIndex(1);self.assertEqual(w.rows[0]['name'],'New snapshot')


if __name__=='__main__':unittest.main()
