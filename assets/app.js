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
}());
