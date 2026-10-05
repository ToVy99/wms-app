"""Regression checks for the actual v1.4 JS renderer and Chrome transport."""
import base64
import io
import json
import os
import time
import unittest
from pathlib import Path

os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import openpyxl
from PySide6.QtWidgets import QApplication
from chrome_cot import ChromeCotTab, NativeBridge, validate_request, FETCH_JS


def fixture_bytes(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['WMS Order No','Status','New 3PL','Buyer State','Shopee order SN',
               'Wave Type','Picking ID','Device ID','Basket ID','Create Time','Cut off Time'])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


class WebCotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.tab = ChromeCotTab({}, lambda config: True)
        cls.tab.resize(1450,900)
        cls.tab.show()
        limit=time.monotonic()+30
        while time.monotonic()<limit:
            if cls.js("typeof config!=='undefined' && !!config && $('carrier').options.length===4"):
                break
            cls.app.processEvents()
            time.sleep(.03)
        else:
            raise AssertionError('Embedded v1.4 did not initialize')

    @classmethod
    def js(cls, source):
        values=[]
        cls.tab.view.page().runJavaScript(source, values.append)
        deadline=time.monotonic()+10
        while not values and time.monotonic()<deadline:
            cls.app.processEvents()
            time.sleep(.005)
        if not values:
            raise AssertionError('JavaScript callback timed out')
        return values[0]

    def async_js(self, source):
        self.js("window.__testResult=null;(async()=>{"+source+"})().then(x=>window.__testResult=JSON.stringify({ok:true,value:x})).catch(e=>window.__testResult=JSON.stringify({ok:false,error:e.message}));")
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            result=self.js('window.__testResult')
            if result:
                data=json.loads(result)
                self.assertTrue(data['ok'], data.get('error'))
                return data.get('value')
            self.app.processEvents()
            time.sleep(.01)
        self.fail('Async JS did not complete')

    def test_01_startup_has_no_browser_or_wms_request(self):
        self.assertIsNone(self.tab.bridge.worker)
        self.assertEqual(self.js("Object.keys(config).join(',')"),'intra,aha,sdd,spxck')
        self.assertEqual(self.js("$('tbody').children.length"),0)

    def test_02_all_windows_match_web14(self):
        windows=json.loads(self.js('JSON.stringify(Object.fromEntries(Object.entries(DEFAULT_CONFIG).map(([k,v])=>[k,v.cots.map(c=>c.start+"–"+c.end)])))'))
        self.assertEqual(windows['intra'],['20:00–23:00','23:00–02:00','02:00–16:00','16:00–20:00'])
        self.assertEqual(windows['aha'],['08:00–13:00','13:00–18:00','18:00–08:00'])
        self.assertEqual(windows['sdd'],['18:00–04:00','04:00–09:00','09:00–13:30','13:30–18:00'])
        self.assertEqual(windows['spxck'],['17:00–17:00'])
        self.js("$('date').value='2026-12-31';$('carrier').value='intra';fillCots();$('cot').value='2'")
        self.assertEqual(self.js('Math.round((getRange().end-getRange().beg)/3600000)'),3)
        self.assertEqual(self.js('getRange().end.getDate()'),1)
        self.js("$('carrier').value='spxck';fillCots()")
        self.assertEqual(self.js('Math.round((getRange().end-getRange().beg)/3600000)'),24)

    def test_03_picked_seven_cancel_dedupe_wave_and_tasks(self):
        rows=[[f'OB{i}','Picked','SPX Express','Hà Nội',f'SN{i}',
               'Single' if i<4 else 'Multi',f'P{i}',f'D{i}',f'B{i}','2026-10-05 20:00',''] for i in range(7)]
        rows += [['OB7','Outbound','SPX Express NDD - Trong Ngày','Thành phố Hà Nội','SN7','Multi','P7','D7','B7','',''],
                 ['CANCEL','Cancel','SPX Express','Hà Nội','C','','','','','',''],
                 ['WRONG-STATE','Picked','SPX Express','Bắc Ninh','X','','','','','',''],
                 ['WRONG-3PL','Picked','Ahamove','Hà Nội','Y','','','','','',''], rows[0]]
        data=fixture_bytes(rows)
        result=self.async_js("const bytes=Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0));const p=await parseReport(bytes,'fixture.xlsx','intra');orders=p.orders;activeStatus='3';activeWave='all';activeArea='all';renderAll();return {total:orders.length,shown:visible().length,pct:$('outboundPct').textContent,waves:$('waves').textContent,picking:[...orders[0].picking],bsk:[...orders[0].bsks]}")
        self.assertEqual(result['total'],8)
        self.assertEqual(result['shown'],7)
        self.assertEqual(result['pct'],'12.5%')
        self.assertIn('Single',result['waves'])
        self.assertIn('57.14%',result['waves'])
        self.assertEqual(result['picking'],['P0'])
        self.assertEqual(result['bsk'],['D0','B0'])
        self.assertEqual(self.js("activeWave='Single';renderTable();visible().length"),4)
        self.assertEqual(self.js("activeWave='Multi';renderTable();visible().length"),3)
        self.assertIsNone(self.tab.bridge.worker)

    def test_04_carrier_filters_and_empty_report(self):
        rows=[['A','Picked','Ahamove - Trong Ngày','Bắc Ninh'],
              ['B','Picked','Ahamove SBS - Trong Ngày','Đà Nẵng'],
              ['S','Picked','SPX Express SBS - Trong Ngày','Bắc Ninh'],
              ['K','Picked','SPX - Hàng Cồng Kềnh','Đà Nẵng'],
              ['C','Cancel','Ahamove','Bắc Ninh']]
        data=fixture_bytes(rows)
        result=self.async_js("const b=Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0));const r={};for(const k of ['intra','aha','sdd','spxck'])r[k]=(await parseReport(b,'x.xlsx',k)).orders.map(o=>o.order_number);return r")
        self.assertEqual(result,{'intra':[],'aha':['A','B'],'sdd':['S'],'spxck':['K']})
        empty=fixture_bytes([])
        self.assertEqual(self.async_js("return (await parseReport(Uint8Array.from(atob("+json.dumps(empty)+"),c=>c.charCodeAt(0)),'x.xlsx','intra')).orders.length"),0)

    def test_05_2112_orders_use_one_export_and_no_order_pages(self):
        data=fixture_bytes([[f'OB{i}','Picked','SPX Express','Hà Nội'] for i in range(2112)])
        result=self.async_js("""const oldPost=post,oldGet=get,oldDownload=downloadBytes;
 const calls=[];post=async(u,b)=>{calls.push({u,b});return {task_id:'NEW'}};
 get=async u=>{calls.push({u});return calls.length===1?{list:[]}:{list:[{task_id:'NEW',ctime:Math.floor(Date.now()/1000),task_status:2,processed_percentage:100,download_link:'https://wms.ssc.shopee.vn/oss_downloads_v2/test',export_file_name:'fixture.xlsx'}]}};
 downloadBytes=async()=>Uint8Array.from(atob("""+json.dumps(data)+"""),c=>c.charCodeAt(0));
 try{$('carrier').value='intra';fillCots();await fetchDataset();return {calls,count:orders.length,done:!$('load').disabled}}
 finally{post=oldPost;get=oldGet;downloadBytes=oldDownload}
 """)
        self.assertEqual(result['count'],2112)
        self.assertTrue(result['done'])
        self.assertEqual(len(result['calls']),3)
        self.assertEqual(sum('create_export_task' in c['u'] for c in result['calls']),1)
        self.assertFalse(any('search_order' in c['u'] for c in result['calls']))
        extra=json.loads(result['calls'][1]['b']['extra_data'])
        self.assertEqual(extra['date_ref'],0)
        self.assertEqual(extra['include_sku_list'],1)

    def test_06_reject_ambiguous_export_and_do_not_retry_http429(self):
        result=self.async_js("const old=get;get=async()=>({list:[{task_id:'ONE',ctime:100},{task_id:'TWO',ctime:100}]});try{await waitExport(new Set(),100);return false}catch(e){return e.message.includes('nhiều Export')}finally{get=old}")
        self.assertTrue(result)
        self.assertIn("resp.status===429",FETCH_JS)
        self.assertNotIn('urllib.request',(Path(__file__).parent/'chrome_cot.py').read_text())
        self.assertNotIn('COTOrderListThread',(Path(__file__).parent/'intra_2_3_COT_Dashboard_loginfix.py').read_text())

    def test_07_bridge_disconnected_validation_storage_clipboard(self):
        bridge=NativeBridge({},lambda c:True)
        results=[]
        bridge.completed.connect(lambda rid,raw:results.append(json.loads(raw)))
        bridge.request('1',json.dumps({'type':'WMS_GET','url':'https://wms.ssc.shopee.vn/api/v2/apps/basic/reportcenter/search_export_task'}))
        self.assertFalse(results[-1]['success'])
        self.assertIsNone(bridge.worker)
        bridge.request('2',json.dumps({'type':'STORAGE_SET','value':{'key':{'a':1}}}))
        bridge.request('3',json.dumps({'type':'STORAGE_GET'}))
        self.assertEqual(results[-1]['data'],{'key':{'a':1}})
        bridge.request('4',json.dumps({'type':'COPY','text':'OBVN\nOB2'}))
        self.assertEqual(self.app.clipboard().text(),'OBVN\nOB2')
        for url in ['http://wms.ssc.shopee.vn/api/v2/apps/basic/reportcenter/search_export_task','https://wms.ssc.shopee.vn.evil.example/','https://wms.ssc.shopee.vn/api/unknown']:
            with self.assertRaises(ValueError):
                validate_request({'type':'WMS_GET','url':url})

    @classmethod
    def tearDownClass(cls):
        import shiboken6
        cls.tab.close()
        shiboken6.delete(cls.tab)
        cls.tab = None
        cls.app.processEvents()


if __name__=='__main__':
    unittest.main(verbosity=2)
