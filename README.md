# Neural Voice Studio

A Django text-to-speech studio with sixteen local Piper voices and four online Bangla voices across nine language locales. Local voices use ONNX; Bangla uses Microsoft Edge’s online service through `edge-tts`, without an API key.

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
