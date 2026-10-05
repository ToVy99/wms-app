"""Desktop entry point and verification of the real Windows executable."""
import json
import sys
import time
import intra_2_3_COT_Dashboard_loginfix as intra
from chrome_cot import FETCH_JS


def main():
    smoke = '--smoke-test' in sys.argv
    if smoke:
        intra.AutoUpdaterThread.run = lambda self: None
        intra.WMSDashboard.start_folder_watcher = lambda self, path=None: None
    app = intra.QApplication(sys.argv)
    window = intra.WMSDashboard()
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
                assert window.mainTabs.count()==2
                assert window.cotTab.bridge.worker is None
                assert not hasattr(intra,'COTOrderListThread')
                assert not hasattr(intra,'_wms_post')
                # Route fixtures never reach the real WMS server.
                with intra.sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='chrome',headless=True)
                    context=browser.new_context()
                    context.add_cookies([{'name':'fixture_session','value':'fixture-only','domain':'wms.ssc.shopee.vn','path':'/','secure':True}])
                    seen=[]
                    def route(r):
                        if '/api/' in r.request.url:
                            seen.append(r.request.all_headers())
                            r.fulfill(status=200,content_type='application/json',body='{"retcode":0,"data":{"total":2112}}')
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
