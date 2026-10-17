# Neural Voice Studio

A Django text-to-speech studio with CPU Piper Bangla selected by default. Expressive Bangla uses AI4Bharat Indic Parler-TTS on its public Hugging Face GPU service, without an API key. Bangladesh Microsoft neural voices and sixteen local Piper voices remain available.

## Setup

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Large `.onnx` files are not stored in the repository. On first use, the selected voice is downloaded atomically from the configured GitHub release and cached in `models/piper/`; subsequent generations are fully local. The small `.onnx.json` configuration files remain versioned. Override the cache with `PIPER_MODEL_DIR` or the release base with `PIPER_MODEL_BASE_URL`.

Scripts may contain up to 20,000 characters. Long scripts are split at natural sentence/paragraph boundaries, synthesized in bounded local segments, and merged losslessly into one downloadable WAV file.

## Commercial and licensing notes

Piper 1.4 is GPLv3 software. Commercial use and monetization are allowed, but distributing or deploying a combined derivative may impose GPLv3 source-code and license obligations. Consult qualified counsel for your exact distribution model.

Voice models have separate licenses. This project uses `en_US-ljspeech-medium`, trained from the LJSpeech dataset. Preserve [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), verify the model card before each release, and do not add a voice without reviewing its dataset/model license.

## Production

Use HTTPS, environment-based Django secrets, authentication, per-user quotas, request rate limiting, a background job queue, and published privacy/acceptable-use policies before accepting public traffic. Run `collectstatic`, keep `db.sqlite3`, `media/`, and `models/` on persistent storage, and serve Windows deployments with Waitress:

```powershell
python manage.py migrate
waitress-serve --listen=127.0.0.1:8000 config.wsgi:application
```

Health check: `GET /health/`.

### Vercel temporary mode

Vercel uses Python 3.12 and detects `config.wsgi.application`. Configure a nonempty
`DJANGO_SECRET_KEY` and `DJANGO_DEBUG=0` in the project environment. Static assets
are collected automatically. The function allows up to 300 seconds for cold model
downloads and synthesis.

On Vercel, SQLite, downloaded voice models, and generated WAV files live under
`/tmp/neural-voice-studio`. Migrations initialize a fresh database on each instance;
the development database is excluded from the function. History and downloads are
temporary and are not shared between instances. Download audio immediately. For
durable history and reliable downloads across instances, use an external database
and object storage or deploy the existing Docker app with a persistent disk.

### Bangla narration

Choose **বাংলা — Bangla** for **Nabanita** (female) or **Pradeep** (male)
with Bangladesh pronunciation, or **Tanishaa** (female) or **Bashkar** (male)
with Indian Bengali pronunciation. These voices support general narration,
conversations, audiobooks, and stories.
These replace the earlier Piper Bangla voices. Scripts selected for Bangla are
sent to Microsoft; other voices remain local. No API key is required. The
unofficial Edge service can change or become unavailable, and use remains subject
to the provider’s terms. No commercial-use rights are implied by the client library.

The service returns compressed MP3 audio, decoded into a 24 kHz mono WAV using
miniaudio. A WAV container does not restore quality lost in the source MP3.
Start at 1.0× for the original speaking pace, with normal Bangla punctuation.

### IndicVoice-82M experimental option

All existing languages, Piper models, and four online Bangla voices are retained.
The additional **IndicVoice-82M · Female · Experimental** option runs locally on
CPU and uses the upstream `hf_beta` voice style. Bengali support is beta; this is
not a verified improvement over the existing voices. Its frontend needs two
compatibility fixes: allowing `bn` and avoiding incomplete English token objects.
The adapter also keeps phonemes joined within each word and uses short chunks to
avoid the upstream pipeline's silent truncation.

Install `requirements.txt` plus `requirements-indicvoice.txt` (Python 3.12) on a separate CPU/GPU host. This option is hidden on Vercel to keep its runtime small. The optional runtime is imported only
when this voice is selected. Model assets are pinned to Hugging Face revision
`2cf8fffbdf72a6fdee5cf841323a161d958b2e0a`, checked by SHA-256 on download, and
cached under `models/indicvoice` within the runtime directory. No API key is used.
The experimental option accepts up to 1,000 characters; existing voices retain
the 20,000-character limit. CPU-only PyTorch is selected on Linux. The function
bundle requires Vercel large-functions support; do not enable this deployment
without a real memory and synthesis check on the target runtime.

### Expressive Bangla (optional)

**Aditi** (female) and **Arjun** (male) use the actual AI4Bharat
[Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) model,
not the Microsoft voices. These are the model author's recommended Bengali
speakers; their accent is Indian Bengali, not a promised Bangladesh accent.
The author's native-speaker evaluation reports 86.16 ± 1.85 for Bengali;
this is not a comparison against ElevenLabs or our own listening evaluation.

Vercel sends the script and a voice description to the author's public
[Hugging Face Space](https://huggingface.co/spaces/ai4bharat/indic-parler-tts).
No API key, PyTorch installation, model download, or GPU is needed on Vercel.
The service is shared and free: queues, quotas, sleeping and upstream changes
can interrupt availability. It is suitable for trying expressive voices, not
a guaranteed production inference service. Errors never silently switch models.
For sustained production traffic, host a dedicated inference service.

Requests accept up to 20,000 characters. The browser splits expressive Bangla
at natural boundaries into 250-character sections, generates each in an
independent Vercel request, and merges the PCM into one 24 kHz mono WAV.
This avoids one long-running request exceeding Vercel duration limits. Keep
the tab open until completion; shared GPU quotas can still interrupt a long job.
Section requests do not create separate server history entries. Completed
sections remain in memory if a later request fails; submit the unchanged script
and voice again to resume in the same tab. Refreshing discards an unfinished job. The pace slider guides
the model through a slow/moderate/fast prompt; it does not guarantee an exact
playback-speed multiplier. Nabanita and Pradeep remain available for Bangladesh pronunciation.
Audio is delivered in the original generation response and saved in the browser
so playback/download survives Vercel instance changes.

Research: IndicF5 supports Bengali but needs permitted reference audio; the
public demo supplies cross-language references, making accent selection less
predictable for this app. A newer Bangladesh-specific IndicF5 fine-tune has
no hosted inference provider and no listening-study evaluation. The checked
BosonLab Bangla Chatterbox Space was failing to start. None of these findings
establish a universal best model or ElevenLabs-equivalent quality.

### Automatic emotional Bangla stories

Paste a story and generate. There is no emotion selector. A CPU-only semantic
analysis step runs on Vercel before speech generation, using the Apache-2.0
[Horizon multilingual emotion classifier](https://huggingface.co/Horizon-Labs/multilingual-emotions-small),
which includes Bengali in its training languages. It uses a quantized ONNX model
and tokenizer, downloaded into memory once per instance, pinned to revision
`1bc9627f189e5aa08b00cf525c3c86052067b81e` and verified by SHA-256. No story
text is sent to the classifier's publisher. No PyTorch or GPU is used for analysis.

The planner scores sentences and nearby paragraph context. A clear local emotion
can mark a turn inside a paragraph; short ambiguous continuations use the
paragraph mood. Low-confidence passages use restrained narration. Adjacent
passages with the same mood are grouped up to 250 characters. Emotion changes
and paragraph breaks receive slightly longer pauses. Every section is sent to
Indic Parler-TTS with its own detected delivery; all sections become one WAV.
20,000-character scripts and same-tab resume remain supported.

Emotion inference is imperfect, especially for irony, figurative writing, and
unusual story contexts. This classifier was trained mainly on translated short
comments rather than fiction. Uncertain scores are not represented as certain
emotions. There is no keyword-list fallback if analysis is unavailable: the UI
reports an error and allows retrying. The published emotion-classification
benchmarks do not establish the quality of this narration pipeline.

Local checks: approximately 963 MB peak process memory during in-memory analysis; a large
story planned in a few seconds after model loading. Vercel cold starts also need
to download about 303 MB of model/tokenizer assets. These are cached in memory
without using Vercel scratch disk space. Live deployment tests
are needed to establish actual runtime behavior on Vercel.


### CPU Bangla (default)

`bn_BD-google-medium` uses Piper on the application server CPU. The 76.8 MB
model is downloaded from the upstream Rhasspy collection and cached in /tmp on
Vercel. No speech API key or external GPU quota is used. The existing CPU
emotion detector plans passages; detected mood changes pacing slightly and
paragraph/mood boundaries add pauses. Piper has no learned emotional acting.
Each passage returns mono 24 kHz PCM WAV for browser merging and retry.
The original model card and dataset attribution are in models/piper.
Vercel CPU usage and execution limits still apply.
