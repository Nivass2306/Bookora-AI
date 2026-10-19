document.addEventListener('DOMContentLoaded', () => {
  const menuButton = document.querySelector('.menu-toggle');
  const navigation = document.getElementById('main-navigation');
  if (menuButton && navigation) {
    menuButton.addEventListener('click', () => {
      const expanded = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!expanded));
      menuButton.setAttribute('aria-label', expanded ? 'Open navigation' : 'Close navigation');
      document.body.classList.toggle('nav-open', !expanded);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.setAttribute('aria-label', 'Open navigation');
        document.body.classList.remove('nav-open');
        menuButton.focus();
      }
    });
  }

  const railButtons = document.querySelectorAll('[data-scroll-rail]');
  const updateRailControls = () => {
    railButtons.forEach((button) => {
      const rail = document.getElementById(button.dataset.scrollRail);
      if (rail) button.hidden = rail.scrollWidth <= rail.clientWidth + 1;
    });
  };
  updateRailControls();
  window.addEventListener('resize', updateRailControls);
  railButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const rail = document.getElementById(button.dataset.scrollRail);
      if (!rail) return;
      const direction = button.dataset.direction === 'next' ? 1 : -1;
      rail.scrollBy({ left: direction * Math.max(240, rail.clientWidth * 0.75), behavior: 'smooth' });
    });
  });

  const form = document.querySelector('.summary-form');
  if (!form) return;
  const button = form.querySelector('button');
  const result = document.querySelector('.summary-result');
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]')?.value;

  function addTextSection(parent, heading, value) {
    const section = document.createElement('section');
    section.className = 'summary-section';
    const title = document.createElement('h3');
    title.textContent = heading;
    section.append(title);
    if (Array.isArray(value) && value.length) {
      const list = document.createElement('ul');
      value.forEach((entry) => {
        const item = document.createElement('li');
        item.textContent = String(entry);
        list.append(item);
      });
      section.append(list);
    } else {
      const paragraph = document.createElement('p');
      paragraph.textContent = Array.isArray(value) ? 'Not available in the supplied book details.' : String(value || 'Not available in the supplied book details.');
      section.append(paragraph);
    }
    parent.append(section);
  }

  async function generateSummary() {
    button.disabled = true;
    button.textContent = 'Preparing your reading notes...';
    result.className = 'summary-result is-visible';
    result.setAttribute('aria-busy', 'true');
    result.replaceChildren();
    const loading = document.createElement('p');
    loading.textContent = 'Looking over the available book details. This may take a few seconds.';
    result.append(loading);
    try {
      const response = await fetch(form.dataset.url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, Accept: 'application/json' },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The reading assistant could not finish just now.');
      result.replaceChildren();
      addTextSection(result, 'Overview', data.summary.overview);
      addTextSection(result, 'Themes', data.summary.themes);
      addTextSection(result, 'Key ideas and learning points', data.summary.key_ideas);
      addTextSection(result, 'Who may enjoy it', data.summary.audience);
      button.textContent = data.cached ? 'Notes are ready' : 'Generate again';
    } catch (error) {
      result.replaceChildren();
      const message = document.createElement('div');
      message.className = 'summary-error';
      message.textContent = error.message || 'The reading assistant could not finish just now.';
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Try again';
      retry.addEventListener('click', generateSummary);
      message.append(retry);
      result.append(message);
      button.textContent = 'Generate AI overview';
    } finally {
      result.setAttribute('aria-busy', 'false');
      button.disabled = false;
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    generateSummary();
  });
});
