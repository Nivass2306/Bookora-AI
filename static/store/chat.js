document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('bookora-chat-form');
  const transcript = document.getElementById('chat-transcript');
  const input = document.getElementById('chat-message');
  if (!form || !transcript || !input) return;
  const button = form.querySelector('button');
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]')?.value;

  function message(role, text) {
    const article = document.createElement('article');
    article.className = `chat-turn ${role === 'You' ? 'chat-user' : 'chat-assistant'}`;
    const heading = document.createElement('strong');
    heading.textContent = role;
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    article.append(heading, paragraph);
    transcript.append(article);
    return article;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question || question.length > 500) return;
    message('You', question);
    input.value = '';
    input.disabled = true;
    button.disabled = true;
    button.textContent = 'Thinking…';
    const pending = message('Bookora', 'Checking the catalogue…');
    pending.setAttribute('aria-busy', 'true');
    try {
      const body = new URLSearchParams({ message: question });
      const response = await fetch(form.dataset.url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Bookora could not answer just now.');
      pending.querySelector('p').textContent = data.answer;
      pending.removeAttribute('aria-busy');
      if (data.fallback) {
        const fallback = document.createElement('small');
        fallback.textContent = 'Catalogue search fallback';
        pending.append(fallback);
      }
      if (data.books?.length) {
        const list = document.createElement('ul');
        list.className = 'chat-book-links';
        data.books.forEach((book) => {
          const item = document.createElement('li');
          const link = document.createElement('a');
          link.href = book.url;
          link.textContent = `${book.title} — ${book.author}`;
          item.append(link);
          const note = document.createElement('small');
          note.textContent = `${book.kind || 'Book'} · ${book.access} · ₹${book.price}${book.kind === 'Audiobook' && !book.playable ? ' · recording unavailable' : ''}`;
          item.append(note);
          list.append(item);
        });
        pending.append(list);
      }
    } catch (error) {
      pending.querySelector('p').textContent = error.message || 'Bookora could not answer just now.';
      pending.removeAttribute('aria-busy');
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'text-button chat-retry';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => {
        input.value = question;
        form.requestSubmit();
      });
      pending.append(retry);
    } finally {
      input.disabled = false;
      button.disabled = false;
      button.textContent = 'Ask';
      input.focus();
      transcript.scrollTop = transcript.scrollHeight;
    }
  });
});
