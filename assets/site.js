(() => {
  const toggle = document.querySelector('[data-menu-toggle]');
  const nav = document.getElementById('primary-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      nav.classList.toggle('is-open', open);
    });
    nav.addEventListener('click', (event) => {
      if (event.target.closest('a') && window.matchMedia('(max-width: 850px)').matches) {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  document.querySelectorAll('[data-table-filter]').forEach((input) => {
    const table = document.getElementById(input.getAttribute('aria-controls'));
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    input.addEventListener('input', () => {
      const query = input.value.trim().toLocaleLowerCase();
      rows.forEach((row) => {
        row.hidden = query !== '' && !row.textContent.toLocaleLowerCase().includes(query);
      });
    });
  });
})();
