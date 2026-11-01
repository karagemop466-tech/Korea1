
// Client-side sorting for every table: click a header to sort, click again to reverse.
document.querySelectorAll('table').forEach(function (table) {
  var headers = table.querySelectorAll('thead th');
  headers.forEach(function (th, idx) {
    th.style.cursor = 'pointer';
    th.title = 'Click to sort';
    var dir = 1;
    th.addEventListener('click', function () {
      var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));
      rows.sort(function (a, b) {
        var av = a.children[idx] ? a.children[idx].innerText.trim() : '';
        var bv = b.children[idx] ? b.children[idx].innerText.trim() : '';
        var an = parseFloat(av.replace(/[^0-9.\-+]/g, ''));
        var bn = parseFloat(bv.replace(/[^0-9.\-+]/g, ''));
        var bothNumeric = !isNaN(an) && !isNaN(bn);
        if (bothNumeric) return (an - bn) * dir;
        return av.localeCompare(bv) * dir;
      });
      dir = -dir;
      var tb = table.querySelector('tbody');
      rows.forEach(function (r) { tb.appendChild(r); });
    });
  });
});
