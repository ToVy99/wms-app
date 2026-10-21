(function (root) {
  'use strict';

  var VN_OFFSET = 7 * 3600;
  var DEFAULT_TARGETS = { 'Sort': 270, 'Check': 270, 'Check Station': 270, 'Check&Pack': 60, 'Pack': 55 };
  var override = null;

  function builtin() {
    if (typeof STATIONS !== 'undefined') return STATIONS;
    if (typeof require === 'function') return require('./stations.js');
    return { CS: {}, PS: {} };
  }
  function stations() { return override || builtin(); }

  // Replace the lookup table (from an uploaded Excel file). Pass null to go back to the built-in table.
  // A table saved before Sort existed has no SS key: keep the built-in Sort names for it.
  function setStations(t) {
    override = t ? { CS: t.CS || {}, PS: t.PS || {}, SS: t.SS !== undefined ? t.SS : (builtin().SS || {}) } : null;
  }

  // ---- time (Vietnam time, UTC+7, no DST) ----
  function vnParts(nowSec) {
    var d = new Date((nowSec + VN_OFFSET) * 1000);
    return { y: d.getUTCFullYear(), mo: d.getUTCMonth(), d: d.getUTCDate(), h: d.getUTCHours() };
  }
  function vnToUnix(y, mo, d, h) {
    return Date.UTC(y, mo, d, h, 0, 0) / 1000 - VN_OFFSET;
  }

  // The round hour we are in: 16:29 -> 16:00:00 to 16:59:59 (Sort stations).
  function hourWindow(nowSec) {
    var p = vnParts(nowSec), from = vnToUnix(p.y, p.mo, p.d, p.h);
    return { from: from, to: from + 3599 };
  }

  // H-1 = the round hour before this one, H = the round hour we are in (WMS only has data up to now).
  // 05:30 -> H-1 = 04:00:00 to 04:59:59, H = 05:00:00 to 05:59:59.
  function hourWindows(nowSec) {
    var cur = hourWindow(nowSec);
    return { prev: { from: cur.from - 3600, to: cur.from - 1 }, cur: cur };
  }

  // WMS default range of the task lists: today and the 6 days before, 00:00 to 23:59:59.
  function defaultTaskRange(nowSec) {
    var p = vnParts(nowSec);
    return { start: vnToUnix(p.y, p.mo, p.d - 6, 0), end: vnToUnix(p.y, p.mo, p.d, 0) + 86399 };
  }

  // Morning 06:00-18:00, night 18:00-06:00.
  // to = end of the current hour (Pack), end = end of the whole shift (Check and Check&Pack).
  function shiftWindow(nowSec) {
    var p = vnParts(nowSec), from, shift;
    if (p.h >= 6 && p.h < 18) { from = vnToUnix(p.y, p.mo, p.d, 6); shift = 'morning'; }
    else if (p.h >= 18) { from = vnToUnix(p.y, p.mo, p.d, 18); shift = 'night'; }
    else { from = vnToUnix(p.y, p.mo, p.d - 1, 18); shift = 'night'; }
    return { from: from, to: vnToUnix(p.y, p.mo, p.d, p.h) + 3599, end: from + 12 * 3600 - 1, shift: shift };
  }

  // ---- stations ----
  function norm(email) { return typeof email === 'string' ? email.trim().toLowerCase() : ''; }
  function normId(id) { return typeof id === 'string' ? id.trim().toUpperCase() : ''; }

  function stationNumber(id) {
    var m = /(\d{5})$/.exec(typeof id === 'string' ? id.trim() : '');
    return m ? parseInt(m[1], 10) : null;
  }

  // Last 5 digits >= 500 -> Check&Pack, otherwise Check.
  function areaOf(stationId) {
    var n = stationNumber(stationId);
    return n !== null && n >= 500 ? 'Check&Pack' : 'Check';
  }

  function lookupStation(id) {
    var key = normId(id);
    var m = /^(CS|PS|SS)\d{5}$/.exec(key);
    if (!m) return null;
    var v = (stations()[m[1]] || {})[key];
    return v === undefined || v === '' ? null : v;
  }

  function firstStation(task) {
    if (task.checking_station_id) return task.checking_station_id;
    if (Array.isArray(task.station_id)) return task.station_id[0] || '';
    return task.station_id || '';
  }

  function num(v) { var n = Number(v); return isFinite(n) && v !== null && v !== '' ? n : null; }

  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  // email -> productivity (Items) of one round hour, from an individual productivity list
  function hourMap(list) {
    var m = new Map();
    (list || []).forEach(function (p) {
      var e = norm(p.staff_email);
      if (e && !m.has(e)) m.set(e, num(p.productivity));
    });
    return m;
  }
  function hourOf(map, email) {
    var e = norm(email);
    return map && e && map.has(e) ? map.get(e) : null;
  }

  // A value fails when it is a number below the target. "-" (no data) is never a failure.
  function failFlags(vals, target) {
    return vals.map(function (v) { return isNum(v) && v < target; });
  }
  function failCount(vals, target) {
    return failFlags(vals, target).filter(Boolean).length;
  }

  // Keep the rows that fail at least one of [whole shift, H-1, H]; most failures first, then the lowest
  // whole-shift Prod, then the tie key. One row per staff, however many of the three fail.
  function rankBelow(rows, getVals, target, tieKey) {
    var out = rows.filter(function (r) { return failCount(getVals(r), target) > 0; });
    out.sort(function (a, b) {
      var d = failCount(getVals(b), target) - failCount(getVals(a), target);
      if (d) return d;
      var va = getVals(a)[0], vb = getVals(b)[0];
      var x = isNum(va) ? va : Infinity, y = isNum(vb) ? vb : Infinity;
      if (x !== y) return x - y;
      return String(tieKey(a)).localeCompare(String(tieKey(b)));
    });
    return out;
  }
  function stationVals(r) { return [r.staffProd, r.hPrev, r.hCur]; }
  function hasAny(vals) { return vals.some(isNum); }

  // ---- Check and Check&Pack: one row per station ----

  // Completed tasks -> for every station, the operator who finished a task closest to now
  // (complete_time for checking tasks, done_time for sorting tasks).
  function lastOperatorByStation(tasks) {
    var map = new Map();
    (tasks || []).forEach(function (t) {
      var sid = normId(t.checked_station_id || firstStation(t)), email = norm(t.operator);
      if (!sid || !email) return;
      var ts = t.done_time || t.complete_time || t.ongoing_time || t.ctime || 0;
      var cur = map.get(sid);
      if (!cur || ts > cur.t) map.set(sid, { email: email, rawEmail: t.operator, t: ts });
    });
    return map;
  }

  function buildStationRows(stationList, people, opMap, hours) {
    var pm = new Map();
    (people || []).forEach(function (p) {
      var e = norm(p.staff_email);
      if (e && !pm.has(e)) pm.set(e, {
        name: p.local_staff_name || p.staff_name || '', email: p.staff_email,
        prod: num(p.productivity), mh: num(p.man_hour)
      });
    });
    var seen = new Set(), rows = [];
    (stationList || []).forEach(function (s) {
      var id = normId(s.station_id);
      if (!id || seen.has(id)) return;
      seen.add(id);
      var op = opMap.get(id), info = op ? pm.get(op.email) : null;
      rows.push({
        stationId: id,
        stationName: lookupStation(id),
        prod: num(s.productivity) || 0,
        manHour: num(s.man_hour),
        items: num(s.sum_count),
        operatorEmail: op ? (info ? info.email : op.rawEmail) : null,
        operatorName: info && info.name ? info.name : null,
        staffProd: info ? info.prod : null,
        staffMh: info ? info.mh : null,
        hPrev: op && hours ? hourOf(hours.prev, op.email) : null,
        hCur: op && hours ? hourOf(hours.cur, op.email) : null
      });
    });
    return rows;
  }

  // The target is the Operator's own Prod (Items), not the station's. It is compared with three numbers:
  // the whole shift, H-1 and H. A station is listed when its Operator fails at least one of them.
  // A station whose Operator has none of the three cannot be compared: it is left out and counted as hidden.
  function filterStationRows(rows, tab, target) {
    return rankBelow(rows.filter(function (r) { return areaOf(r.stationId) === tab; }), stationVals, target,
      function (r) { return r.stationId; });
  }

  // total = stations in this tab with an Operator who has numbers, hidden = stations without
  function countStations(rows, tab) {
    var inTab = rows.filter(function (r) { return areaOf(r.stationId) === tab; });
    var total = inTab.filter(function (r) { return hasAny(stationVals(r)); }).length;
    return { total: total, hidden: inTab.length - total };
  }

  function stationIds(stationList) {
    var out = [];
    (stationList || []).forEach(function (s) {
      var id = normId(s.station_id);
      if (id && out.indexOf(id) < 0) out.push(id);
    });
    return out;
  }

  // ---- Sort: one row per Operator, with every station they last worked at ----
  // Stations whose Operator has no numbers cannot be compared with the target: they are counted in `hidden`.
  function groupByOperator(rows) {
    var by = new Map(), hidden = 0;
    (rows || []).forEach(function (r) {
      if (!r.operatorEmail || !hasAny(stationVals(r))) { hidden++; return; }
      var key = norm(r.operatorEmail), p = by.get(key);
      if (!p) {
        p = { email: r.operatorEmail, name: r.operatorName, staffProd: r.staffProd, staffMh: r.staffMh, hPrev: r.hPrev, hCur: r.hCur, stations: [] };
        by.set(key, p);
      }
      p.stations.push({ stationId: r.stationId, stationName: r.stationName, prod: r.prod, manHour: r.manHour, items: r.items });
    });
    var persons = Array.from(by.values());
    persons.forEach(function (p) { p.stations.sort(function (a, b) { return a.stationId.localeCompare(b.stationId); }); });
    return { persons: persons, hidden: hidden };
  }

  function filterSortPersons(persons, target) {
    return rankBelow(persons, stationVals, target, function (p) { return p.name || p.email; });
  }

  // ---- Pack: one row per person (unchanged) ----

  // Every email in task.list; operator only when that email is in no task's list. Latest task wins.
  function buildPackStationMap(tasks) {
    var map = new Map(), inList = new Set();
    function put(email, sid, ts) {
      var cur = map.get(email);
      if (!cur || ts > cur.t) map.set(email, { stationId: sid, t: ts });
    }
    (tasks || []).forEach(function (t) {
      var sid = firstStation(t), ts = t.start_time || t.ctime || 0;
      if (!sid) return;
      (t.list || []).forEach(function (m) {
        var e = norm(m.email);
        if (e) { inList.add(e); put(e, sid, ts); }
      });
    });
    (tasks || []).forEach(function (t) {
      var sid = firstStation(t), ts = t.start_time || t.ctime || 0, e = norm(t.operator);
      if (sid && e && !inList.has(e)) put(e, sid, ts);
    });
    return map;
  }

  function mergeRows(items, orders, stationMap, hours) {
    var ord = new Map();
    (orders || []).forEach(function (o) {
      var e = norm(o.staff_email);
      if (e && !ord.has(e)) ord.set(e, num(o.productivity));
    });
    var seen = new Set(), rows = [];
    (items || []).forEach(function (it) {
      var e = norm(it.staff_email);
      if (!e || seen.has(e)) return;
      seen.add(e);
      var st = stationMap.get(e);
      rows.push({
        name: it.local_staff_name || it.staff_name || it.staff_email,
        email: it.staff_email,
        items: num(it.productivity) || 0,
        orders: ord.has(e) ? ord.get(e) : null,
        manHour: num(it.man_hour),
        stationId: st ? st.stationId : null,
        stationName: st ? lookupStation(st.stationId) : null,
        hPrev: hours ? hourOf(hours.prev, e) : null,
        hCur: hours ? hourOf(hours.cur, e) : null
      });
    });
    return rows;
  }

  function packVals(r) { return [r.items, r.hPrev, r.hCur]; }
  function filterPackRows(rows, target) {
    return rankBelow(rows, packVals, target, function (r) { return r.name; });
  }

  var api = {
    DEFAULT_TARGETS: DEFAULT_TARGETS, setStations: setStations, shiftWindow: shiftWindow,
    hourWindow: hourWindow, hourWindows: hourWindows, hourMap: hourMap, failFlags: failFlags,
    defaultTaskRange: defaultTaskRange, stationIds: stationIds,
    groupByOperator: groupByOperator, filterSortPersons: filterSortPersons,
    stationNumber: stationNumber, areaOf: areaOf, lookupStation: lookupStation, norm: norm,
    lastOperatorByStation: lastOperatorByStation, buildStationRows: buildStationRows,
    filterStationRows: filterStationRows, countStations: countStations,
    buildPackStationMap: buildPackStationMap, mergeRows: mergeRows, filterPackRows: filterPackRows
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.WMSCore = api;
})(typeof self !== 'undefined' ? self : this);
