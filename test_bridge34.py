import copy,json,os,socket,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject,Signal
from chrome_cot import ChromeCotTab,NativeBridge
from extension_bridge import ExtensionWorker
from native_link import encode_frame,read_frame,EXTENSION_ID
from cot_logic import progress,URL_EXPORT_LIST

class FakeWorker(QObject):
    result=Signal(str,str);state=Signal(bool,str);skuProgress=Signal(str,str)
    def __init__(self):
        super().__init__();import queue;self.commands=queue.Queue();self.calls=[];self.running=False
    def isRunning(self):return self.running
    def start(self):self.running=True
    def enqueue(self,rid,msg):self.calls.append((rid,msg))

class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def spin(self,predicate):
        end=time.monotonic()+5
        while not predicate() and time.monotonic()<end:self.app.processEvents();time.sleep(.01)
        self.assertTrue(predicate())
    def test_one_transport_per_request_and_no_mid_request_switch(self):
        b=NativeBridge({},lambda _:True);chrome=FakeWorker();ext=FakeWorker()
        b._connect_mode('chrome',lambda:chrome);chrome.state.emit(True,'Chrome')
        b._connect_mode('extension',lambda:ext);ext.state.emit(True,'Extension')
        b.request('1',json.dumps({'type':'WMS_GET','url':URL_EXPORT_LIST}))
        self.assertEqual(len(ext.calls),1);self.assertEqual(chrome.calls,[])
        b._connect_mode('chrome',lambda:chrome);self.assertEqual(b.mode,'extension')
        ext.result.emit('1','{"success":true}')
        b._connect_mode('chrome',lambda:chrome);self.assertTrue(b.connected)
        ext.state.emit(False,'lost');self.assertTrue(b.connected)
        b.request('2',json.dumps({'type':'WMS_GET','url':URL_EXPORT_LIST}));self.assertEqual(len(chrome.calls),1)
    def test_chunked_unicode_report_and_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            worker=ExtensionWorker(directory);results=[];states=[]
            worker.result.connect(lambda rid,raw:results.append((rid,json.loads(raw))))
            worker.state.connect(lambda connected,text:states.append(connected));worker.start();client=None
            try:
                endpoint=Path(directory)/'endpoint.json';self.spin(endpoint.exists)
                info=json.loads(endpoint.read_text());client=socket.create_connection(('127.0.0.1',info['port']),timeout=4)
                client.sendall(encode_frame({'kind':'hello','token':info['token'],'extension':EXTENSION_ID}));self.assertEqual(read_frame(client.recv)['kind'],'ready')
                client.sendall(encode_frame({'kind':'state','connected':True,'text':'fixture'}));self.spin(lambda:True in states)
                worker.enqueue('sku-one',{'type':'WMS_SKU_SEARCH','upc':'1'});self.assertEqual(read_frame(client.recv)['id'],'sku-one')
                worker.cancel_sku('sku-one');self.assertEqual(read_frame(client.recv),{'kind':'cancel','id':'sku-one'})
                raw=json.dumps({'success':True,'data':'Mã rổ 🧺 '*40000},ensure_ascii=False)
                pieces=[raw[i:i+60000] for i in range(0,len(raw),60000)]
                client.sendall(encode_frame({'kind':'result_start','id':'sku-one'}))
                for n,part in enumerate(pieces):client.sendall(encode_frame({'kind':'result_chunk','id':'sku-one','seq':n,'text':part}))
                client.sendall(encode_frame({'kind':'result_end','id':'sku-one','count':len(pieces)}))
                self.spin(lambda:bool(results));self.assertEqual(results[0][1]['data'],'Mã rổ 🧺 '*40000)
                worker.enqueue('bad',{'type':'WMS_GET'});read_frame(client.recv)
                client.sendall(encode_frame({'kind':'result_start','id':'bad'}));client.sendall(encode_frame({'kind':'result_end','id':'bad','count':1}))
                self.spin(lambda:len(results)==2);self.assertFalse(results[1][1]['success'])
            finally:
                if client:client.close()
                worker.requestInterruption();self.assertTrue(worker.wait(5000))
    def test_unknown_relay_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            w=ExtensionWorker(directory);w.start();client=None
            try:
                path=Path(directory)/'endpoint.json';self.spin(path.exists);info=json.loads(path.read_text())
                client=socket.create_connection(('127.0.0.1',info['port']),timeout=3)
                client.sendall(encode_frame({'kind':'hello','token':'wrong','extension':EXTENSION_ID}));self.assertEqual(client.recv(1),b'')
            finally:
                if client:client.close()
                w.requestInterruption();self.assertTrue(w.wait(5000))
    def test_basket_projection_preserves_all_source_orders_and_statistics(self):
        tab=ChromeCotTab({},lambda _:True)
        def row(n,baskets,status=3):return dict(order_number=n,order_status=status,bsks=set(baskets),sns={'SN'+n},picking={'P'+n},sku_names={'SKU'+n},area='A1',wave_type='Single',ctime_text='x',cutoff_text='y')
        tab.orders=[row('A',['BSK1','BSK2']),row('B',['BSK1']),row('C',['BSK1'],14),row('D',[],4)]
        original=copy.deepcopy(tab.orders);tab.render_all();tab.toggle_picked_baskets(True)
        self.assertEqual(tab.table.rowCount(),2);self.assertEqual([tab.table.item(i,4).text() for i in range(2)],['BSK1','BSK2'])
        self.assertEqual(tab.orders,original);self.assertEqual(progress(tab.orders),(1,4,25))
        self.assertIn('A: 2',tab.area_summary.text());self.assertNotIn(4,tab.status_buttons);self.assertNotIn(7,tab.status_buttons);self.assertNotIn(8,tab.status_buttons);self.assertIn(10,tab.status_buttons)
        tab.table.selectRow(0);tab.copy_obvn();self.assertEqual(QApplication.clipboard().text(),'A\nB')
        self.assertEqual(set().union(*(o['picking'] for o in tab.target_orders())),{'PA','PB'})
        tab.search.setText('SNB');self.assertEqual(tab.table.rowCount(),1);tab.copy_obvn();self.assertEqual(QApplication.clipboard().text(),'B')
        tab.search.clear();tab.toggle_picked_baskets(False);self.assertEqual(tab.table.rowCount(),2)
        import shiboken6;shiboken6.delete(tab)

if __name__=='__main__':unittest.main()
