document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('home-discovery-form');
  const input = document.getElementById('home-discovery-input');
  const result = document.getElementById('home-discovery-result');
  if (!form || !input || !result) return;

  const submit = form.querySelector('button[type="submit"]');
  const csrf = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
  const originalLabel = submit?.textContent || 'Find my reads';

  function label(text, source) {
    const badge = document.createElement('span');
    badge.className = 'home-result-label';
    badge.dataset.source = source;
    badge.textContent = text;
    return badge;
  }

  function renderBooks(books) {
    if (!Array.isArray(books) || books.length === 0) return;
    const list = document.createElement('ul');
    list.className = 'home-result-books';
    books.forEach((book) => {
      if (!book || typeof book.title !== 'string' || typeof book.author !== 'string' || typeof book.url !== 'string') return;
      const url = new URL(book.url, window.location.origin);
      if (url.origin !== window.location.origin) return;
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = url.pathname + url.search + url.hash;
      const title = document.createElement('span');
      title.textContent = `${book.title} — ${book.author}`;
      const access = document.createElement('small');
      access.textContent = `${book.kind || 'Book'} · ${book.access || 'See book details'}`;
      link.append(title, access);
      item.append(link);
      list.append(item);
    });
    if (list.childElementCount) result.append(list);
  }

  document.querySelectorAll('.home-prompts [data-prompt]').forEach((chip) => {
    chip.addEventListener('click', () => {
      input.value = chip.dataset.prompt || '';
      input.focus();
    });
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || message.length > 500 || !csrf || !submit) return;

    result.hidden = false;
    result.dataset.state = 'loading';
    result.setAttribute('aria-busy', 'true');
    result.replaceChildren();
    const loading = document.createElement('p');
    loading.textContent = 'Looking through the current catalogue…';
    result.append(loading);
    submit.disabled = true;
    input.disabled = true;
    submit.textContent = 'Searching…';

    try {
      const response = await fetch(form.dataset.url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrf,
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ message }),
        credentials: 'same-origin',
      });
      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('The assistant returned a response that could not be read. Please try again.');
      }
      if (!response.ok) throw new Error(data.error || `Bookora could not complete the request (HTTP ${response.status}).`);
      if (typeof data.answer !== 'string' || !Array.isArray(data.books) || typeof data.fallback !== 'boolean') {
        throw new Error('Bookora returned an unexpected response. Please try again.');
      }

      result.dataset.state = 'success';
      result.replaceChildren();
      result.append(label(data.fallback ? 'Local catalogue matches · Gemini unavailable' : 'Gemini-generated recommendation', data.fallback ? 'fallback' : 'gemini'));
      const answer = document.createElement('p');
      answer.textContent = data.answer;
      result.append(answer);
      renderBooks(data.books);
    } catch (error) {
      result.dataset.state = 'error';
      result.replaceChildren(label('Request error', 'error'));
      const messageText = document.createElement('p');
      messageText.textContent = error instanceof TypeError
        ? 'Book discovery could not connect. Check your connection and try again.'
        : (error.message || 'Book discovery could not finish just now. Please try again.');
      result.append(messageText);
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'home-text-link';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => form.requestSubmit());
      result.append(retry);
    } finally {
      result.setAttribute('aria-busy', 'false');
      submit.disabled = false;
      input.disabled = false;
      submit.textContent = originalLabel;
    }
  });
});
