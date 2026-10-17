"""Desktop entry point and verification of the real Windows executable."""
import json
import sys
import time
from pathlib import Path
# Native Messaging must start before importing GUI / pandas.
if any(arg.startswith('chrome-extension://') for arg in sys.argv[1:]):
    from native_link import relay
    sys.exit(relay(next(arg for arg in sys.argv[1:] if arg.startswith('chrome-extension://'))))

from PySide6.QtGui import QIcon
import intra_2_3_COT_Dashboard_loginfix as intra
from chrome_cot import FETCH_JS, SKU_FETCH_JS
from sku_search_engine import SKU_SEARCH_JS


def apply_app_icon(app, window):
    # __file__ points inside the bundle when built with PyInstaller.
    icon = QIcon(str(Path(__file__).resolve().with_name('app.ico')))
    if icon.isNull():
        raise RuntimeError('Khong doc duoc app.ico trong thu muc ung dung.')
    app.setWindowIcon(icon)
    window.setWindowIcon(icon)


def main():
    smoke = '--smoke-test' in sys.argv
    if smoke:
        intra.AutoUpdaterThread.run = lambda self: None
        intra.WMSDashboard.start_folder_watcher = lambda self, path=None: None
        intra.show_changes = lambda *args, **kwargs: None
    app = intra.QApplication(sys.argv)
    window = intra.WMSDashboard()
    apply_app_icon(app, window)
    window.show()
    if smoke:
        started = time.monotonic()
        def finish(result):
            with open('smoke-test-result.json','w',encoding='utf-8') as f:
                json.dump(result,f,ensure_ascii=False,indent=2)
            window.grab().save('smoke-gui.png')
            window.updater_thread.wait(2000)
            window.close()
            app.exit(0 if result['passed'] else 1)

        def checked(ready):
            if not ready:
                if time.monotonic()-started < 45:
                    intra.QTimer.singleShot(200, verify)
                else:
                    finish({'passed':False,'error':'Native COT failed to initialize'})
                return
            try:
                assert not app.windowIcon().isNull()
                assert not window.windowIcon().isNull()
                assert window.mainTabs.count()==2
                assert window.mainTabs.tabBar().isHidden()
                assert window.topTabs.count()==2
                from extension_bridge import ASSETS
                assert all(Path(__file__).resolve().with_name(name).is_file() for name in ASSETS.values())
                available=window.screen().availableGeometry()
                assert available.contains(window.frameGeometry())
                window.open_sku_finder()
                assert window.sku_dialog.searcher.bridge is window.cotTab.bridge
                assert not window.sku_dialog.searcher.busy
                assert window.sku_dialog.searcher.counter==0
                window.sku_dialog.grab().save('smoke-sku.png')
                window.sku_dialog.close()
                assert window.cotTab.bridge.worker is None
                assert not hasattr(intra,'COTOrderListThread')
                assert not hasattr(intra,'_wms_post')
                # Route fixtures never reach the real WMS server.
                with intra.sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='chrome',headless=True)
                    context=browser.new_context()
                    context.add_cookies([{'name':'fixture_session','value':'fixture-only','domain':'wms.ssc.shopee.vn','path':'/','secure':True}])
                    seen=[];sku_flow=[False]
                    def route(r):
                        if '/api/' in r.request.url:
                            seen.append(r.request.all_headers())
                            data={'total':2112}
                            if sku_flow[0]:
                                data={'total':1,'list':[{'order_number':'O','shopee_order_sn':['S1','S2']}] } if r.request.url.endswith('/search_order') else {'total':1,'list':[{'sub_pickup_id':'T','device_id':'B'}]}
                            r.fulfill(status=200,content_type='application/json',body=json.dumps({'retcode':0,'data':data}))
                        else:
                            r.fulfill(status=200,content_type='text/html',body='<html>Fixture WMS</html>')
                    context.route('https://wms.ssc.shopee.vn/**',route)
                    page=context.new_page()
                    page.goto('https://wms.ssc.shopee.vn/home')
                    response=page.evaluate(FETCH_JS,{'url':'https://wms.ssc.shopee.vn/api/v2/apps/process/outbound/salesorder/search_order','method':'POST','body':{'pageno':1},'binary':False})
                    assert response=={'success':True,'data':{'total':2112}}
                    assert len(seen)==1
                    assert 'fixture_session=fixture-only' in seen[0].get('cookie','')
                    assert seen[0].get('x-cctv-tenant-id')=='WMS'
                    assert browser.is_connected()
                    sku_response=page.evaluate(SKU_FETCH_JS,{'url':'https://wms.ssc.shopee.vn/api/v2/apps/process/taskcenter/pickingtask/search_sales_sub_picking_task','body':{'search_key_two':'FIXTURE'}})
                    assert sku_response=={'success':True,'data':{'total':2112}}
                    assert len(seen)==2
                    context.expose_binding('__intraSkuCancelled',lambda source,rid:False)
                    context.expose_binding('__intraSkuProgress',lambda source,rid,message:None)
                    sku_flow[0]=True
                    parallel_result=page.evaluate(SKU_SEARCH_JS,{'upc':'00123','requestId':'sku-fixture'})
                    assert parallel_result['success'],parallel_result
                    assert set(parallel_result['data']['tasks']['T']['sns'])=={'S1','S2'}
                    assert parallel_result['requests']==3
                    browser.close()
                window.set_banner_status(False,custom_msg='Chrome transport + native COT verified')
                finish({'passed':True,'tabs':2,'logic_version':'1.4','native_ui':True,'startup_wms_requests':0,
                        'legacy_api_removed':True,'chrome_same_origin_fetch':'passed',
                        'chrome_session_cookie':'passed','real_wms_requests':0})
            except Exception as exc:
                finish({'passed':False,'error':str(exc)})

        def verify():
            checked(window.cotTab.carrier.count()==4)
        intra.QTimer.singleShot(300,verify)
    code = app.exec()
    # Destroy the embedded page before Qt tears down its global WebEngine profile.
    import shiboken6
    window.cotTab.bridge.stop(120000)
    shiboken6.delete(window)
    return code


if __name__=='__main__':
    sys.exit(main())

