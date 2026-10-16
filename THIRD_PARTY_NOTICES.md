# Third-party notices

## Piper

- Project: [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)
- Version family: 1.4.x
- License: GNU General Public License v3.0

## Bundled Piper voices

- Repository: [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)
- Voices: `en_US-ljspeech-medium`, `en_US-hfc_male-medium`, `en_US-amy-medium`, `en_US-lessac-high`, `en_US-kristin-medium`, `en_US-ryan-high`, `en_US-joe-medium`, `en_US-bryce-medium`, `en_GB-alba-medium`, `es_ES-davefx-medium`, `fr_FR-siwis-medium`, `de_DE-thorsten-medium`, `hi_IN-pratham-medium`, `hi_IN-priyamvada-medium`, `pt_BR-faber-medium`, and `zh_CN-huayan-medium`
- LJSpeech dataset reference: [LJSpeech](https://keithito.com/LJ-Speech-Dataset/)

Piper voice models can carry independent dataset/model terms. Review the voice's current `MODEL_CARD` before redistribution or commercial launch. This notice is informational and not legal advice.

## Bangla multi-speaker voice

- Model: [`bn_BD-google-medium`](https://huggingface.co/rhasspy/piper-voices/tree/c10ece1aade47bb51c153c893d14e5bf8e5b7117/bn/bn_BD/google/medium)
- Selected speakers: `4811` (12) and `rm` (15); UI names describe narration options, not performer identities.
- Google Bengali dataset: [OpenSLR 37](https://www.openslr.org/37/), collected by Google, licensed CC BY-SA 4.0.
- CMU Indic data: Carnegie Mellon University, copyright 2009–2017, under the permission notice preserved in `models/piper/bn_BD-google-medium.MODEL_CARD`.
- The model card is included verbatim; no model weights are modified.

## Online Bangla synthesis

- Client: [rany2/edge-tts](https://github.com/rany2/edge-tts), LGPLv3.
- Audio decoder: [miniaudio](https://github.com/irmen/pyminiaudio), MIT; bundled miniaudio is public domain or MIT No Attribution.
- Voices: Microsoft `bn-BD-NabanitaNeural` and `bn-IN-TanishaaNeural`.
- The client library license does not grant rights to Microsoft’s service or its output. Provider terms apply; no commercial license is promised by this app.
- Earlier Piper Bangla assets remain documented above for historical attribution; they are no longer selectable.
