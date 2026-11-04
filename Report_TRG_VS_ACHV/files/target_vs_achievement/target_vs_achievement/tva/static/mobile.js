/* Mobile report: level tabs, search, sort and "show more" paging.
   Only PAGE cards are visible at a time, so very large teams stay fast. */
(function () {
  var PAGE = 25;
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
  var panels = Array.prototype.slice.call(document.querySelectorAll('.panel'));
  var box = document.getElementById('q');
  var sortSel = document.getElementById('sort');
  if (!tabs.length) return;

  var state = {};   // per panel: how many cards are currently allowed to show
  panels.forEach(function (p) { state[p.id] = PAGE; });

  var SORTS = {
    'ach-desc':    function (a, b) { return +b.dataset.ach - +a.dataset.ach; },
    'ach-asc':     function (a, b) { return +a.dataset.ach - +b.dataset.ach; },
    'target-desc': function (a, b) { return +b.dataset.target - +a.dataset.target; },
    'sales-desc':  function (a, b) { return +b.dataset.sales - +a.dataset.sales; },
    'name-asc':    function (a, b) { return a.dataset.name < b.dataset.name ? -1 : a.dataset.name > b.dataset.name ? 1 : 0; }
  };

  function active() { return panels.filter(function (p) { return !p.hidden; })[0]; }

  function apply(panel, resetPaging) {
    if (resetPaging) state[panel.id] = PAGE;
    var list = panel.querySelector('.list');
    var cards = Array.prototype.slice.call(list.children);
    cards.sort(SORTS[sortSel.value] || SORTS['ach-desc']);
    cards.forEach(function (c) { list.appendChild(c); });

    var q = box.value.trim().toLowerCase();
    var matches = 0, shown = 0;
    cards.forEach(function (c) {
      var hit = !q || c.dataset.s.indexOf(q) > -1;
      if (hit) matches++;
      var visible = hit && matches <= state[panel.id];
      c.hidden = !visible;
      if (visible) shown++;
    });

    var info = panel.querySelector('.shown');
    info.textContent = matches === 0 ? 'No matches' :
      'Showing ' + shown + ' of ' + matches + (q ? ' matches' : '');
    var more = panel.querySelector('.more');
    var left = matches - shown;
    more.hidden = left <= 0;
    more.textContent = 'Show ' + Math.min(PAGE, left) + ' more (' + left + ' left)';
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () {
      tabs.forEach(function (x) { x.setAttribute('aria-selected', x === t ? 'true' : 'false'); });
      panels.forEach(function (p) { p.hidden = p.id !== t.dataset.target; });
      apply(active(), false);
    });
  });
  panels.forEach(function (p) {
    p.querySelector('.more').addEventListener('click', function () {
      state[p.id] += PAGE;
      apply(p, false);
    });
  });
  box.addEventListener('input', function () { apply(active(), true); });
  sortSel.addEventListener('change', function () { apply(active(), true); });

  panels.forEach(function (p) { apply(p, true); });
})();
