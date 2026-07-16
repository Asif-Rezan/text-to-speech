# Neural Voice Studio

A self-hosted Django text-to-speech studio powered by Piper. Sixteen voices—including eight US English options—across eight language locales are synthesized locally with ONNX: no account, API key, per-character charge, or network request during generation.

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
