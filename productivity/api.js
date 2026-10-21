(function (root) {
  'use strict';

  var BASE = 'https://wms.ssc.shopee.vn';
  var PROD_URL = BASE + '/mgmt/api/wms_pc/forward_wms_be/api/v2/openapi/mgmt/workspace/pc/data_wms__warehouse_operation_whs__outbound_productivity_info_ri';
  var CHECK_TASKS_URL = BASE + '/api/v2/apps/process/taskcenter/checkingtask/search_checking_task';
  var SORT_TASKS_URL = BASE + '/api/v2/apps/process/taskcenter/sortingtask/search_sorting_task';
  var PACK_TASKS_URL = BASE + '/api/v2/apps/process/outbound/packing/search_packing_task';
  var PAGE = 20;
  var BIG_PAGE = 200;
  var MAX_PAGES = 150;
  var MAX_OFFSET = 2000;                  // WMS refuses to read deeper than offset 2000 ("deep pagination is not allowed")
  var MAX_SORT_PAGES = 10;                // the default range holds thousands of sorting tasks: never read them all
  var PARALLEL = 3;                       // WMS rate-limits (HTTP 429), so keep the burst small
  var MAX_INFLIGHT = 4;                   // never more than 4 requests at once, whatever the number of lists
  var inflight = 0, waiters = [];
  var backoff = [800, 1600, 3200, 6400];  // waits before retry #1..#4 after a 429/503
  var LOG = [];

  // err.kind: 'http' | 'notjson' | 'retcode' | 'network'; err.status = HTTP status when kind is 'http'
  function fail(kind, msg, status) { var e = new Error(msg); e.kind = kind; e.status = status; return e; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function httpMessage(what, status) {
    if (status === 429) return what + ': WMS is limiting requests (HTTP 429). Wait a minute, then press Start again.';
    if (status === 401 || status === 403) return what + ': HTTP ' + status + '. Check that you are signed in to WMS.';
    return what + ': HTTP ' + status + '.';
  }

  // One request with logging, retries after 429/503, and JSON + retcode checks.
  function acquire() {
    if (inflight < MAX_INFLIGHT) { inflight++; return Promise.resolve(); }
    return new Promise(function (resolve) { waiters.push(resolve); });
  }
  function release() {
    var next = waiters.shift();
    if (next) next(); else inflight--;
  }

  async function request(url, init, label, what, meta) {
    await acquire();
    try { return await requestNow(url, init, label, what, meta); }
    finally { release(); }
  }

  async function requestNow(url, init, label, what, meta) {
    var entry = { label: label, status: null, attempts: 0, meta: meta || null };
    LOG.push(entry);
    if (LOG.length > 300) LOG.shift();
    var res;
    for (var attempt = 0; ; attempt++) {
      try { res = await fetch(url, init); }
      catch (e) { entry.status = 'network error'; throw fail('network', what + ": couldn't reach WMS. Check your connection and sign-in."); }
      entry.status = res.status; entry.attempts = attempt + 1;
      if ((res.status === 429 || res.status === 503) && attempt < backoff.length) {
        var ra = res.headers && res.headers.get ? parseFloat(res.headers.get('Retry-After')) : NaN;
        await sleep(isFinite(ra) ? Math.min(ra * 1000, 10000) : backoff[attempt]);
        continue;
      }
      break;
    }
    if (!res.ok) throw fail('http', httpMessage(what, res.status), res.status);
    var j;
    try { j = await res.json(); }
    catch (e) { throw fail('notjson', what + ': response is not JSON. Sign in to WMS and try again.'); }
    entry.retcode = j.retcode;
    entry.total = j.data && j.data.total;
    entry.rows = j.data && j.data.list ? j.data.list.length : null;
    if (j.message && j.retcode !== 0) entry.message = String(j.message).slice(0, 120);
    if (j.retcode !== 0) throw fail('retcode', what + ': ' + (j.message || 'retcode ' + j.retcode));
    return j;
  }

  async function pool(items, limit, worker) {
    var out = new Array(items.length), i = 0, runners = [];
    for (var n = 0; n < Math.min(limit, items.length); n++) {
      runners.push((async function () {
        while (true) {
          var k = i++;
          if (k >= items.length) return;
          out[k] = await worker(items[k]);
        }
      })());
    }
    await Promise.all(runners);
    return out;
  }

  function postProductivity(o, page) {
    var dim = o.dim || 'individual';
    var label = 'POST productivity dim=' + dim + ' ' + o.column + ' task_type=' + o.taskType + ' page=' + page + (o.tag ? ' tag=' + o.tag : '') +
      ' from=' + o.from + ' to=' + o.to + ' user_email=' + (o.email ? 'set' : 'empty');
    return request(PROD_URL, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_time: o.from, to_time: o.to, task_type: o.taskType, dim_type: dim,
        query_column: o.column, order_by_column_key: '', order_type: 'desc', staff_email: '',
        time_interval: 3600, pageno: page, count: PAGE, user_email: o.email || ''
      })
    }, label, dim === 'station' ? 'Stations' : (o.column === 'item_count' ? 'Items' : 'Orders'), { from: o.from, to: o.to, field: 'Time' });
  }

  // All pages of one productivity list. Page 1 gives the total, the rest load a few at a time.
  async function fetchProductivity(o) {
    var first = await postProductivity(o, 1);
    var list = (first.data && first.data.list) || [];
    var total = first.data && first.data.total;
    if (typeof total === 'number') {
      if (list.length < total) {
        var size = Math.max(list.length, PAGE);          // WMS may send more rows than the 20 we asked for
        var pages = Math.min(Math.ceil(total / size), MAX_PAGES), nums = [];
        for (var p = 2; p <= pages; p++) nums.push(p);
        (await pool(nums, PARALLEL, function (p) { return postProductivity(o, p); })).forEach(function (r) {
          list = list.concat((r.data && r.data.list) || []);
        });
      }
    } else {
      for (var q = 2; q <= MAX_PAGES && list.length >= (q - 1) * PAGE; q++) {
        var r2 = await postProductivity(o, q);
        var l2 = (r2.data && r2.data.list) || [];
        if (!l2.length) break;
        list = list.concat(l2);
      }
    }
    return list;
  }

  function getJson(url, label, what, meta) {
    return request(url, { credentials: 'include' }, label, what, meta);
  }

  function taskStation(t) {
    var id = t.checked_station_id || t.checking_station_id || (Array.isArray(t.station_id) ? t.station_id[0] : t.station_id) || '';
    return String(id).toUpperCase();
  }

  async function fetchTasks(buildUrl, what) {
    var all = [];
    for (var page = 1; page <= Math.min(MAX_PAGES, Math.floor(MAX_OFFSET / PAGE) + 1); page++) {
      var j = await getJson(buildUrl(page), 'GET ' + what + ' page=' + page, what);
      var list = (j.data && j.data.list) || [];
      all = all.concat(list);
      var total = j.data && j.data.total;
      if (list.length < PAGE || (typeof total === 'number' && all.length >= total)) break;
    }
    return all;
  }

  function fetchPackTasks() {
    return fetchTasks(function (page) {
      return PACK_TASKS_URL + '?task_status=1&pageno=' + page + '&count=' + PAGE;
    }, 'Pack stations');
  }

  // Checking tasks completed between range.start and range.end (unix seconds) -> { rows, partial }.
  // Asks for a big page first and learns the real page size from what comes back, so it works whether WMS
  // honours the size, caps it, or refuses it (then it falls back to 20 per page). A 429 is retried after a pause.
  // WMS cannot read past offset 2000: pages beyond that are not requested, and a later page that fails keeps
  // what was already read (partial) instead of throwing everything away.
  async function fetchCompletedRange(range) {
    var what = 'Completed tasks';
    var meta = { from: range.start, to: range.end, field: 'Complete Time' };
    function url(page, count) {
      return CHECK_TASKS_URL + '?is_get_total=0&complete_time_start=' + range.start +
        '&complete_time_end=' + range.end + '&pageno=' + page + '&count=' + count;
    }
    function get(page, count) {
      return getJson(url(page, count), 'GET completed page=' + page + ' count=' + count, what, meta);
    }
    var first;
    try { first = await get(1, BIG_PAGE); }
    catch (e) {
      var refused = e.kind === 'retcode' || (e.kind === 'http' && e.status === 400);
      if (!refused) throw e;
      first = await get(1, PAGE);
    }
    var list = (first.data && first.data.list) || [];
    var total = first.data && first.data.total;
    if (!list.length) return { rows: [], partial: null };
    var size = list.length, rows = list.slice(), partial = null;
    if (typeof total === 'number' && size >= total) return { rows: rows, partial: null };

    var maxPage = Math.min(MAX_PAGES, Math.floor(MAX_OFFSET / size) + 1);
    if (typeof total === 'number') {
      var need = Math.ceil(total / size), pages = Math.min(need, maxPage), nums = [];
      if (need > maxPage) partial = 'WMS only lets the first ' + (maxPage * size) + ' of ' + total + ' tasks be read';
      for (var p = 2; p <= pages; p++) nums.push(p);
      var got = await pool(nums, PARALLEL, async function (p) {
        try { var j = await get(p, size); return { list: (j.data && j.data.list) || [] }; }
        catch (e) { return { err: e }; }
      });
      got.forEach(function (g) {
        if (g.err) { partial = partial || g.err.message; } else { rows = rows.concat(g.list); }
      });
      return { rows: rows, partial: partial };
    }
    for (var q = 2; q <= maxPage; q++) {
      var l2;
      try { var j2 = await get(q, size); l2 = (j2.data && j2.data.list) || []; }
      catch (e) { partial = e.message; break; }
      rows = rows.concat(l2);
      if (l2.length < size) break;
    }
    return { rows: rows, partial: partial };
  }

  // Who finished a task last at each wanted station in the last hour before o.now.
  // The hour is read as 5 separate windows, newest first: [0-5) [5-10) [10-20) [20-35) [35-60) minutes ago.
  // A station found in a newer window already has its latest Operator, so reading stops as soon as every
  // wanted station is found. This also keeps each read far below the 2000-row limit of one list.
  async function fetchCheckedRecent(o) {
    var bounds = [0, 300, 600, 1200, 2100, 3600];
    var wanted = {}, nWanted = 0, found = {}, nFound = 0, rows = [], partial = null;
    (o.wanted || []).forEach(function (id) { if (!wanted[id]) { wanted[id] = true; nWanted++; } });
    for (var i = 0; i < bounds.length - 1; i++) {
      var part;
      try { part = await fetchCompletedRange({ start: o.now - bounds[i + 1] + 1, end: o.now - bounds[i] }); }
      catch (e) {
        if (!rows.length) throw e;
        partial = partial || e.message;
        break;
      }
      rows = rows.concat(part.rows);
      if (part.partial && !partial) partial = part.partial;
      part.rows.forEach(function (t) {
        var id = taskStation(t);
        if (t.operator && wanted[id] && !found[id]) { found[id] = true; nFound++; }
      });
      if (nWanted && nFound >= nWanted) break;
    }
    return { rows: rows, partial: partial, complete: nFound >= nWanted };
  }

  // Completed sorting tasks, newest first (by creation time). o = { start, end, hourStart, wanted: [station ids] }.
  // start/end is the WMS default range (7 days, thousands of tasks), so reading stops as soon as every wanted
  // station has an operator and the page has gone back past hourStart - 30 min (or past hourStart - 6 h,
  // or after MAX_SORT_PAGES pages). Stations still without an operator then show "-". -> { rows, partial, complete }
  async function fetchSortTasks(o) {
    var what = 'Sorting tasks';
    var meta = { from: o.start, to: o.end, field: 'Create Time' };
    function url(page, count) {
      return SORT_TASKS_URL + '?task_status=2&beg_ctime=' + o.start + '&end_ctime=' + o.end + '&pageno=' + page + '&count=' + count;
    }
    function get(page, count) {
      return getJson(url(page, count), 'GET sorting page=' + page + ' count=' + count, what, meta);
    }
    var first;
    try { first = await get(1, BIG_PAGE); }
    catch (e) {
      var refused = e.kind === 'retcode' || (e.kind === 'http' && e.status === 400);
      if (!refused) throw e;
      first = await get(1, PAGE);
    }
    var list = (first.data && first.data.list) || [];
    var total = first.data && first.data.total;
    if (!list.length) return { rows: [], partial: null, complete: false };
    var size = list.length, all = list.slice(), partial = null;
    var wanted = {}, nWanted = 0, found = {}, nFound = 0;
    (o.wanted || []).forEach(function (id) { if (!wanted[id]) { wanted[id] = true; nWanted++; } });

    function scan(l) {
      var oldest = Infinity;
      l.forEach(function (t) {
        var id = taskStation(t);
        if (t.operator && wanted[id] && !found[id]) { found[id] = true; nFound++; }
        if (t.ctime && t.ctime < oldest) oldest = t.ctime;
      });
      return oldest;
    }
    function enough(oldest) {
      return oldest < o.hourStart - 6 * 3600 || (nFound >= nWanted && oldest < o.hourStart - 1800);
    }

    if (!enough(scan(list))) {
      var maxPage = Math.min(MAX_SORT_PAGES, Math.floor(MAX_OFFSET / size) + 1);
      for (var page = 2; page <= maxPage; page++) {
        if (typeof total === 'number' && all.length >= total) break;
        var l;
        try { var j = await get(page, size); l = (j.data && j.data.list) || []; }
        catch (e) { partial = e.message; break; }
        if (!l.length) break;
        all = all.concat(l);
        if (enough(scan(l)) || l.length < size) break;
      }
    }
    return { rows: all, partial: partial, complete: nFound >= nWanted };
  }

  root.WMSApi = {
    fetchProductivity: fetchProductivity, fetchPackTasks: fetchPackTasks, fetchCheckedRecent: fetchCheckedRecent,
    fetchSortTasks: fetchSortTasks,
    getLog: function () { return LOG.slice(); }, resetLog: function () { LOG = []; },
    setBackoff: function (a) { backoff = a; }
  };
})(typeof self !== 'undefined' ? self : this);
