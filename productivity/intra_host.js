/* Local-only renderer adapter. WMS requests are executed in the authenticated Chrome
 * tab through IntraCity's existing validated bridge, not in QtWebEngine. */
(function () {
  'use strict';
  const pending = new Map();
  let serial = 0;
  const sessionId = Date.now().toString(36) + Math.random().toString(36).slice(2,8);
  const ready = new Promise((resolve, reject) => {
    if (typeof QWebChannel !== 'function' || !window.qt?.webChannelTransport) {
      reject(new Error('Không mở được cầu nối giao diện Check Prod.')); return;
    }
    new QWebChannel(window.qt.webChannelTransport, ch => resolve(ch.objects.bridge));
  });
  window.__prodReceive = function (id, response) {
    const f = pending.get(String(id));
    if (f) { pending.delete(String(id)); f(response); }
  };
  function rpc(value) {
    return ready.then(native => new Promise(resolve => {
      const id = sessionId + '-' + String(++serial);
      pending.set(id, resolve);
      native.callNative(id, JSON.stringify(value));
    }));
  }
  const storage = {
    get(keys, cb) { rpc({kind:'get',keys}).then(x => cb(x.data || {})).catch(() => cb({})); },
    set(value, cb) { rpc({kind:'set',value}).then(() => cb && cb()).catch(() => cb && cb()); },
    remove(keys, cb) { rpc({kind:'remove',keys}).then(() => cb && cb()).catch(() => cb && cb()); }
  };
  window.chrome = {
    storage: {local: storage},
    runtime: {getManifest: () => ({version:'1.9.4 · IntraCity 3.4'}), getURL: name => name},
    tabs: {create: () => rpc({kind:'upload'})}
  };
  window.__prodExport = function (headers, rows) {
    return rpc({kind:'export',headers,rows});
  };
  const defaultFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : input?.url;
    if (!url || !url.startsWith('https://wms.ssc.shopee.vn/')) return defaultFetch(input,init);
    const method = (init?.method || 'GET').toUpperCase();
    let body = {};
    if (method === 'POST') {
      try { body = JSON.parse(init?.body || '{}'); }
      catch (_) { throw new Error('Nội dung yêu cầu WMS không hợp lệ.'); }
    }
    const response = await rpc({kind:'wms',url,method,body});
    if (response.success) return new Response(JSON.stringify({retcode:0,data:response.data}),
      {status:200,headers:{'Content-Type':'application/json'}});
    const error = String(response.error || 'Chưa kết nối WMS.');
    const match = /HTTP\s+(\d{3})/.exec(error);
    const status = match ? Number(match[1]) : 200;
    return new Response(JSON.stringify({retcode: response.auth ? 10001 : -1, message:error}),
      {status:status >= 200 && status <= 599 ? status : 500, headers:{'Content-Type':'application/json'}});
  };
})();
