# Neural Voice Studio

A self-hosted Django text-to-speech studio powered by Piper. Sixteen voices—including eight US English options—across eight language locales are synthesized locally with ONNX: no account, API key, per-character charge, or network request during generation.

## Setup

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m piper.download_voices --data-dir models\piper en_US-ljspeech-medium en_US-hfc_male-medium en_US-amy-medium en_US-lessac-high en_US-kristin-medium en_US-ryan-high en_US-joe-medium en_US-bryce-medium en_GB-alba-medium es_ES-davefx-medium fr_FR-siwis-medium de_DE-thorsten-medium hi_IN-pratham-medium hi_IN-priyamvada-medium pt_BR-faber-medium zh_CN-huayan-medium
python manage.py migrate
python manage.py runserver
```

Each voice must have both its `.onnx` and `.onnx.json` files in `models/piper/`. Override that directory with `PIPER_MODEL_DIR` if needed. Models are loaded on first use and cached for subsequent requests.

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
