(() => {
  const text = document.querySelector('#id_text');
  const count = document.querySelector('#charCount');
  const estimate = document.querySelector('#estimate');
  const speed = document.querySelector('#id_speed');
  const speedValue = document.querySelector('#speedValue');
  const language = document.querySelector('#id_language');
  const voice = document.querySelector('#id_voice');
  const emotion = document.querySelector('#id_emotion');
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
  let expressiveJob;

  const voiceOptions = [...voice.options].map(option => ({value: option.value, label: option.textContent}));

  function syncVoices() {
    const previous = voice.value;
    const matches = voiceOptions.filter(option => option.value.startsWith(`${language.value}-`));
    voice.replaceChildren(...matches.map(option => new Option(option.label, option.value)));
    voice.value = matches.some(option => option.value === previous) ? previous : matches[0]?.value || '';
    updateVoicePrivacy();
    text.lang = language.value === 'bn_BD' ? 'bn' : language.value.replace('_', '-');
    voice.classList.remove('field-invalid');
    const error = form.querySelector('[data-error-for="voice"]');
    if (error) error.textContent = '';
  }

  function updateVoicePrivacy() {
    const cpu = voice.value === 'bn_BD-google-medium';
    const expressive = cpu || voice.value.endsWith('-parler');
    document.querySelector('#emotionControls .pane-help').textContent = cpu
      ? 'Automatic mood detection adjusts pacing and pauses. This voice does not perform emotional acting.'
      : 'Automatic emotion: speech delivery changes to match the story’s mood.';
    document.querySelector('#emotionControls').hidden = !expressive;
    emotion.disabled = !expressive;
    text.maxLength = voice.value === 'bn_BD-indicvoice-experimental' ? 1000 : 20000;
    document.querySelector('#charLimit').textContent = text.maxLength.toLocaleString();
    document.querySelector('#voiceLimitNote').textContent = cpu
      ? 'Up to 20,000 characters. CPU-generated sections are combined into one WAV. Keep this tab open.'
      : expressive
      ? 'Indian Bengali accent · Up to 20,000 characters. Long scripts are generated in sections and combined into one WAV. Keep this tab open.'
      : 'Up to 20,000 characters.';
    const localIndic = voice.value === 'bn_BD-indicvoice-experimental';
    document.querySelector('#voicePrivacyNote').textContent = cpu
      ? '◆ Bangla audio is generated on this server’s CPU. No external GPU quota.'
      : expressive
      ? '◆ Expressive Bangla sends your script to AI4Bharat on Hugging Face. Free shared GPU; availability and quotas may vary.'
      : localIndic
      ? '◆ IndicVoice runs on this server. Experimental Bangla support; up to 1,000 characters.'
      : language.value === 'bn_BD'
        ? '◆ Online Bangla voices send your script to Microsoft. No API key required.'
        : '◆ Text and audio stay on this server for local voices.';
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
      message.textContent = ['Preparing voice model and script…', language.value === 'bn_BD' && voice.value !== 'bn_BD-indicvoice-experimental' ? 'Generating natural Bangla speech online…' : 'Synthesizing neural audio locally…', 'Polishing the final waveform…'][stage];
    }, 1000);
  }

  function hideProgress(delay = 650) {
    clearInterval(timer);
    setTimeout(() => {
      overlay.classList.remove('show'); overlay.setAttribute('aria-hidden', 'true'); document.body.style.overflow = '';
    }, delay);
  }

  // Keep temporary-server audio on this device, independent of Vercel instances.
  const audioDb = new Promise((resolve, reject) => {
    const request = indexedDB.open('neuralvoice-audio', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('clips', {keyPath: 'id'});
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  audioDb.catch(() => {});
  function attachAudio(card, clip) {
    const url = URL.createObjectURL(clip.blob);
    const audio = card.querySelector('audio');
    audio.src = url;
    audio.load();
    const download = card.querySelector('.download-btn');
    download.href = url;
    download.download = clip.filename;
  }
  async function receiveGeneration(response) {
    if (!response.headers.get('content-type')?.includes('application/x-ndjson')) return response.json();
    const reader = response.body.getReader(), decoder = new TextDecoder();
    const parts = [];
    let pending = '', data, complete = false;
    while (true) {
      const {value, done} = await reader.read();
      pending += decoder.decode(value, {stream: !done});
      let end;
      while ((end = pending.indexOf('\n')) >= 0) {
        const line = pending.slice(0, end); pending = pending.slice(end + 1);
        if (!line) continue;
        const packet = JSON.parse(line);
        if (packet.audio) parts.push(Uint8Array.from(atob(packet.audio), c => c.charCodeAt(0)));
        else if (packet.complete) complete = true;
        else data = packet;
      }
      if (done) break;
    }
    if (!complete || !data || !parts.length) throw new Error('Audio transfer interrupted. Please generate again.');
    data.clip = {id: data.id, filename: data.filename, card_html: data.card_html,
      blob: new Blob(parts, {type: 'audio/wav'}), created: Date.now()};
    return data;
  }

  async function requestGeneration(input, url = form.action || window.location.href) {
    const response = await fetch(url, {
      method: 'POST', body: input,
      headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
    });
    const data = await receiveGeneration(response);
    if (response.status === 422) {
      const validation = showErrors(data.errors);
      throw Object.assign(new Error(validation.firstMessage || data.message), {validation});
    }
    if (!response.ok || !data.ok) throw new Error(data.message || 'Audio generation failed.');
    return data;
  }

  const {splitScript, readPcm, mergePcm} = window.NeuralVoiceAudio;

  async function generateExpressive(input) {
    clearInterval(timer);
    const key = JSON.stringify(['text', 'voice', 'language', 'speed', 'title', 'format', 'emotion'].map(name => input.get(name)));
    if (!expressiveJob || expressiveJob.key !== key) expressiveJob = {key, pcm: [], completed: 0, result: null, plan: null};
    const job = expressiveJob, pcm = job.pcm, start = Date.now();
    let result = job.result;
    message.textContent = 'Analyzing the story’s mood…';
    timer = setInterval(() => { elapsedLabel.textContent = `${Math.floor((Date.now() - start) / 1000)}s elapsed`; }, 1000);
    if (!job.plan) {
      const analysis = await requestGeneration(input, form.dataset.planUrl);
      job.plan = analysis.plan;
    }
    const chunks = job.plan;
    if (!chunks?.length) throw new Error('The story analysis did not return any passages.');
    const emotionNames = {narration: 'Storytelling', happy: 'Happy', sad: 'Sad', angry: 'Angry', fear: 'Fear', surprise: 'Surprise'};
    const progress = index => {
      const value = Math.round(index / chunks.length * 100);
      bar.style.width = `${value}%`; percent.textContent = `${value}%`;
      message.textContent = `Generating Bangla section ${index + 1} of ${chunks.length} · ${emotionNames[chunks[index].emotion] || chunks[index].emotion}… Keep this tab open.`;
      elapsedLabel.textContent = `${Math.floor((Date.now() - start) / 1000)}s elapsed`;
      steps.forEach((step, i) => step.classList.toggle('active', i < 2));
    };
    for (let index = job.completed; index < chunks.length; index++) {
      progress(index);
      const section = new FormData();
      for (const [key, value] of input) section.append(key, value);
      section.set('segment_text', chunks[index].text);
      section.set('segment_emotion', chunks[index].emotion);
      let data;
      try { data = await requestGeneration(section); }
      catch (error) {
        if (job.completed) error.message += ` ${job.completed} of ${chunks.length} sections are saved in this tab. Click Generate again to resume; keep the script and voice unchanged.`;
        throw error;
      }
      if (!data.clip) throw new Error('The speech section did not include audio. Please reload and try again.');
      const part = readPcm(await data.clip.blob.arrayBuffer());
      if (index) pcm.push(new Uint8Array(48 * chunks[index].pause_ms));
      pcm.push(part);
      if (!result) result = data;
      job.result = result; job.completed = index + 1;
    }
    const merged = mergePcm(pcm);
    result.clip.blob = merged.blob;
    const template = document.createElement('template'); template.innerHTML = result.card_html;
    const total = Math.round(merged.seconds), minutes = Math.floor(total / 60), seconds = total % 60;
    template.content.querySelector('.duration-badge').textContent = minutes ? `${minutes} min ${seconds} sec` : `${seconds} sec`;
    const moodSequence = chunks.map(section => section.emotion).filter((mood, i, moods) => !i || mood !== moods[i - 1]);
    const summary = document.createElement('p'); summary.className = 'pane-help';
    summary.textContent = (input.get('voice') === 'bn_BD-google-medium' ? 'Detected mood (pacing and pauses only): ' : 'Automatic emotion: ') + moodSequence.slice(0, 8).map(mood => emotionNames[mood] || mood).join(' → ') + (moodSequence.length > 8 ? ' …' : '');
    template.content.querySelector('.script-preview').after(summary);
    result.card_html = template.innerHTML;
    result.clip.card_html = result.card_html;
    expressiveJob = null;
    return result;
  }

  async function restoreAudio() {
    try {
      const db = await audioDb;
      const clips = await new Promise((resolve, reject) => {
        const request = db.transaction('clips').objectStore('clips').getAll();
        request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
      });
      const grid = document.querySelector('#historyGrid');
      for (const clip of clips.sort((a, b) => a.created - b.created).slice(-6)) {
        let card = grid.querySelector(`[data-generation-id="${CSS.escape(clip.id)}"]`);
        if (!card) { grid.insertAdjacentHTML('afterbegin', clip.card_html); card = grid.firstElementChild; }
        // Older saved clips keep their scripts, but interface labels use English.
        const legacyLabels = {
          'শনাক্ত আবেগ (শুধু গতি ও বিরতি): ': 'Detected mood (pacing and pauses only): ',
          'স্বয়ংক্রিয় আবেগ: ': 'Automatic emotion: ',
          'স্বয়ংক্রিয় আবেগ / Automatic': 'Automatic',
          'গল্প বলা / Storytelling': 'Storytelling', 'কথোপকথন / Conversation': 'Conversation',
          'আনন্দ / Happy': 'Happy', 'দুঃখ / Sad': 'Sad', 'রাগ / Angry': 'Angry',
          'ভয় / Fear': 'Fear', 'বিস্ময় / Surprise': 'Surprise', 'সংবাদ / News': 'News',
          'স্বাভাবিক / Neutral': 'Neutral', 'গল্প বলা': 'Storytelling',
          'আনন্দ': 'Happy', 'দুঃখ': 'Sad', 'রাগ': 'Angry', 'ভয়': 'Fear', 'বিস্ময়': 'Surprise',
        };
        card.querySelectorAll('.card-top p, .pane-help').forEach(label => {
          let value = label.textContent;
          for (const [before, after] of Object.entries(legacyLabels)) value = value.split(before).join(after);
          label.textContent = value;
        });
        attachAudio(card, clip);
        document.querySelector('#historySection').classList.remove('d-none');
      }
      bindDelete(grid);
    } catch (_) { /* Playback in this tab still works when device storage is unavailable. */ }
  }

  function bindDelete(scope = document) {
    scope.querySelectorAll('.delete-form:not([data-bound])').forEach(deleteForm => {
      deleteForm.dataset.bound = 'true';
      deleteForm.addEventListener('submit', event => {
        if (!confirm('Delete this generation and its audio file?')) { event.preventDefault(); return; }
        const card = deleteForm.closest('.audio-card');
        if (card.querySelector('audio')?.src.startsWith('blob:')) {
          event.preventDefault();
          audioDb.then(db => db.transaction('clips', 'readwrite').objectStore('clips').delete(card.dataset.generationId)).catch(() => {});
          URL.revokeObjectURL(card.querySelector('audio').src); card.remove();
        }
      });
    });
  }

  text.addEventListener('input', update);
  speed.addEventListener('input', update);
  language.addEventListener('change', syncVoices);
  voice.addEventListener('change', updateVoicePrivacy);
  form.querySelectorAll('input, textarea, select').forEach(field => field.addEventListener('input', () => {
    field.classList.remove('field-invalid');
    const error = form.querySelector(`[data-error-for="${CSS.escape(field.name)}"]`);
    if (error) error.textContent = '';
  }));
  document.querySelector('#sampleBtn').addEventListener('click', () => {
    text.value = language.value === 'bn_BD'
      ? 'আজ আমার মেয়ে পরীক্ষায় প্রথম হয়েছে। খুশিতে সবার মুখে হাসি।\n\nআমি খুব ভয় পাচ্ছি। মনে হচ্ছে কেউ আমাকে মেরে ফেলবে।\n\nপরের দিনই বাবা মারা গেলেন। বুক ফেটে কান্না এলো।'
      : samples[Math.floor(Math.random() * samples.length)];
    update(); text.focus();
  });
  document.querySelector('#clearBtn').addEventListener('click', () => { text.value = ''; update(); text.focus(); });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearErrors();
    document.querySelector('#generationError').hidden = true;
    if (!form.reportValidity()) return;
    button.disabled = true;
    showProgress();
    try {
      const input = new FormData(form);
      const data = (String(input.get('voice')).endsWith('-parler') || input.get('voice') === 'bn_BD-google-medium')
        ? await generateExpressive(input) : await requestGeneration(input);
      clearInterval(timer); bar.style.width = '100%'; percent.textContent = '100%'; message.textContent = 'Your audio is ready!'; steps.forEach(step => step.classList.add('active'));
      const grid = document.querySelector('#historyGrid');
      grid.insertAdjacentHTML('afterbegin', data.card_html);
      if (data.clip) {
        attachAudio(grid.firstElementChild, data.clip);
        audioDb.then(db => db.transaction('clips', 'readwrite').objectStore('clips').put(data.clip)).catch(() => {});
      }
      document.querySelector('#historySection').classList.remove('d-none');
      bindDelete(grid); hideProgress(850);
      setTimeout(() => grid.querySelector('.audio-card').scrollIntoView({behavior: 'smooth', block: 'center'}), 900);
    } catch (error) {
      const errorNote = document.querySelector('#generationError');
      errorNote.textContent = error.message; errorNote.hidden = false;
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

  bindDelete(); syncVoices(); update(); restoreAudio();
})();
