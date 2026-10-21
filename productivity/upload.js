(function () {
  'use strict';

  var KEY = 'stationsCustom';
  var $ = function (id) { return document.getElementById(id); };
  var el = { current: $('current'), file: $('file'), drop: $('drop'), error: $('error'), result: $('result'), reset: $('reset') };

  function get() { return new Promise(function (res) { chrome.storage.local.get([KEY], function (s) { res(s[KEY] || null); }); }); }
  function set(v) { return new Promise(function (res) { chrome.storage.local.set({ stationsCustom: v }, res); }); }
  function clear() { return new Promise(function (res) { chrome.storage.local.remove(KEY, res); }); }

  function line(parent, k, v) {
    var p = document.createElement('p');
    var a = document.createElement('span'); a.className = 'k'; a.textContent = k + ' ';
    p.appendChild(a); p.appendChild(document.createTextNode(v));
    parent.appendChild(p);
  }

  function fmtTime(ms) {
    return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(ms));
  }

  async function showCurrent() {
    var c = await get();
    el.current.textContent = '';
    if (c) {
      line(el.current, 'Đang dùng:', c.fileName || 'file đã tải lên');
      line(el.current, 'Số Station:', c.cs + ' CS codes, ' + c.ps + ' PS codes, ' + (c.ss === undefined ? 'no SS codes (built-in Sort names are used)' : c.ss + ' SS codes'));
      line(el.current, 'Đã tải:', fmtTime(c.loadedAt));
    } else {
      line(el.current, 'Đang dùng:', 'bảng mặc định');
    }
    el.reset.hidden = !c;
  }

  function showError(text) {
    el.error.textContent = text;
    el.error.hidden = false;
    el.result.hidden = true;
  }

  function msg(cls, text) {
    var p = document.createElement('p');
    p.className = 'msg ' + cls; p.textContent = text;
    return p;
  }

  function showResult(name, stats) {
    el.error.hidden = true;
    el.result.textContent = '';
    el.result.appendChild(msg('ok', 'Loaded ' + (stats.cs + stats.ps + stats.ss) + ' stations (' + stats.cs + ' CS, ' + stats.ps + ' PS, ' + stats.ss + ' SS) from ' + name + '.'));
    var warn = [];
    if (stats.cs === 0) warn.push('Không tìm thấy mã CS: tên Station trong Check và Check&Pack sẽ hiện "-".');
    if (stats.ps === 0) warn.push('Không tìm thấy mã PS: tên Station trong Pack sẽ hiện "-".');
    if (stats.ss === 0) warn.push('Không tìm thấy mã SS: tên Station trong Sort sẽ hiện "-".');
    warn.forEach(function (w) { el.result.appendChild(msg('warn', w)); });

    var notes = [];
    if (stats.skipped.length) {
      var first = stats.skipped.slice(0, 5).map(function (s) { return 'row ' + s.row + ' ("' + s.text + '")'; }).join(', ');
      notes.push('Skipped ' + stats.skipped.length + ' row' + (stats.skipped.length > 1 ? 's' : '') +
        ' without a CS/PS code in column A or without a name: ' + first + (stats.skipped.length > 5 ? ', …' : ''));
    }
    if (stats.duplicates) notes.push(stats.duplicates + ' repeated ID' + (stats.duplicates > 1 ? 's' : '') + ' ignored (the first row is used).');
    if (notes.length) {
      var ul = document.createElement('ul');
      notes.forEach(function (n) { var li = document.createElement('li'); li.textContent = n; ul.appendChild(li); });
      el.result.appendChild(ul);
    }
    el.result.hidden = false;
  }

  function readBuffer(file) {
    if (file.arrayBuffer) return file.arrayBuffer();
    return new Promise(function (res, rej) {
      var r = new FileReader();
      r.onload = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
      r.readAsArrayBuffer(file);
    });
  }

  async function handle(file) {
    if (!file) return;
    if (!/\.xlsx$/i.test(file.name)) { showError('Vui lòng chọn file Excel .xlsx và thử lại.'); return; }
    var rows;
    try { rows = await WMSXlsx.parseXlsx(await readBuffer(file)); }
    catch (e) { showError('Không đọc được file. Hãy lưu lại dưới dạng .xlsx và thử lại.'); return; }

    var built = WMSXlsx.buildStationTable(rows);
    if (!built.stats.cs && !built.stats.ps && !built.stats.ss) {
      showError('Không tìm thấy Station. Cột A cần là Station ID, cột B là tên Station trong sheet đầu tiên. Dữ liệu đang dùng chưa bị thay đổi.');
      return;
    }
    await set({ CS: built.table.CS, PS: built.table.PS, SS: built.table.SS, fileName: file.name, loadedAt: Date.now(), cs: built.stats.cs, ps: built.stats.ps, ss: built.stats.ss });
    showResult(file.name, built.stats);
    showCurrent();
  }

  el.file.addEventListener('change', function () { handle(el.file.files[0]); el.file.value = ''; });
  el.drop.addEventListener('dragover', function (e) { e.preventDefault(); el.drop.classList.add('over'); });
  el.drop.addEventListener('dragleave', function () { el.drop.classList.remove('over'); });
  el.drop.addEventListener('drop', function (e) {
    e.preventDefault(); el.drop.classList.remove('over');
    handle(e.dataTransfer && e.dataTransfer.files[0]);
  });
  el.reset.addEventListener('click', async function () {
    await clear();
    el.error.hidden = true;
    el.result.textContent = '';
    el.result.appendChild(msg('ok', 'Back to the built-in table.'));
    el.result.hidden = false;
    showCurrent();
  });

  showCurrent();
})();
