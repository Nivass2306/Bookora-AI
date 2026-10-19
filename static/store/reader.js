document.addEventListener('DOMContentLoaded', () => {
  const content = document.querySelector('[data-reader-content]');
  if (!content) return;
  const storageKey = `bookora-reader-${location.pathname}`;
  const setSize = (size) => {
    const bounded = Math.max(16, Math.min(28, size));
    content.style.fontSize = `${bounded}px`;
    try { localStorage.setItem(`${storageKey}-size`, String(bounded)); } catch (_) { /* Optional preference. */ }
  };
  const themeButton = document.querySelector('[data-reader-theme]');
  const setTheme = (dark) => {
    content.classList.toggle('reader-dark', dark);
    themeButton.setAttribute('aria-pressed', String(dark));
    themeButton.textContent = dark ? 'Light reading theme' : 'Dark reading theme';
    try { localStorage.setItem(`${storageKey}-dark`, String(dark)); } catch (_) { /* Optional preference. */ }
  };
  try {
    const size = Number(localStorage.getItem(`${storageKey}-size`));
    if (size) setSize(size);
    setTheme(localStorage.getItem(`${storageKey}-dark`) === 'true');
  } catch (_) { setTheme(false); }
  document.querySelectorAll('[data-font-step]').forEach((button) => button.addEventListener('click', () => setSize((parseInt(getComputedStyle(content).fontSize, 10) || 19) + Number(button.dataset.fontStep) * 2)));
  themeButton.addEventListener('click', () => setTheme(themeButton.getAttribute('aria-pressed') !== 'true'));
});
