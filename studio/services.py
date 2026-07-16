import re
import tempfile
import threading
import wave
from pathlib import Path

from django.conf import settings

LANGUAGES = [
    ('en_US', 'English — US'), ('en_GB', 'English — UK'),
    ('es_ES', 'Spanish — Spain'), ('fr_FR', 'French — France'),
    ('de_DE', 'German — Germany'), ('hi_IN', 'Hindi — India'),
    ('pt_BR', 'Portuguese — Brazil'), ('zh_CN', 'Mandarin Chinese'),
]
VOICES = [
    ('en_US-ljspeech-medium', 'LJ Speech · US Female'),
    ('en_US-hfc_male-medium', 'HFC · US Male'),
    ('en_US-amy-medium', 'Amy · US Female'),
    ('en_US-lessac-high', 'Lessac · US Female · High'),
    ('en_US-kristin-medium', 'Kristin · US Female'),
    ('en_US-ryan-high', 'Ryan · US Male · High'),
    ('en_US-joe-medium', 'Joe · US Male'),
    ('en_US-bryce-medium', 'Bryce · US Male'),
    ('en_GB-alba-medium', 'Alba · UK Female'),
    ('es_ES-davefx-medium', 'Dave · Spanish Male'),
    ('fr_FR-siwis-medium', 'Siwis · French Female'),
    ('de_DE-thorsten-medium', 'Thorsten · German Male'),
    ('hi_IN-pratham-medium', 'Pratham · Hindi Male'),
    ('hi_IN-priyamvada-medium', 'Priyamvada · Hindi Female'),
    ('pt_BR-faber-medium', 'Faber · Portuguese Male'),
    ('zh_CN-huayan-medium', 'Huayan · Mandarin Female'),
]

_voices = {}
_load_lock = threading.Lock()
_synthesis_lock = threading.Lock()


class TTSUnavailable(RuntimeError):
    pass


def model_path(voice):
    return Path(settings.PIPER_MODEL_DIR) / f'{voice}.onnx'


def model_available(voice='en_US-ljspeech-medium'):
    path = model_path(voice)
    return path.is_file() and path.with_suffix('.onnx.json').is_file()


def all_models_available():
    return all(model_available(voice) for voice, _label in VOICES)


def _get_voice(voice_name):
    try:
        from piper import PiperVoice
    except (ImportError, OSError) as exc:
        raise TTSUnavailable('Piper is not installed. Run: pip install -r requirements.txt') from exc
    path = model_path(voice_name)
    if not model_available(voice_name):
        raise TTSUnavailable(f'Piper voice {voice_name} is missing. Run the voice download command in README.md.')
    with _load_lock:
        if voice_name not in _voices:
            _voices[voice_name] = PiperVoice.load(str(path))
    return _voices[voice_name]


def split_text(text, max_chars=3500):
    """Split long scripts on natural boundaries without losing content."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    units = re.split(r'(?<=[.!?。！？])\s+|\n+', text)
    chunks, current = [], ''
    for unit in filter(None, (unit.strip() for unit in units)):
        if len(unit) > max_chars:
            if current:
                chunks.append(current)
                current = ''
            while len(unit) > max_chars:
                boundary = unit.rfind(' ', 0, max_chars + 1)
                boundary = boundary if boundary > max_chars // 2 else max_chars
                chunks.append(unit[:boundary].strip())
                unit = unit[boundary:].strip()
        candidate = f'{current} {unit}'.strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _merge_wav_files(parts, output_path):
    with wave.open(str(parts[0]), 'rb') as first:
        params = first.getparams()
        with wave.open(str(output_path), 'wb') as destination:
            destination.setparams(params)
            destination.writeframes(first.readframes(first.getnframes()))
            for part in parts[1:]:
                with wave.open(str(part), 'rb') as source:
                    audio_format = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                    expected = (params.nchannels, params.sampwidth, params.framerate)
                    if audio_format != expected:
                        raise TTSUnavailable('Generated segments have incompatible WAV formats.')
                    destination.writeframes(source.readframes(source.getnframes()))


def synthesize(text, voice, language, speed, output_path, audio_format='wav'):
    try:
        from piper.config import SynthesisConfig
    except (ImportError, OSError) as exc:
        raise TTSUnavailable('Piper is not installed. Run: pip install -r requirements.txt') from exc
    output_path = Path(output_path).with_suffix('.wav')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config = SynthesisConfig(length_scale=1 / float(speed), normalize_audio=True)
    try:
        loaded_voice = _get_voice(voice)
        chunks = split_text(text)
        if not chunks:
            raise TTSUnavailable('Enter text to synthesize.')
        # Generate bounded segments, then join their PCM frames into one lossless WAV.
        with _synthesis_lock, tempfile.TemporaryDirectory(prefix='piper-', dir=output_path.parent) as temp_dir:
            parts = []
            for index, chunk in enumerate(chunks):
                part = Path(temp_dir) / f'{index:04d}.wav'
                with wave.open(str(part), 'wb') as wav_file:
                    loaded_voice.synthesize_wav(chunk, wav_file, syn_config=config)
                parts.append(part)
            _merge_wav_files(parts, output_path)
        with wave.open(str(output_path), 'rb') as wav_file:
            return wav_file.getnframes() / wav_file.getframerate()
    except TTSUnavailable:
        raise
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise TTSUnavailable(f'Piper synthesis error: {exc}') from exc
