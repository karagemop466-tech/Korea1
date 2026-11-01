
// Minimal, dependency-free table tools: click a header to sort, type in .filter to search.
document.querySelectorAll('table').forEach(function (t) {
  var head = t.querySelectorAll('thead th');
  head.forEach(function (th, i) {
    th.style.cursor = 'pointer';
    th.title = 'Click to sort';
    th.addEventListener('click', function () {
      var body = t.tBodies[0];
      var rows = Array.prototype.slice.call(body.rows);
      var dir = th.dataset.dir === 'asc' ? -1 : 1;
      th.dataset.dir = dir === 1 ? 'asc' : 'desc';
      rows.sort(function (a, b) {
        var x = a.cells[i] ? a.cells[i].innerText.trim() : '';
        var y = b.cells[i] ? b.cells[i].innerText.trim() : '';
        var nx = parseFloat(x.replace(/[%+,]/g, ''));
        var ny = parseFloat(y.replace(/[%+,]/g, ''));
        if (!isNaN(nx) && !isNaN(ny)) return (nx - ny) * dir;
        return x.localeCompare(y) * dir;
      });
      rows.forEach(function (r) { body.appendChild(r); });
    });
  });
});
