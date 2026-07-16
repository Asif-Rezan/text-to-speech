(() => {
  const text = document.querySelector('#id_text');
  const count = document.querySelector('#charCount');
  const estimate = document.querySelector('#estimate');
  const speed = document.querySelector('#id_speed');
  const speedValue = document.querySelector('#speedValue');
  const language = document.querySelector('#id_language');
  const voice = document.querySelector('#id_voice');
  const form = document.querySelector('#speechForm');
  const button = document.querySelector('#generateBtn');
  const overlay = document.querySelector('#generationOverlay');
  const progressCard = overlay.querySelector('.progress-card');
  const bar = document.querySelector('#progressBar');
  const percent = document.querySelector('#progressPercent');
  const message = document.querySelector('#progressMessage');
  const elapsedLabel = document.querySelector('#progressTime');
  const steps = [...overlay.querySelectorAll('.progress-steps span')];
  const samples = [
    'Great stories do more than fill the silence. They give every pause a purpose, every sentence a rhythm, and every idea a voice worth remembering.',
    'Welcome to natural text to speech. Transform your words into clear, expressive audio quickly and beautifully.'
  ];
  let timer;

  const voiceOptions = [...voice.options].map(option => ({value: option.value, label: option.textContent}));

  function syncVoices() {
    const previous = voice.value;
    const matches = voiceOptions.filter(option => option.value.startsWith(`${language.value}-`));
    voice.replaceChildren(...matches.map(option => new Option(option.label, option.value)));
    voice.value = matches.some(option => option.value === previous) ? previous : matches[0]?.value || '';
    voice.classList.remove('field-invalid');
    const error = form.querySelector('[data-error-for="voice"]');
    if (error) error.textContent = '';
  }

  function update() {
    const words = text.value.trim().split(/\s+/).filter(Boolean).length;
    const seconds = Math.round((words / 155 * 60) / Number(speed.value || 1));
    count.textContent = text.value.length.toLocaleString();
    estimate.textContent = `~${seconds < 60 ? `${seconds} sec` : `${Math.floor(seconds / 60)} min ${seconds % 60} sec`} audio`;
    speedValue.textContent = `${Number(speed.value).toFixed(2)}×`;
  }

  function clearErrors() {
    form.querySelectorAll('.field-invalid').forEach(field => field.classList.remove('field-invalid'));
    form.querySelectorAll('.client-field-error').forEach(error => { error.textContent = ''; });
  }

  function showErrors(errors = {}) {
    clearErrors();
    let firstField = null;
    let firstMessage = '';
    Object.entries(errors).forEach(([name, details]) => {
      const field = form.querySelector(`[name="${CSS.escape(name)}"]`);
      const errorBox = form.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
      const fieldMessage = details.map(detail => detail.message).join(' ');
      if (field) {
        field.classList.add('field-invalid');
        if (!firstField) firstField = field;
      }
      if (errorBox) errorBox.textContent = fieldMessage;
      if (!firstMessage) firstMessage = fieldMessage;
    });
    return { firstField, firstMessage };
  }

  function showProgress() {
    let value = 8, elapsed = 0;
    progressCard.classList.remove('error');
    overlay.classList.add('show');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    bar.style.width = '8%'; percent.textContent = '8%'; elapsedLabel.textContent = '0s elapsed';
    message.textContent = 'Preparing your script…';
    steps.forEach((step, index) => step.classList.toggle('active', index === 0));
    timer = setInterval(() => {
      elapsed += 1;
      value = Math.min(92, value + Math.max(1, Math.round((92 - value) * .08)));
      bar.style.width = `${value}%`; percent.textContent = `${value}%`; elapsedLabel.textContent = `${elapsed}s elapsed`;
      const stage = value < 34 ? 0 : value < 78 ? 1 : 2;
      steps.forEach((step, index) => step.classList.toggle('active', index <= stage));
      message.textContent = ['Preparing voice model and script…', 'Synthesizing neural audio locally…', 'Polishing the final waveform…'][stage];
    }, 1000);
  }

  function hideProgress(delay = 650) {
    clearInterval(timer);
    setTimeout(() => {
      overlay.classList.remove('show'); overlay.setAttribute('aria-hidden', 'true'); document.body.style.overflow = '';
    }, delay);
  }

  function bindDelete(scope = document) {
    scope.querySelectorAll('.delete-form:not([data-bound])').forEach(deleteForm => {
      deleteForm.dataset.bound = 'true';
      deleteForm.addEventListener('submit', event => {
        if (!confirm('Delete this generation and its audio file?')) event.preventDefault();
      });
    });
  }

  text.addEventListener('input', update);
  speed.addEventListener('input', update);
  language.addEventListener('change', syncVoices);
  form.querySelectorAll('input, textarea, select').forEach(field => field.addEventListener('input', () => {
    field.classList.remove('field-invalid');
    const error = form.querySelector(`[data-error-for="${CSS.escape(field.name)}"]`);
    if (error) error.textContent = '';
  }));
  document.querySelector('#sampleBtn').addEventListener('click', () => { text.value = samples[Math.floor(Math.random() * samples.length)]; update(); text.focus(); });
  document.querySelector('#clearBtn').addEventListener('click', () => { text.value = ''; update(); text.focus(); });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearErrors();
    if (!form.reportValidity()) return;
    button.disabled = true;
    showProgress();
    try {
      const response = await fetch(form.action || window.location.href, {
        method: 'POST', body: new FormData(form),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
      });
      const data = await response.json();
      if (response.status === 422) {
        const validation = showErrors(data.errors);
        throw Object.assign(new Error(validation.firstMessage || data.message), {validation});
      }
      if (!response.ok || !data.ok) throw new Error(data.message || 'Audio generation failed.');
      clearInterval(timer); bar.style.width = '100%'; percent.textContent = '100%'; message.textContent = 'Your audio is ready!'; steps.forEach(step => step.classList.add('active'));
      const grid = document.querySelector('#historyGrid');
      grid.insertAdjacentHTML('afterbegin', data.card_html);
      document.querySelector('#historySection').classList.remove('d-none');
      bindDelete(grid); hideProgress(850);
      setTimeout(() => grid.querySelector('.audio-card').scrollIntoView({behavior: 'smooth', block: 'center'}), 900);
    } catch (error) {
      clearInterval(timer); progressCard.classList.add('error'); bar.style.width = '100%'; percent.textContent = 'Error'; message.textContent = error.message;
      const delay = error.validation ? 1500 : 2600;
      hideProgress(delay);
      if (error.validation?.firstField) setTimeout(() => {
        error.validation.firstField.scrollIntoView({behavior: 'smooth', block: 'center'});
        error.validation.firstField.focus({preventScroll: true});
      }, delay + 100);
    } finally {
      button.disabled = false;
    }
  });

  bindDelete(); syncVoices(); update();
})();
