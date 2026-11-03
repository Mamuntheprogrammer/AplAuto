/* Search boxes above the big tables. Filters rows by ID, name, depot or territory. */
document.querySelectorAll('.search').forEach(function (box) {
  var section = box.closest('.block');
  var rows = Array.prototype.slice.call(section.querySelectorAll('tbody tr'));
  var counter = section.querySelector('.count');
  var total = rows.length;
  box.addEventListener('input', function () {
    var q = box.value.trim().toLowerCase(), shown = 0;
    rows.forEach(function (r) {
      var text = [0, 1, 3, 4].map(function (i) { return r.cells[i].textContent; }).join(' ').toLowerCase();
      var hit = !q || text.indexOf(q) > -1;
      r.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    counter.textContent = q ? shown + ' of ' + total + ' records' : total + ' records';
  });
});
