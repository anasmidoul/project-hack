document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy]');
  if (!button) return;
  const draft = document.getElementById(button.dataset.copy);
  if (!draft) return;
  try {
    await navigator.clipboard.writeText(draft.value);
    button.textContent = 'Copied ✓';
    setTimeout(() => { button.textContent = 'Copy draft'; }, 1600);
  } catch {
    draft.focus();
    draft.select();
    button.textContent = 'Selected — copy text';
  }
});
