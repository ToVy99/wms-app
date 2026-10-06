"""Regression tests for native COT, full export, and Chrome bridge."""
import base64
import copy
import io
import json
import os
import time
import unittest
import zipfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from openpyxl import Workbook
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate
from cot_logic import *
from chrome_cot import ChromeCotTab, NativeBridge, validate_request, FETCH_JS


def fixture(rows):
    wb=Workbook(); ws=wb.active
    ws.append(['WMS Order No','Status','New 3PL','Buyer State','Shopee order SN','Wave Type','Picking ID','Device ID','Basket ID','Create Time','Cut off Time'])
    for row in rows: ws.append(row)
    out=io.BytesIO();wb.save(out);return out.getvalue()

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self): self.tab=ChromeCotTab({},lambda c:True)
    def tearDown(self):
        if self.tab.parser: self.tab.parser.wait(10000)
        import shiboken6
        shiboken6.delete(self.tab);self.app.processEvents()
    def wait(self,predicate):
        end=time.monotonic()+10
        while not predicate() and time.monotonic()<end:
            self.app.processEvents();time.sleep(.005)
        self.assertTrue(predicate())
    def test_startup_and_scope_changes_never_call_wms(self):
        calls=[];self.tab.request=lambda m,c:calls.append(m)
        self.tab.carrier.setCurrentIndex(1);self.tab.date.setDate(QDate(2026,12,31));self.tab.select_cot('2')
        self.assertEqual(calls,[]);self.assertIsNone(self.tab.bridge.worker);self.assertEqual(self.tab.carrier.count(),4)
    def test_exact_windows_and_year_rollover(self):
        expected={'intra':[('20:00','23:00'),('23:00','02:00'),('02:00','16:00'),('16:00','20:00')],'aha':[('08:00','13:00'),('13:00','18:00'),('18:00','08:00')],'sdd':[('18:00','04:00'),('04:00','09:00'),('09:00','13:30'),('13:30','18:00')],'spxck':[('17:00','17:00')]}
        for k,c in DEFAULT_CONFIG.items(): self.assertEqual([(x['start'],x['end']) for x in c['cots']],expected[k])
        c=DEFAULT_CONFIG['intra'];a,b=time_range('2026-12-31',c,c['cots'][1]);self.assertEqual((b-a).total_seconds(),10800);self.assertEqual(b.year,2027);self.assertEqual(b.minute,0)
        c=DEFAULT_CONFIG['spxck'];a,b=time_range('2026-01-01',c,c['cots'][0]);self.assertEqual((b-a).total_seconds(),86400);self.assertEqual(a.year,2025)
    def test_picked_seven_dedupe_cancel_wave_and_bsk(self):
        rows=[[f'OB{i}','Picked','SPX Express','Hà Nội',f'SN{i}','Single' if i<4 else 'Multi',f'P{i}',f'D{i}',f'B{i}'] for i in range(7)]
        rows+=[['OB7','Outbound','SPX Express NDD - Trong Ngày','Thành phố Hà Nội'],['C','Cancel','SPX Express','Hà Nội'],['WRONG','Picked','SPX Express','Bắc Ninh'],['WRONG3','Picked','Ahamove','Hà Nội'],rows[0]]
        self.tab.orders=parse_report(fixture(rows),'x.xlsx','intra')['orders'];self.tab.active_status=3;self.tab.render_all()
        self.assertEqual(progress(self.tab.orders),(1,8,12.5));self.assertEqual(self.tab.table.rowCount(),7)
        self.assertIn('57.14%',self.tab.wave.itemText(1));self.assertEqual(self.tab.orders[0]['bsks'],{'D0','B0'})
        self.tab.wave.setCurrentIndex(self.tab.wave.findData('Single'));self.assertEqual(self.tab.table.rowCount(),4)
        self.tab.select_visible();self.tab.copy_obvn();self.assertEqual(len(self.app.clipboard().text().splitlines()),4)
    def test_all_carrier_filters_empty_and_outer_zip(self):
        rows=[['A','Picked','Ahamove - Trong Ngày','Bắc Ninh'],['B','Picked','Ahamove SBS - Trong Ngày','Đà Nẵng'],['S','Picked','SPX Express SBS - Trong Ngày','Bắc Ninh'],['K','Picked','SPX - Hàng Cồng Kềnh','Đà Nẵng'],['C','Cancel','Ahamove','Bắc Ninh']]
        raw=fixture(rows);out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('report.xlsx',raw)
        for k,expected in [('intra',[]),('aha',['A','B']),('sdd',['S']),('spxck',['K'])]:self.assertEqual([o['order_number'] for o in parse_report(out.getvalue(),'x.zip',k)['orders']],expected)
        self.assertEqual(parse_report(fixture([]),'x.xlsx','intra')['orders'],[])
    def test_wms_incorrect_a1_dimension_reads_all_columns_and_rows(self):
        import re
        from openpyxl import load_workbook
        original=fixture([[f'OB{i}','Picked','SPX Express','Hà Nội',f'SN{i}'] for i in range(2112)])
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as src, zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data=src.read(item.filename)
                if item.filename=='xl/worksheets/sheet1.xml':
                    data=re.sub(rb'<dimension ref="[^"]+"',b'<dimension ref="A1"',data)
                dst.writestr(item,data)
        broken=out.getvalue()
        wb=load_workbook(io.BytesIO(broken),read_only=True,data_only=True)
        self.assertEqual(next(wb.active.iter_rows(values_only=True)),('WMS Order No',))
        wb.close()
        parsed=parse_report(broken,'wms.xlsx','intra')
        self.assertEqual(len(parsed['orders']),2112)
        self.assertEqual(parsed['rawRows'],2112)
        self.assertEqual(parsed['orders'][-1]['sns'],{'SN2111'})

    def test_2112_orders_one_export_no_second_pass(self):
        data=fixture([[f'OB{i}','Picked','SPX Express','Hà Nội'] for i in range(2112)])
        calls=[]
        def request(msg,callback):
            calls.append(msg)
            if msg['type']=='WMS_DOWNLOAD':callback(base64.b64encode(data).decode())
            elif msg['type']=='WMS_POST':callback({'task_id':'NEW'})
            elif len(calls)==1:callback({'list':[]})
            else:callback({'list':[dict(task_id='NEW',ctime=int(time.time()),task_status=2,download_link=ORIGIN+'/oss_downloads_v2/fixture',export_file_name='fixture.xlsx')]})
        self.tab.bridge.connected=True;self.tab.request=request;self.tab.fetch_dataset();self.wait(lambda:not self.tab.busy)
        self.assertEqual(len(self.tab.orders),2112);self.assertEqual(len(calls),4)
        self.assertEqual(sum(m['url']==URL_EXPORT for m in calls),1);self.assertFalse(any(m['url']==URL_ORDER for m in calls))
        extra=json.loads(calls[1]['body']['extra_data']);self.assertEqual(extra['date_ref'],0);self.assertEqual(extra['include_sku_list'],1)
    def test_status_area_200_cached_and_filters_local(self):
        self.tab.orders=parse_report(fixture([[f'OB{i}','Picked','SPX Express','Hà Nội'] for i in range(7)]),'x.xlsx','intra')['orders'];self.tab.render_all();calls=[]
        def request(msg,cb):calls.append(msg);cb({'total':7,'list':[dict(order_number=f'OB{i}',pre_hit_zone_list=['Z1']) for i in range(7)]})
        self.tab.request=request;self.tab.select_status(3)
        self.assertEqual(self.tab.table.rowCount(),7);self.assertEqual(calls[0]['body']['count'],200)
        self.tab.select_status(None);self.tab.select_status(3);self.tab.area.setCurrentIndex(1);self.assertEqual(len(calls),1)
    def test_429_stops_no_retry_and_ambiguous_jobs_rejected(self):
        with self.assertRaises(ValueError):choose_job([dict(task_id='a',ctime=100),dict(task_id='b',ctime=100)],set(),100)
        self.assertIsNone(choose_job([dict(task_id='old',ctime=100)],{'old'},100))
        self.tab.bridge.connected=True;calls=[]
        def request(rid,raw):calls.append(json.loads(raw));self.tab.bridge.completed.emit(rid,json.dumps(dict(success=False,error='HTTP 429')))
        self.tab.bridge.request=request;self.tab.fetch_dataset();self.assertFalse(self.tab.busy);self.assertEqual(len(calls),1);self.assertIn('429',self.tab.message.text());self.assertIn('resp.status===429',FETCH_JS)
    def test_disconnected_bridge_and_url_validation(self):
        bridge=NativeBridge({},lambda c:True);results=[];bridge.completed.connect(lambda rid,raw:results.append(json.loads(raw)))
        bridge.request('1',json.dumps(dict(type='WMS_GET',url=URL_EXPORT_LIST)));self.assertFalse(results[-1]['success']);self.assertIsNone(bridge.worker)
        for url in ['http://wms.ssc.shopee.vn/api/v2/apps/basic/reportcenter/search_export_task','https://wms.ssc.shopee.vn.evil.example/','https://wms.ssc.shopee.vn/api/unknown']:
            with self.assertRaises(ValueError):validate_request(dict(type='WMS_GET',url=url))
    def test_ui_has_no_embedded_browser(self):
        self.assertFalse(hasattr(self.tab,'view'))
        code=(Path(__file__).parent/'chrome_cot.py').read_text(encoding='utf-8')
        self.assertNotIn('QtWebEngine',code);self.assertNotIn('urllib.request',code)

if __name__=='__main__':unittest.main(verbosity=2)

