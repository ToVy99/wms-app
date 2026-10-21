(function () {
  'use strict';

  var Core = WMSCore, Api = WMSApi;
  var TABS = ['Sort', 'Check', 'Check Station', 'Check&Pack', 'Pack'];
  var THEME = { 'Sort': 'sort', 'Check': 'check', 'Check Station': 'check', 'Check&Pack': 'checkpack', 'Pack': 'pack' };

  var $ = function (id) { return document.getElementById(id); };
  var el = {
    tabs: $('tabs'), target: $('target'), edit: $('edit'), start: $('start'), upd: $('upd'),
    modeSwitch: $('modeSwitch'), shift1: $('shift1'), shift2: $('shift2'), configureShifts: $('configureShifts'), shiftSettings: $('shiftSettings'), closeShifts: $('closeShifts'), saveShifts: $('saveShifts'), presetError: $('presetError'),
    unitSwitch: $('unitSwitch'), unitItem: $('unitItem'), unitOrder: $('unitOrder'), peopleQuantityHeader: $('peopleQuantityHeader'), peopleProdHeader: $('peopleProdHeader'), targetUnit: $('targetUnit'), targetError: $('targetError'), banner: $('banner'), warning: $('warning'),
    emailBox: $('emailBox'), emailMsg: $('emailMsg'), emailInput: $('emailInput'), emailSave: $('emailSave'), emailError: $('emailError'),
    count: $('count'), updated: $('updated'), empty: $('empty'), diag: $('diag'), diagBox: $('diagBox'), diagText: $('diagText'),
    summary: $('summary'), showAll: $('showAll'), tblPeople: $('tblPeople'), rowsPeople: $('rowsPeople'), rangeBox: $('rangeBox'), rangeFrom: $('rangeFrom'), rangeTo: $('rangeTo'), rangeDate: $('rangeDate'), rangeNote: $('rangeNote'), tblStation: $('tblStation'), tblPack: $('tblPack'), tblSort: $('tblSort'), rowsStation: $('rowsStation'), rowsPack: $('rowsPack'), rowsSort: $('rowsSort')
  };

  var state = {
    tab: 'Check',
    mode: 'BAU', shiftNumber: 1, presets: {BAU1:'08:00–19:00',BAU2:'19:00–06:00',CP1:'07:00–18:00',CP2:'18:00–06:00'},
    targets: Object.assign({}, Core.DEFAULT_TARGETS),
    peopleUnit: 'item_count', orderTargets: { Sort: 110, Check: 110, Pack:110 },
    editing: false,
    busy: false,
    namesFile: null,
    last: null,
    cache: { sort: null, check: null, checkstation: null, checkpack: null, pack: null }, generation: 0
  };

  function isPeopleTab(t) { return t === 'Sort' || t === 'Check'; }
  function activeTarget() { return (isPeopleTab(state.tab) || state.tab === 'Pack') && state.peopleUnit === 'order_count' ? state.orderTargets[state.tab] : state.targets[state.tab]; }
  function groupOf(tab) { return tab === 'Pack' ? 'pack' : (tab === 'Sort' ? 'sort' : (tab === 'Check' ? 'check' : (tab === 'Check Station' ? 'checkstation' : 'checkpack'))); }
  function nowSec() { return Math.floor(Date.now() / 1000); }
  function fmt(v) { return typeof v === 'number' ? v.toFixed(2) : '-'; }
  function whole(v) { return typeof v === 'number' ? String(Math.round(v)) : '-'; }
  function clockVN(d) {
    return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', hour12: false }).format(d);
  }

  function validPreset(value) {
    var m = /^(\d{2}:\d{2})[–-](\d{2}:\d{2})$/.exec(String(value).trim().replace(/\s/g,''));
    if (!m || ![m[1],m[2]].every(function(v){return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v);}) || m[1] === m[2]) return null;
    return { start:m[1], end:m[2], normalized:m[1]+'–'+m[2] };
  }
  function persistRange() {
    storageSet({ intervalPrefs:{date:el.rangeDate.value,from:el.rangeFrom.value,to:el.rangeTo.value} });
    state.cache.sort=null;state.cache.check=null;render();
  }
  function renderMode() {
    Array.prototype.forEach.call(el.modeSwitch.children,function(b){b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode));});
    el.shift1.setAttribute('aria-pressed',String(state.shiftNumber===1));
    el.shift2.setAttribute('aria-pressed',String(state.shiftNumber===2));
    el.shift1.title=state.presets[state.mode+'1'];el.shift2.title=state.presets[state.mode+'2'];
  }
  function applyPreset(n) {
    var preset=validPreset(state.presets[state.mode+n]);if(!preset)return;
    state.shiftNumber=n;
    // For an overnight shift selected after midnight (before its end), use yesterday as start date.
    var vn = new Date(Date.now() + 7 * 3600000);
    var today = vn.toISOString().slice(0,10);
    var currentClock = vn.toISOString().slice(11,16);
    if (preset.end < preset.start && currentClock < preset.end && el.rangeDate.value === today) {
      el.rangeDate.value = new Date(vn.getTime() - 86400000).toISOString().slice(0,10);
    } else if (el.rangeDate.value === new Date(vn.getTime() - 86400000).toISOString().slice(0,10) && currentClock >= preset.start) {
      el.rangeDate.value = today;
    }
    el.rangeFrom.value=preset.start;
    if(!Array.from(el.rangeTo.options).some(function(o){return o.value===preset.end;})){
      var option=document.createElement('option');option.value=preset.end;option.textContent=preset.end;el.rangeTo.appendChild(option);
    }
    el.rangeTo.value=preset.end;
    storageSet({ shiftMode:state.mode,shiftNumber:n });
    persistRange();renderMode();
  }
  // ---------- storage ----------
  function storageGet(keys) { return new Promise(function (res) { chrome.storage.local.get(keys, res); }); }
  function storageSet(obj) { return new Promise(function (res) { chrome.storage.local.set(obj, res); }); }

  // ---------- render ----------
  function cell(tr, cls, text) {
    var td = document.createElement('td');
    if (cls) td.className = cls;
    td.textContent = text;
    tr.appendChild(td);
    return td;
  }

  // class for a number that is below the target (red), nothing for a number that passes or is missing
  function mark(v, target) {
    return 'num' + (Core.failFlags([v], target)[0] ? ' prod' : '');
  }

  function mailLine(cls, text) {
    var d = document.createElement('div');
    d.className = cls; d.textContent = text; d.title = text;
    return d;
  }

  function renderStation(list, target) {
    el.rowsStation.textContent = '';
    list.forEach(function (r) {
      var tr = document.createElement('tr');
      cell(tr, 'c-first', r.stationId);
      cell(tr, '', r.stationName || '-');
      cell(tr, 'num', fmt(r.prod));
      cell(tr, 'num', fmt(r.manHour));
      cell(tr, 'num', whole(r.items));

      var op = document.createElement('td');
      op.className = 'gl';
      if (r.operatorName) {
        var n = document.createElement('div');
        n.className = 'opname'; n.textContent = r.operatorName; n.title = r.operatorName;
        op.appendChild(n);
        op.appendChild(mailLine('opmail', r.operatorEmail || ''));
      } else if (r.operatorEmail) {
        op.appendChild(mailLine('opmail solo', r.operatorEmail));
      } else {
        op.textContent = '-';
      }
      tr.appendChild(op);
      cell(tr, mark(r.staffProd, target), fmt(r.staffProd));
      cell(tr, 'num', fmt(r.staffMh));
      cell(tr, mark(r.hPrev, target), fmt(r.hPrev));
      cell(tr, mark(r.hCur, target) + ' c-last', fmt(r.hCur));
      el.rowsStation.appendChild(tr);
    });
  }

  function renderPack(list, target) {
    el.rowsPack.textContent = '';
    list.forEach(function (r) {
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.className = 'c-first';
      var n = document.createElement('div');
      n.className = 'opname'; n.textContent = r.name; n.title = r.name;
      td.appendChild(n);
      td.appendChild(mailLine('opmail', r.email || '-'));
      tr.appendChild(td);
      cell(tr, state.peopleUnit === 'item_count' ? mark(r.items, target) : 'num', fmt(r.items));
      cell(tr, state.peopleUnit === 'order_count' ? mark(r.orders, target) : 'num', fmt(r.orders));
      cell(tr, 'num', fmt(r.manHour));
      cell(tr, mark(r.hPrev, target), fmt(r.hPrev));
      cell(tr, mark(r.hCur, target), fmt(r.hCur));
      cell(tr, '', r.stationId || '-');
      cell(tr, 'c-last', r.stationName || '-');
      el.rowsPack.appendChild(tr);
    });
  }

  // Sort: one row per Operator. Station columns come first (the stations they last worked at, stacked one
  // line each), then the Operator columns.
  function renderSort(list, target) {
    el.rowsSort.textContent = '';
    el.rowsPeople.textContent = '';
    list.forEach(function (p) {
      var tr = document.createElement('tr');

      function stack(cls, pick) {
        var td = document.createElement('td');
        if (cls) td.className = cls;
        p.stations.forEach(function (st) {
          var d = document.createElement('div');
          d.className = 'stline' + (cls && cls.indexOf('num') >= 0 ? ' num' : '');
          d.textContent = pick(st);
          td.appendChild(d);
        });
        tr.appendChild(td);
      }
      stack('c-first', function (st) { return st.stationId; });
      stack('', function (st) { return st.stationName || '-'; });
      stack('num', function (st) { return fmt(st.prod); });
      stack('num', function (st) { return fmt(st.manHour); });
      stack('num', function (st) { return whole(st.items); });

      var op = document.createElement('td');
      op.className = 'gl';
      if (p.name) {
        var n = document.createElement('div');
        n.className = 'opname'; n.textContent = p.name; n.title = p.name;
        op.appendChild(n);
        op.appendChild(mailLine('opmail', p.email || ''));
      } else {
        op.appendChild(mailLine('opmail solo', p.email || '-'));
      }
      tr.appendChild(op);
      cell(tr, mark(p.staffProd, target), fmt(p.staffProd));
      cell(tr, 'num', fmt(p.staffMh));
      cell(tr, mark(p.hPrev, target), fmt(p.hPrev));
      cell(tr, mark(p.hCur, target) + ' c-last', fmt(p.hCur));
      el.rowsSort.appendChild(tr);
    });
  }

  function renderPeople(list, target) {
    el.rowsPeople.textContent = '';
    list.forEach(function (r) {
      var tr = document.createElement('tr');
      var td = document.createElement('td'); td.className='c-first';
      td.appendChild(mailLine('opname', r.name || r.email || '-'));
      if (r.email && r.name !== r.email) td.appendChild(mailLine('opmail', r.email));
      tr.appendChild(td);
      cell(tr, 'num', fmt(r.items));
      cell(tr, 'num', fmt(r.manHour));
      cell(tr, mark(r.productivity, target), fmt(r.productivity));
      cell(tr, 'num c-last', fmt(target));
      el.rowsPeople.appendChild(tr);
    });
  }

  function intervalWindow() {
    var day = el.rangeDate.value, start = el.rangeFrom.value, end = el.rangeTo.value;
    if (!day || !start) throw new Error('Hãy chọn ngày và giờ bắt đầu.');
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(start)) throw new Error('Nhập giờ bắt đầu theo định dạng 24h HH:mm (ví dụ 19:20).');
    var from = Math.floor(new Date(day + 'T' + start + ':00+07:00').getTime() / 1000);
    var to = end === 'now' ? nowSec() : Math.floor(new Date(day + 'T' + end + ':00+07:00').getTime() / 1000);
    if (end !== 'now' && to <= from) to += 86400;
    if (to <= from) throw new Error('Giờ bắt đầu phải trước giờ hiện tại.');
    if (from > nowSec()) throw new Error('Giờ bắt đầu không được ở tương lai.');
    if (to > nowSec()) { to = nowSec(); el.rangeNote.textContent = 'Giờ kết thúc ở tương lai: sử dụng giờ hiện tại.'; }
    else el.rangeNote.textContent = '';
    return { from: from, to: to };
  }

  function buildPeople(items) {
    var map = new Map();
    (items || []).forEach(function (r) {
      var key = Core.norm(r.staff_email);
      if (!key) return;
      var prod = r.productivity === null || r.productivity === undefined ? NaN : Number(r.productivity);
      var mh = r.man_hour === null || r.man_hour === undefined ? NaN : Number(r.man_hour);
      var row = map.get(key);
      if (!row) {
        row = { name: r.local_staff_name || r.staff_name || r.staff_email,
          email: r.staff_email, productivity: null, manHour: null, items: null,
          _qty: 0, _hours: 0, _valid: 0, _missing: 0 };
        map.set(key, row);
      }
      // If WMS groups a person by hour, sum quantity and hours, then divide once.
      // An unusable segment makes the interval indeterminate rather than falsely low.
      if (Number.isFinite(prod) && Number.isFinite(mh) && mh > 0) {
        row._qty += prod * mh;
        row._hours += mh;
        row._valid++;
      } else row._missing++;
    });
    return Array.from(map.values()).map(function (r) {
      if (r._hours > 0 && !r._missing) {
        r.productivity = r._qty / r._hours;
        r.manHour = r._hours;
        r.items = r._qty;
      }
      delete r._qty; delete r._hours; delete r._valid; delete r._missing;
      return r;
    });
  }

  function filterPeople(rows, target) {
    return rows.filter(function (r) { return typeof r.productivity === 'number' && r.productivity < target; })
      .sort(function (a, b) { return a.productivity - b.productivity; });
  }

  async function loadPeople(tab, interval, email) {
    var people = await Api.fetchProductivity({ dim: 'individual', from: interval.from, to: interval.to,
      taskType: tab === 'Sort' ? 43 : 41, column: state.peopleUnit, email: email });
    return { rows: buildPeople(people), updatedAt: clockVN(new Date()), interval: interval, queryColumn: state.peopleUnit };
  }

  function emptyMessage(tab, isStations, noRows, total, hidden) {
    if (noRows) {
      return 'WMS không có dữ liệu ' + (isStations ? 'Station' : 'nhân viên') + ' cho ' + (tab === 'Sort' ? 'giờ này' : 'ca này') +
        '. Nếu vẫn gặp lỗi, hãy mở Chẩn đoán.';
    }
    if (!total && hidden) {
      return 'Không có thông tin Prod nhân viên tại ' + hidden + ' Station trong ' + tab + ': chưa có Task hoàn thành gần đây hoặc thiếu dữ liệu nhân viên.';
    }
    return 'Tất cả đều đạt hoặc vượt Target';
  }

  // Decorative, locally rendered SVG-free icons; KPI values always come from real WMS data.
  var KPI_ICONS = ['▱','▥','◴','♙','⚠'];
  function addKpiCard(entry, index) {
    var card = document.createElement('div'); card.className = 'metric-card kpi-' + index;
    var glyph = document.createElement('span'); glyph.className = 'metric-icon'; glyph.textContent = KPI_ICONS[index]; glyph.setAttribute('aria-hidden','true');
    var details = document.createElement('div'); details.className = 'metric-details';
    var label = document.createElement('span'); label.className = 'metric-label'; label.textContent = entry[0];
    var value = document.createElement('strong'); value.className = 'metric-value'; value.textContent = entry[1];
    var sub = document.createElement('span'); sub.className = 'metric-sub'; sub.textContent = entry[2];
    details.appendChild(label); details.appendChild(value); details.appendChild(sub);
    card.appendChild(glyph);card.appendChild(details);el.summary.appendChild(card);
  }

  // Display-only ordering: use existing per-row Prod fields and never modify source rows.
  var prodAscending = false;
  var directionButton = document.getElementById('sortDirection');
  function sortForView(rows, tab) {
    function score(r) {
      var value = tab === 'Pack' ? (state.peopleUnit === 'order_count' ? r.orders : r.items) :
        (isPeopleTab(tab) ? r.productivity : (tab === 'Sort' ? r.staffProd : r.prod));
      var n = Number(value); return value == null || !Number.isFinite(n) ? null : n;
    }
    return rows.slice().sort(function (a,b) {
      var x=score(a), y=score(b);
      if (x === null) return y === null ? 0 : 1;
      if (y === null) return -1;
      return prodAscending ? x-y : y-x;
    });
  }
  document.getElementById('exportProd').addEventListener('click', function () {
    var tbl = Array.prototype.find.call(document.querySelectorAll('.tablewrap table'), function (t) { return !t.hidden; });
    if (!tbl) return;
    var headers = Array.prototype.map.call(tbl.querySelectorAll('thead tr:last-child th'), function (th) { return th.textContent.trim(); });
    var rows = Array.prototype.map.call(tbl.querySelectorAll('tbody tr'), function (tr) {
      return Array.prototype.map.call(tr.querySelectorAll('td'), function (td) { return td.textContent.trim(); });
    });
    window.__prodExport(headers, rows).then(function(r) {
      if (r && !r.ok) setMsg(el.banner, r.error || 'Không xuất được Excel.');
    }).catch(function(e) { setMsg(el.banner, e.message || 'Không xuất được Excel.'); });
  });
  directionButton.addEventListener('click', function () {
    prodAscending = !prodAscending;
    directionButton.textContent = prodAscending ? '↑ Thấp → Cao' : '↓ Cao → Thấp';
    render();
  });

  function render() {
    var tab = state.tab, isPack = tab === 'Pack', isSort = tab === 'Sort', isPeople = isPeopleTab(tab), target = activeTarget(), data = state.cache[groupOf(tab)];

    document.body.setAttribute('data-theme', THEME[tab]);
    Array.prototype.forEach.call(el.tabs.children, function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-tab') === tab ? 'true' : 'false');
    });
    el.target.value = target;
    el.unitSwitch.hidden = !(isPeople || isPack);
    el.unitItem.setAttribute('aria-pressed', String(state.peopleUnit === 'item_count'));
    el.unitOrder.setAttribute('aria-pressed', String(state.peopleUnit === 'order_count'));
    el.targetUnit.textContent = state.peopleUnit === 'order_count' ? 'Orders/h' : 'Items/h';
    el.peopleQuantityHeader.textContent = state.peopleUnit === 'order_count' ? 'Orders (WMS-derived estimate)' : 'Items (WMS-derived estimate)';
    el.peopleProdHeader.textContent = state.peopleUnit === 'order_count' ? 'Prod (Orders/h)' : 'Prod (Items/h)';
    el.rangeBox.hidden = !isPeople;
    el.tblPeople.hidden = !isPeople;
    el.tblSort.hidden = true;
    el.tblStation.hidden = isPack || isPeople;
    el.tblPack.hidden = !isPack;
    el.rowsStation.textContent = '';
    el.rowsPack.textContent = '';
    el.rowsSort.textContent = '';
    el.rowsPeople.textContent = '';

    el.summary.hidden = false;
    el.summary.textContent = '';
    if (!data) {
      // Keep the summary visible before the first API request, without presenting invented values.
      [
        ['TỔNG SẢN LƯỢNG', '—', state.peopleUnit === 'order_count' ? 'Order · đang chờ dữ liệu' : 'Item · đang chờ dữ liệu'],
        ['TỔNG PROD', '—', 'Chờ dữ liệu'],
        ['PROD TRUNG BÌNH', '—', 'Chờ dữ liệu'],
        ['GIỜ CÔNG', '—', 'Chờ dữ liệu'],
        ['DƯỚI TARGET', '—', 'Chờ dữ liệu']
      ].forEach(addKpiCard);
      el.count.textContent = '';
      el.updated.textContent = '';
      el.empty.textContent = 'Bấm Tải dữ liệu để lấy ' + tab + ' data';
      return;
    }

    var list, total, hidden = 0, unit = '', below;
    if (isPack) {
      below = state.peopleUnit === 'order_count' ? data.rows.filter(function(r){return Number.isFinite(r.orders) && r.orders < target;}) : Core.filterPackRows(data.rows, target);
      list = el.showAll.checked ? data.rows : below;
      total = data.rows.length;
      renderPack(sortForView(list, tab), target);
    } else if (isPeople) {
      below = filterPeople(data.rows, target);
      list = el.showAll.checked ? data.rows : below;
      total = data.rows.length; unit = 'operators ';
      renderPeople(sortForView(list, tab), target);
    } else {
      var kind = tab === 'Check Station' ? 'Check' : tab;
      var eligible = data.rows.filter(function (r) { return Core.areaOf(r.stationId) === kind; });
      below = tab === 'Check Station' ? eligible.filter(function (r) { return Number.isFinite(r.prod) && r.prod < target; }).sort(function (a,b) { return a.prod - b.prod; }) : Core.filterStationRows(data.rows, kind, target);
      list = el.showAll.checked ? eligible : below;
      var c = Core.countStations(data.rows, kind);
      total = tab === 'Check Station' ? eligible.length : c.total; hidden = tab === 'Check Station' ? 0 : c.hidden; unit = 'stations ';
      renderStation(sortForView(list, tab), target);
    }
    {
      var summaryRows = isPeople || isPack ? data.rows : data.rows.filter(function (r) { return Core.areaOf(r.stationId) === (tab === 'Check Station' ? 'Check' : tab); });
      var vals = summaryRows.filter(function (r) {
        var q = isPack && state.peopleUnit === 'order_count' ? r.orders * r.manHour : isPack ? r.items * r.manHour : r.items, h = r.manHour;
        return Number.isFinite(q) && Number.isFinite(h) && h > 0;
      });
      var qty = vals.reduce(function (a,r) { return a + (isPack ? (state.peopleUnit === 'order_count' ? r.orders : r.items) * r.manHour : r.items); }, 0);
      var mh = vals.reduce(function (a,r) { return a + r.manHour; }, 0);
      var pr = vals.map(function (r) { return isPeople ? r.productivity : (isPack ? (state.peopleUnit === 'order_count' ? r.orders : r.items) : r.prod); }).filter(Number.isFinite);
      var weighted = mh > 0 ? qty / mh : null;
      var avg = pr.length ? pr.reduce(function (a,b) { return a+b; },0)/pr.length : null;
      var isOrder = state.peopleUnit === 'order_count' && (isPeople || isPack);
      var quantityUnit = isOrder ? 'Orders' : 'Items';
      var summaryCards = [
        ['TỔNG SẢN LƯỢNG', whole(qty), quantityUnit + ' đã xử lý'],
        ['TỔNG PROD', fmt(weighted), quantityUnit + '/h (weighted)'],
        ['PROD TRUNG BÌNH', fmt(avg), quantityUnit + '/h (arithmetic)'],
        ['GIỜ CÔNG', fmt(mh), 'Giờ'],
        ['DƯỚI TARGET', String(below.length), (isPeople || isPack ? 'Nhân viên' : 'Station')]
      ];
      summaryCards.forEach(addKpiCard);
      el.summary.hidden = false;
    }
    el.count.textContent = below.length + ' dưới Target trong tổng số ' + total + ' ' + unit + 'trong ' + tab +
      (hidden ? ' · ' + hidden + ' Station chưa xác định nhân viên' : '');
    el.updated.textContent = 'Cập nhật ' + data.updatedAt + (state.namesFile ? ' · Tên Station: ' + state.namesFile : '');
    el.empty.textContent = list.length ? '' : emptyMessage(tab, !isPack, !data.rows.length, total, hidden);
  }

  // ---------- messages ----------
  function setMsg(node, text) {
    node.textContent = text || '';
    node.hidden = !text;
  }

  // ---------- target ----------
  function lockTarget() {
    state.editing = false;
    el.target.readOnly = true;
    el.edit.textContent = 'Sửa';
  }

  function saveTarget() {
    var v = parseFloat(el.target.value);
    if (!(v > 0)) { el.targetError.hidden = false; return false; }
    el.targetError.hidden = true;
    if ((isPeopleTab(state.tab) || state.tab === 'Pack') && state.peopleUnit === 'order_count') {
      state.orderTargets[state.tab] = v;
      storageSet({ orderTargets: state.orderTargets });
    } else {
      state.targets[state.tab] = v;
      storageSet({ targets: state.targets });
    }
    lockTarget();
    return true;
  }

  // ---------- data ----------
  function soft(p) {
    return p.then(function (v) { return { ok: v }; }, function (e) { return { err: e }; });
  }

  // The two extra lists: Operator productivity (Items) in H-1 and H, same request, only the hour changes.
  // In the first hour of a shift H is the same window as the whole-shift list, so that list is reused.
  function hourLists(taskType, email, win, shiftList) {
    var hw = Core.hourWindows(nowSec());
    var base = { dim: 'individual', taskType: taskType, column: 'item_count', email: email };
    var same = shiftList && win.from === hw.cur.from && win.to === hw.cur.to;
    return [
      soft(Api.fetchProductivity(Object.assign({ from: hw.prev.from, to: hw.prev.to, tag: 'H-1' }, base))),
      same ? shiftList : soft(Api.fetchProductivity(Object.assign({ from: hw.cur.from, to: hw.cur.to, tag: 'H' }, base)))
    ];
  }

  function hourWarning(prev, cur) {
    var errs = [];
    if (prev.err) errs.push('Prod H-1 (' + prev.err.message + ')');
    if (cur.err) errs.push('Prod H (' + cur.err.message + ')');
    return errs.length ? errs.join(' ') + ' chưa có dữ liệu.' : '';
  }

  function hourMaps(prev, cur) {
    return { prev: Core.hourMap(prev.ok || []), cur: Core.hourMap(cur.ok || []) };
  }

  // Check and Check&Pack: one row per station.
  async function loadCheck(win, email) {
    var now = nowSec();
    // Same upper limit the Pack request uses (end of the current hour). If WMS answers with nothing,
    // try once more with the end of the whole shift, then give up.
    var base = { from: win.from, to: win.to, taskType: 41, column: 'item_count', email: email };
    var stationList = await Api.fetchProductivity(Object.assign({ dim: 'station' }, base));
    if (!stationList.length && win.end !== win.to) {
      var alt = Object.assign({}, base, { to: win.end });
      var again = await Api.fetchProductivity(Object.assign({ dim: 'station' }, alt));
      if (again.length) { stationList = again; base = alt; }
    }
    if (!stationList.length) {
      setMsg(el.warning, '');
      return { rows: [], updatedAt: clockVN(new Date()) };
    }
    var shiftP = soft(Api.fetchProductivity(Object.assign({ dim: 'individual' }, base)));
    var hl = hourLists(41, email, base, shiftP);
    var res = await Promise.all([
      shiftP,
      soft(Api.fetchCheckedRecent({ now: now, wanted: Core.stationIds(stationList) })),
      hl[0], hl[1]
    ]);
    var people = res[0], tasks = res[1], warnings = [];
    if (people.err) warnings.push('Không tải được tên nhân viên (' + people.err.message + ').');
    if (tasks.err) warnings.push('Không tải được nhân viên (' + tasks.err.message + ').');
    else if (tasks.ok.partial && !tasks.ok.complete) warnings.push('Có thể thiếu thông tin nhân viên (' + tasks.ok.partial + ').');
    var hw = hourWarning(res[2], res[3]);
    if (hw) warnings.push(hw);
    setMsg(el.warning, warnings.join(' '));
    var opMap = tasks.ok ? Core.lastOperatorByStation(tasks.ok.rows) : new Map();
    return { rows: Core.buildStationRows(stationList, people.ok || [], opMap, hourMaps(res[2], res[3])), updatedAt: clockVN(new Date()) };
  }

  // Sort: one row per Operator. Stations come from the current round hour, people from shift start to end of hour.
  async function loadSort(win, email) {
    var now = nowSec(), hour = Core.hourWindow(now), range = Core.defaultTaskRange(now);
    state.last.hour = hour;
    var stationList = await Api.fetchProductivity({ dim: 'station', from: hour.from, to: hour.to, taskType: 43, column: 'item_count', email: email });
    if (!stationList.length) {
      setMsg(el.warning, '');
      return { rows: [], updatedAt: clockVN(new Date()) };
    }
    var shiftP = soft(Api.fetchProductivity({ dim: 'individual', from: win.from, to: win.to, taskType: 43, column: 'item_count', email: email }));
    var hl = hourLists(43, email, { from: win.from, to: win.to }, shiftP);
    var res = await Promise.all([
      shiftP,
      soft(Api.fetchSortTasks({ start: range.start, end: range.end, hourStart: hour.from, wanted: Core.stationIds(stationList) })),
      hl[0], hl[1]
    ]);
    var people = res[0], tasks = res[1], warnings = [];
    if (people.err) warnings.push('Không tải được tên nhân viên (' + people.err.message + ').');
    if (tasks.err) warnings.push('Không tải được nhân viên (' + tasks.err.message + ').');
    else if (tasks.ok.partial && !tasks.ok.complete) warnings.push('Có thể thiếu thông tin nhân viên (' + tasks.ok.partial + ').');
    var hw = hourWarning(res[2], res[3]);
    if (hw) warnings.push(hw);
    setMsg(el.warning, warnings.join(' '));
    var opMap = tasks.ok ? Core.lastOperatorByStation(tasks.ok.rows) : new Map();
    return { rows: Core.buildStationRows(stationList, people.ok || [], opMap, hourMaps(res[2], res[3])), updatedAt: clockVN(new Date()) };
  }

  // Pack: one row per person.
  async function loadPack(win, email) {
    var base = { from: win.from, to: win.to, taskType: 42, email: email };
    var itemsP = soft(Api.fetchProductivity(Object.assign({ column: 'item_count' }, base)));
    var hl = hourLists(42, email, base, itemsP);
    var res = await Promise.all([
      itemsP.then(function (r) { if (r.err) throw r.err; return r.ok; }),
      Api.fetchProductivity(Object.assign({ column: 'order_count' }, base)),
      soft(Api.fetchPackTasks()),
      hl[0], hl[1]
    ]);
    var tasks = res[2], warnings = [];
    if (tasks.err) warnings.push(tasks.err.message + ' Cột Station hiển thị "-".');
    var hw = hourWarning(res[3], res[4]);
    if (hw) warnings.push(hw);
    setMsg(el.warning, warnings.join(' '));
    var map = tasks.ok ? Core.buildPackStationMap(tasks.ok) : new Map();
    return { rows: Core.mergeRows(res[0], res[1], map, hourMaps(res[3], res[4])), updatedAt: clockVN(new Date()) };
  }

  function showEmailBox(reason) {
    el.emailMsg.textContent = reason === 'empty'
      ? 'WMS chưa trả dữ liệu. Hãy mở trang Outbound productivity trên WMS rồi F5 hoặc nhập email đăng nhập tại đây.'
      : 'WMS từ chối yêu cầu. Hãy mở trang Outbound productivity rồi F5 hoặc nhập email đăng nhập tại đây.';
    el.emailBox.hidden = false;
  }

  function setBusy(on) {
    state.busy = on;
    el.start.disabled = on;
    el.start.textContent = on ? 'Đang tải…' : 'Tải dữ liệu';
  }

  async function run() {
    if (state.busy) return;
    if (state.editing && !saveTarget()) return;

    var tab = state.tab, group = groupOf(tab), email = '', interval = null;
    try { if (tab === 'Sort' || tab === 'Check') interval = intervalWindow(); }
    catch (e) { setMsg(el.banner, e.message); return; }
    Api.resetLog();
    setMsg(el.banner, '');
    setBusy(true);
    try {
      email = (await storageGet(['loginEmail'])).loginEmail || '';
      var win = Core.shiftWindow(nowSec());
      state.last = { tab: tab, hasEmail: !!email, win: win };
      renderMode();
      var result = interval ? await loadPeople(tab, interval, email) : (group === 'pack' ? await loadPack(win, email) : await loadCheck(win, email));
      state.cache[group] = result;
      if (!email && !state.cache[group].rows.length) showEmailBox('empty');
      else el.emailBox.hidden = true;
    } catch (e) {
      setMsg(el.banner, e && e.message ? e.message : 'Có lỗi xảy ra. Vui lòng thử lại.');
      if (!email && e && (e.kind === 'notjson' || e.kind === 'retcode' || (e.kind === 'http' && (e.status === 401 || e.status === 403)))) showEmailBox('refused');
    } finally {
      setBusy(false);
      render();
    }
  }

  // ---------- diagnostics ----------
  function vnTime(sec) {
    return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(sec * 1000));
  }

  function buildReport() {
    var L = Api.getLog(), last = state.last, lines = [];
    var ver = (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getManifest) ? chrome.runtime.getManifest().version : '?';
    lines.push('WMS productivity monitor ' + ver);
    lines.push('Time (VN): ' + vnTime(nowSec()) + ' | tab: ' + state.tab + ' | station names: ' + (state.namesFile || 'built-in'));
    if (!last) { lines.push('Press Start first, then open Diagnostics.'); return lines.join('\n'); }
    lines.push('Login email stored: ' + (last.hasEmail ? 'yes' : 'no'));
    lines.push('Shift: ' + vnTime(last.win.from) + ' to ' + vnTime(last.win.end) + ' (' + last.win.shift + '), asked up to end of current hour: ' + vnTime(last.win.to));
    if (last.hour) lines.push('Sort station hour: ' + vnTime(last.hour.from) + ' to ' + vnTime(last.hour.to));
    lines.push('Requests: ' + L.length);
    L.forEach(function (e, i) {
      var rng = e.meta ? ' [' + (e.meta.field || 'Time') + ' ' + vnTime(e.meta.from) + ' to ' + vnTime(e.meta.to) + ']' : '';
      lines.push((i + 1) + '. ' + e.label + rng + ' -> HTTP ' + e.status + (e.attempts > 1 ? ' (after ' + e.attempts + ' tries)' : '') +
        (e.retcode !== undefined ? ', retcode ' + e.retcode : '') +
        (e.total !== undefined && e.total !== null ? ', total ' + e.total : '') +
        (e.rows !== undefined && e.rows !== null ? ', rows ' + e.rows : '') +
        (e.message ? ', message "' + e.message + '"' : ''));
    });
    return lines.join('\n');
  }

  // ---------- events ----------
  el.diag.addEventListener('click', function () {
    var show = el.diagBox.hidden;
    el.diagBox.hidden = !show;
    if (!show) return;
    el.diagText.value = buildReport();
    el.diagText.focus(); el.diagText.select();
    try { if (navigator.clipboard) navigator.clipboard.writeText(el.diagText.value).catch(function () {}); } catch (e) { /* select-all is enough */ }
  });

  Array.prototype.forEach.call(el.tabs.children, function (b) {
    b.addEventListener('click', function () {
      state.tab = b.getAttribute('data-tab');
      lockTarget();
      el.targetError.hidden = true;
      storageSet({ tab: state.tab });
      render();
    });
  });

  el.edit.addEventListener('click', function () {
    if (!state.editing) {
      state.editing = true;
      el.target.readOnly = false;
      el.edit.textContent = 'Lưu';
      el.target.focus();
      el.target.select();
    } else if (saveTarget()) {
      render();
    }
  });

  [el.unitItem, el.unitOrder].forEach(function (b) {
    b.addEventListener('click', function () {
      if (!(isPeopleTab(state.tab) || state.tab === 'Pack') || state.busy) return;
      if (state.editing && !saveTarget()) return;
      var next = b === el.unitOrder ? 'order_count' : 'item_count';
      if (state.peopleUnit === next) return;
      state.peopleUnit = next;
      state.cache.sort = null; state.cache.check = null;
      storageSet({ peopleUnit: next });
      render();
    });
  });
  el.target.addEventListener('input', function () { el.targetError.hidden = true; });
  el.target.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && state.editing) run();
  });
  el.start.addEventListener('click', run);
  el.showAll.addEventListener('change', render);
  el.upd.addEventListener('click', function () {
    chrome.tabs.create({ url: chrome.runtime.getURL('upload.html') });
  });

  el.emailSave.addEventListener('click', async function () {
    var v = el.emailInput.value.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { el.emailError.hidden = false; return; }
    el.emailError.hidden = true;
    await storageSet({ loginEmail: v });
    el.emailInput.value = '';
    el.emailBox.hidden = true;
    run();
  });
  el.emailInput.addEventListener('input', function () { el.emailError.hidden = true; });

  Array.prototype.forEach.call(el.modeSwitch.children,function(b){b.addEventListener('click',function(){
    if(state.busy)return;state.mode=b.dataset.mode;storageSet({shiftMode:state.mode});applyPreset(state.shiftNumber);
  });});
  [el.shift1,el.shift2].forEach(function(b,i){b.addEventListener('click',function(){if(!state.busy)applyPreset(i+1);});});
  el.configureShifts.addEventListener('click',function(){
    ['BAU1','BAU2','CP1','CP2'].forEach(function(k){$('preset'+k).value=state.presets[k];});
    el.presetError.hidden=true;el.shiftSettings.hidden=!el.shiftSettings.hidden;
  });
  el.closeShifts.addEventListener('click',function(){el.shiftSettings.hidden=true;});
  el.saveShifts.addEventListener('click',function(){
    var next={},valid=true;
    ['BAU1','BAU2','CP1','CP2'].forEach(function(k){var p=validPreset($('preset'+k).value);if(!p)valid=false;else next[k]=p.normalized;});
    if(!valid){el.presetError.textContent='Hãy nhập đúng HH:mm–HH:mm (24h), giờ bắt đầu khác giờ kết thúc.';el.presetError.hidden=false;return;}
    state.presets=next;storageSet({shiftPresets:next});el.shiftSettings.hidden=true;renderMode();
  });

  // ---------- init ----------
  (async function init() {
    var s = await storageGet(['targets', 'orderTargets', 'peopleUnit', 'tab', 'stationsCustom', 'intervalPrefs', 'shiftPresets', 'shiftMode', 'shiftNumber']);
    var local = new Date(Date.now() + 7 * 3600000).toISOString().slice(0, 10);
    el.rangeDate.value = (s.intervalPrefs && s.intervalPrefs.date) || local;
    el.rangeFrom.value = (s.intervalPrefs && s.intervalPrefs.from) || '07:00';
    el.rangeFrom.addEventListener('blur', function () {
      var raw = el.rangeFrom.value.trim();
      var match = /^(\d{1,2}):(\d{1,2})$/.exec(raw);
      if (match && +match[1] < 24 && +match[2] < 60) el.rangeFrom.value = match[1].padStart(2, '0') + ':' + match[2].padStart(2, '0');
    });
    el.rangeTo.value = (s.intervalPrefs && s.intervalPrefs.to) || 'now';
    [el.rangeDate, el.rangeFrom, el.rangeTo].forEach(function (input) { input.addEventListener('change', function () {
      storageSet({ intervalPrefs: { date: el.rangeDate.value, from: el.rangeFrom.value, to: el.rangeTo.value } });
      state.cache.sort = null; state.cache.check = null; render();
    }); });
    if (s.peopleUnit === 'order_count' || s.peopleUnit === 'item_count') state.peopleUnit = s.peopleUnit;
    if (s.orderTargets) ['Sort', 'Check', 'Pack'].forEach(function (t) { var v = Number(s.orderTargets[t]); if (v > 0) state.orderTargets[t] = v; });
    if (s.targets) {
      TABS.forEach(function (t) {
        var v = Number(s.targets[t]);
        if (v > 0) state.targets[t] = v;
      });
    }
    if (TABS.indexOf(s.tab) >= 0) state.tab = s.tab;
    if (s.stationsCustom && s.stationsCustom.CS && s.stationsCustom.PS) {
      Core.setStations({ CS: s.stationsCustom.CS, PS: s.stationsCustom.PS, SS: s.stationsCustom.SS });
      state.namesFile = s.stationsCustom.fileName || 'custom file';
    }
    if(s.shiftPresets){['BAU1','BAU2','CP1','CP2'].forEach(function(k){var v=validPreset(s.shiftPresets[k]);if(v)state.presets[k]=v.normalized;});}
    if(s.shiftMode==='BAU'||s.shiftMode==='CP')state.mode=s.shiftMode;
    if(s.shiftNumber===1||s.shiftNumber===2)state.shiftNumber=s.shiftNumber;
    renderMode();
    render();
  })();
})();
