// Minimal .xlsx reader (no libraries): reads columns A and B of the first sheet.
(function (root) {
  'use strict';

  function u16(v, o) { return v.getUint16(o, true); }
  function u32(v, o) { return v.getUint32(o, true); }

  function readZip(buf) {
    var bytes = new Uint8Array(buf), v = new DataView(buf), n = bytes.length, eocd = -1;
    for (var i = n - 22; i >= Math.max(0, n - 65557); i--) {
      if (u32(v, i) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('not a zip file');
    var count = u16(v, eocd + 10), p = u32(v, eocd + 16), entries = {};
    for (var k = 0; k < count; k++) {
      if (u32(v, p) !== 0x02014b50) throw new Error('bad zip directory');
      var method = u16(v, p + 10), csize = u32(v, p + 20), nlen = u16(v, p + 28),
          elen = u16(v, p + 30), clen = u16(v, p + 32), off = u32(v, p + 42);
      var name = new TextDecoder('utf-8').decode(bytes.subarray(p + 46, p + 46 + nlen));
      entries[name] = { method: method, csize: csize, off: off };
      p += 46 + nlen + elen + clen;
    }
    return { bytes: bytes, view: v, entries: entries };
  }

  async function inflateRaw(data) {
    var ds = new DecompressionStream('deflate-raw');
    var w = ds.writable.getWriter();
    w.write(data); w.close();
    var r = ds.readable.getReader(), chunks = [], total = 0;
    while (true) {
      var x = await r.read();
      if (x.done) break;
      chunks.push(x.value); total += x.value.length;
    }
    var out = new Uint8Array(total), pos = 0;
    chunks.forEach(function (c) { out.set(c, pos); pos += c.length; });
    return out;
  }

  async function readEntry(zip, name) {
    var e = zip.entries[name];
    if (!e) return null;
    var v = zip.view, o = e.off;
    if (u32(v, o) !== 0x04034b50) throw new Error('bad zip entry');
    var start = o + 30 + u16(v, o + 26) + u16(v, o + 28);
    var data = zip.bytes.subarray(start, start + e.csize);
    var raw = e.method === 0 ? data : await inflateRaw(data);
    return new TextDecoder('utf-8').decode(raw);
  }

  function textOf(node) {
    var ts = node.getElementsByTagName('t'), s = '';
    for (var i = 0; i < ts.length; i++) s += ts[i].textContent;
    return s;
  }

  // -> [{ row, a, b }] for every row that has something in A or B
  async function parseXlsx(buf, opts) {
    var Parser = (opts && opts.DOMParser) || root.DOMParser;
    var parse = function (s) { return new Parser().parseFromString(s, 'application/xml'); };
    var zip = readZip(buf);

    var sheetPath = 'xl/worksheets/sheet1.xml';
    var wb = await readEntry(zip, 'xl/workbook.xml'), rels = await readEntry(zip, 'xl/_rels/workbook.xml.rels');
    if (wb && rels) {
      var sheet = parse(wb).getElementsByTagName('sheet')[0];
      var rid = sheet && (sheet.getAttribute('r:id') || sheet.getAttribute('id'));
      var rs = parse(rels).getElementsByTagName('Relationship');
      for (var i = 0; i < rs.length; i++) {
        if (rs[i].getAttribute('Id') === rid) {
          var t = rs[i].getAttribute('Target');
          sheetPath = t.charAt(0) === '/' ? t.slice(1) : 'xl/' + t;
        }
      }
    }
    var sheetXml = await readEntry(zip, sheetPath);
    if (!sheetXml) throw new Error('sheet not found');

    var shared = [], ssXml = await readEntry(zip, 'xl/sharedStrings.xml');
    if (ssXml) {
      var sis = parse(ssXml).getElementsByTagName('si');
      for (var s = 0; s < sis.length; s++) shared.push(textOf(sis[s]));
    }

    var cells = parse(sheetXml).getElementsByTagName('c'), rows = new Map();
    for (var c = 0; c < cells.length; c++) {
      var cell = cells[c], ref = /^([A-Z]+)(\d+)$/.exec(cell.getAttribute('r') || '');
      if (!ref || (ref[1] !== 'A' && ref[1] !== 'B')) continue;
      var type = cell.getAttribute('t'), vEl = cell.getElementsByTagName('v')[0], val = '';
      if (type === 'inlineStr') val = textOf(cell);
      else if (type === 's') val = vEl ? (shared[parseInt(vEl.textContent, 10)] || '') : '';
      else val = vEl ? vEl.textContent : '';
      var rn = parseInt(ref[2], 10), r = rows.get(rn) || { row: rn, a: '', b: '' };
      r[ref[1].toLowerCase()] = String(val).trim();
      rows.set(rn, r);
    }
    return Array.from(rows.values()).filter(function (r) { return r.a || r.b; }).sort(function (x, y) { return x.row - y.row; });
  }

  // Column A = Station ID (CS00000 / PS00000 / SS00000), column B = name taken exactly as written.
  // A repeated ID keeps its first row. Rows that don't fit are skipped and reported.
  function buildStationTable(rows) {
    var CS = {}, PS = {}, SS = {}, skipped = [], duplicates = 0;
    rows.forEach(function (r) {
      var id = r.a.toUpperCase(), m = /^(CS|PS|SS)\d{5}$/.exec(id);
      if (!m || !r.b) { skipped.push({ row: r.row, text: r.a || r.b }); return; }
      var t = m[1] === 'CS' ? CS : (m[1] === 'PS' ? PS : SS);
      if (Object.prototype.hasOwnProperty.call(t, id)) { duplicates++; return; }
      t[id] = r.b;
    });
    return {
      table: { CS: CS, PS: PS, SS: SS },
      stats: { cs: Object.keys(CS).length, ps: Object.keys(PS).length, ss: Object.keys(SS).length, skipped: skipped, duplicates: duplicates }
    };
  }

  var api = { parseXlsx: parseXlsx, buildStationTable: buildStationTable };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.WMSXlsx = api;
})(typeof self !== 'undefined' ? self : this);
