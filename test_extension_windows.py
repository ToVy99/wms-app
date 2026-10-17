"""Windows CI: real unpacked extension + packaged native relay + routed WMS fixtures."""
import json,os,sys,tempfile,time,winreg
from pathlib import Path
from PySide6.QtWidgets import QApplication
from playwright.sync_api import sync_playwright
from extension_bridge import ASSETS,ExtensionWorker
from native_link import HOST_NAME,EXTENSION_ID,state_dir
from cot_logic import URL_ORDER,URL_EXPORT_LIST

app=QApplication.instance() or QApplication([])
exe=Path(sys.argv[1]).resolve();root=Path(__file__).resolve().parent
saved=[];old_local=os.environ.get('LOCALAPPDATA');worker=None
old_browser_path=os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
# Isolate the native host's state without moving Playwright's installed browsers.
os.environ['PLAYWRIGHT_BROWSERS_PATH']=old_browser_path or str(Path(old_local)/'ms-playwright')
with tempfile.TemporaryDirectory() as td:
    try:
        os.environ['LOCALAPPDATA']=td
        extension=Path(td)/'extension';extension.mkdir()
        for name,source in ASSETS.items():(extension/name).write_bytes((root/source).read_bytes())
        manifest=Path(td)/'host.json';manifest.write_text(json.dumps({'name':HOST_NAME,'description':'IntraCity CI fixture','path':str(exe),'type':'stdio','allowed_origins':['chrome-extension://'+EXTENSION_ID+'/']}))
        for vendor in ['Google\\Chrome','Chromium']:
            keypath='Software\\'+vendor+'\\NativeMessagingHosts\\'+HOST_NAME
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keypath) as key:previous=winreg.QueryValueEx(key,'')
            except FileNotFoundError:previous=None
            saved.append((keypath,previous))
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(manifest))
        worker=ExtensionWorker();results={};states=[]
        worker.result.connect(lambda rid,raw:results.update({rid:json.loads(raw)}))
        worker.state.connect(lambda ok,text:states.append((ok,text)));worker.start()
        with sync_playwright() as pw:
            context=pw.chromium.launch_persistent_context(str(Path(td)/'profile'),channel='chromium',headless=True,args=['--disable-extensions-except='+str(extension),'--load-extension='+str(extension)])
            requests=[];blob=b'IntraCity ZIP fixture\x00'*100000
            def route(r):
                u=r.request.url
                if '/api/' in u or '/oss_downloads_v2/' in u:
                    requests.append((u,r.request.all_headers()))
                    if '/oss_downloads_v2/' in u:r.fulfill(status=200,body=blob,content_type='application/zip');return
                    if u.endswith('/search_order'):data={'total':1,'list':[{'order_number':'O1','shopee_order_sn':['S1','S2']}]}
                    elif u.endswith('/search_sales_sub_picking_task'):data={'total':1,'list':[{'sub_pickup_id':'T1','device_id':'BSK1'}]}
                    else:data={'total':2112}
                    r.fulfill(status=200,content_type='application/json',body=json.dumps({'retcode':0,'data':data}));return
                r.fulfill(status=200,content_type='text/html',body='<title>WMS fixture kho A</title><h1>Fixture only</h1>')
            context.route('https://wms.ssc.shopee.vn/**',route)
            context.add_cookies([{'name':'fixture_session','value':'fixture-only','domain':'wms.ssc.shopee.vn','path':'/','secure':True}])
            page=context.new_page();page.goto('https://wms.ssc.shopee.vn/home')
            popup=context.new_page();popup.goto('chrome-extension://'+EXTENSION_ID+'/popup.html');popup.locator('#tabs option').wait_for(state='attached')
            assert popup.locator('#tabs').input_value(),popup.locator('#tabs').inner_text()
            print('Extension fixture: selecting existing WMS tab',flush=True);popup.locator('#connect').click()
            def wait(predicate,seconds=30):
                end=time.monotonic()+seconds
                while not predicate() and time.monotonic()<end:app.processEvents();popup.wait_for_timeout(50)
                assert predicate(),{'states':states,'popup':popup.locator('#state').inner_text(),'results':list(results)}
            wait(lambda:any(ok for ok,text in states))
            print('Extension fixture: native host connected',flush=True)
            worker.enqueue('cot',{'type':'WMS_GET','url':URL_EXPORT_LIST});wait(lambda:'cot' in results)
            assert results['cot']=={'success':True,'data':{'total':2112}},results['cot']
            print('Extension fixture: COT response passed',flush=True)
            worker.enqueue('download',{'type':'WMS_DOWNLOAD','url':'https://wms.ssc.shopee.vn/oss_downloads_v2/fixture.zip'});wait(lambda:'download' in results)
            import base64
            assert base64.b64decode(results['download']['data'])==blob
            print('Extension fixture: chunked report passed',flush=True)
            worker.enqueue('sku-fixture',{'type':'WMS_SKU_SEARCH','url':URL_ORDER,'upc':'00123'});wait(lambda:'sku-fixture' in results)
            result=results['sku-fixture'];assert result['success'],result
            assert set(result['data']['tasks']['T1']['sns'])=={'S1','S2'},result
            assert all('fixture_session=fixture-only' in headers.get('cookie','') for _,headers in requests)
            assert len(requests)==5,requests
            assert all(headers.get('x-cctv-tenant-id')=='WMS' for url,headers in requests if '/api/' in url)
            # Navigation invalidates selection; no hidden switch to another warehouse.
            page.goto('https://wms.ssc.shopee.vn/another');wait(lambda:states and not states[-1][0])
            context.close()
        print('PASS: packaged native host + real extension; COT, chunked report >1 MB, SKU, cookies, navigation disconnect; zero real WMS calls')
    finally:
        if worker:worker.requestInterruption();assert worker.wait(10000)
        for keypath,previous in saved:
            if previous is None:
                try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,keypath)
                except FileNotFoundError:pass
            else:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER,keypath) as key:winreg.SetValueEx(key,'',0,previous[1],previous[0])
        if old_local is None:os.environ.pop('LOCALAPPDATA',None)
        else:os.environ['LOCALAPPDATA']=old_local
        if old_browser_path is None:os.environ.pop('PLAYWRIGHT_BROWSERS_PATH',None)
        else:os.environ['PLAYWRIGHT_BROWSERS_PATH']=old_browser_path
