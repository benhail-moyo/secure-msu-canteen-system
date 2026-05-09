(function() {
  const html = document.documentElement;
  const toggle = document.getElementById('themeToggle');

  // Get saved theme or default to 'light'
  function getSavedTheme() {
    return localStorage.getItem('theme') || 'light';
  }

  // Apply theme to document
  function applyTheme(theme) {
    if (theme === 'dark') {
      html.setAttribute('data-theme', 'dark');
    } else {
      html.removeAttribute('data-theme');
    }
    updateIcon(theme);
  }

  // Update toggle icon
  function updateIcon(theme) {
    const icon = toggle.querySelector('i');
    if (theme === 'dark') {
      icon.className = 'fas fa-moon';
    } else {
      icon.className = 'fas fa-sun';
    }
  }

  // Initialize theme on page load
  function initTheme() {
    const saved = getSavedTheme();
    applyTheme(saved);
  }

  // Handle toggle click
  function handleToggle() {
    const current = html.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    const next = current === 'dark' ? 'light' : 'dark';

    // Add rotation animation
    toggle.classList.add('switching');
    setTimeout(() => {
      toggle.classList.remove('switching');
    }, 500);

    applyTheme(next);
    localStorage.setItem('theme', next);
  }

  // Attach event listener
  if (toggle) {
    toggle.addEventListener('click', handleToggle);
  }

  // Apply theme immediately to prevent flash
  initTheme();
})();
