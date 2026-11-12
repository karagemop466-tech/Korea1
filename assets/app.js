/* Dependency-free, progressive enhancement. Tables remain readable without JS. */
(function () {
  'use strict';
  document.querySelectorAll('table').forEach(function (table) {
    var body = table.tBodies[0];
    if (!body) return;
    var original = Array.from(body.rows);
    var headers = Array.from(table.querySelectorAll('thead th'));
    headers.forEach(function (th, index) {
      th.tabIndex = 0;
      th.setAttribute('aria-sort', 'none');
      th.title = 'Sort this column';
      function sort() {
        var direction = th.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
        headers.forEach(function (h) { h.setAttribute('aria-sort', 'none'); });
        th.setAttribute('aria-sort', direction === 1 ? 'ascending' : 'descending');
        var rows = Array.from(body.rows);
        rows.sort(function (a, b) {
          var x = (a.cells[index] || {}).textContent || '';
          var y = (b.cells[index] || {}).textContent || '';
          x = x.trim(); y = y.trim();
          var nx = Number(x.replace(/[%+,]/g, ''));
          var ny = Number(y.replace(/[%+,]/g, ''));
          if (x && y && Number.isFinite(nx) && Number.isFinite(ny)) return (nx - ny) * direction;
          return x.localeCompare(y, undefined, {numeric: true}) * direction;
        });
        rows.forEach(function (row) { body.appendChild(row); });
      }
      th.addEventListener('click', sort);
      th.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); sort(); }
      });
    });
    var section = table.closest('section') || table.parentElement.parentElement;
    var input = section.querySelector('.filter');
    if (input) {
      input.setAttribute('aria-label', 'Filter the table on this page');
      input.addEventListener('input', function () {
        var query = input.value.toLocaleLowerCase().trim();
        original.forEach(function (row) { row.hidden = query !== '' && !row.textContent.toLocaleLowerCase().includes(query); });
      });
    }
  });

  /* Reviewer path-selection preview on suggestions-review.html (browser-only; never mutates repo). */
  var pickers = Array.from(document.querySelectorAll('.path-picker'));
  var output = document.getElementById('path-selection-output');
  if (pickers.length && output) {
    var storageKey = 'nfl_line_lab_path_choices_v1';
    var saved = {};
    try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}') || {}; } catch (e) { saved = {}; }
    function syncSummary() {
      var choices = {};
      var chosenCount = 0;
      pickers.forEach(function (p) {
        var id = p.getAttribute('data-sug-id');
        var sel = p.querySelector('.path-select');
        var val = sel ? sel.value : 'Pending review';
        choices[id] = val;
        if (val !== 'Pending review') chosenCount += 1;
      });
      try { localStorage.setItem(storageKey, JSON.stringify(choices)); } catch (e) {}
      var summary = Object.keys(choices).map(function (k) { return k + ': ' + choices[k]; }).join(' · ');
      output.textContent = 'Reviewer status (' + chosenCount + '/' + pickers.length + ' decided, preview only — 0 repo changes applied): ' + summary;
      return choices;
    }
    pickers.forEach(function (p) {
      var id = p.getAttribute('data-sug-id');
      var sel = p.querySelector('.path-select');
      if (sel && saved[id]) sel.value = saved[id];
      if (sel) sel.addEventListener('change', syncSummary);
    });
    var btnRec = document.getElementById('apply-recommended-paths');
    var btnReset = document.getElementById('reset-paths');
    var btnExport = document.getElementById('export-paths');
    if (btnRec) btnRec.addEventListener('click', function () {
      pickers.forEach(function (p) {
        var sel = p.querySelector('.path-select');
        if (sel) sel.value = p.getAttribute('data-recommended') || 'Path B';
      });
      syncSummary();
    });
    if (btnReset) btnReset.addEventListener('click', function () {
      pickers.forEach(function (p) {
        var sel = p.querySelector('.path-select');
        if (sel) sel.value = 'Pending review';
      });
      syncSummary();
    });
    if (btnExport) btnExport.addEventListener('click', function () {
      var payload = JSON.stringify({reviewed_utc: new Date().toISOString(), decisions: syncSummary()}, null, 2);
      output.textContent = payload;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(payload).catch(function () {});
      }
    });
    syncSummary();
  }
}());
