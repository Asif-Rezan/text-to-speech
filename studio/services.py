import asyncio
import re
import shutil
import tempfile
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import wave
from pathlib import Path

from django.conf import settings

from .parler import VOICES as PARLER_VOICES

LANGUAGES = [
    ('bn_BD', 'Bangla — Bangladesh'),
    ('en_US', 'English — US'), ('en_GB', 'English — UK'),
    ('es_ES', 'Spanish — Spain'), ('fr_FR', 'French — France'),
    ('de_DE', 'German — Germany'), ('hi_IN', 'Hindi — India'),
    ('pt_BR', 'Portuguese — Brazil'), ('zh_CN', 'Mandarin Chinese'),
]

PIPER_BANGLA = 'bn_BD-google-medium'
STORY_VOICES = {*PARLER_VOICES, PIPER_BANGLA}

VOICES = [
    ('bn_BD-nabanita-neural', 'Nabanita · Bangladesh Female'),
    ('bn_BD-pradeep-neural', 'Pradeep · Bangladesh Male'),
    (PIPER_BANGLA, 'Bengali · Standard'),
    ('bn_BD-aditi-parler', 'Aditi · Bengali Female · Expressive'),
    ('bn_BD-arjun-parler', 'Arjun · Bengali Male · Expressive'),
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
    ('bn_BD-tanishaa-neural', 'Tanishaa · Indian Bengali Female'),
    ('bn_BD-bashkar-neural', 'Bashkar · Indian Bengali Male'),
    ('bn_BD-indicvoice-experimental', 'Bengali Female · Preview'),
]

ONLINE_VOICES = {
    'bn_BD-nabanita-neural': 'bn-BD-NabanitaNeural',
    'bn_BD-pradeep-neural': 'bn-BD-PradeepNeural',
    'bn_BD-tanishaa-neural': 'bn-IN-TanishaaNeural',
    'bn_BD-bashkar-neural': 'bn-IN-BashkarNeural',
}
INDICVOICE_ID = 'bn_BD-indicvoice-experimental'

_voices = {}
_load_lock = threading.Lock()
_synthesis_lock = threading.Lock()
_download_lock = threading.Lock()


class TTSUnavailable(RuntimeError):
    pass


def model_path(voice):
    return Path(settings.PIPER_MODEL_DIR) / f'{voice}.onnx'


def config_path(voice):
    return Path(settings.PIPER_CONFIG_DIR) / f'{voice}.onnx.json'


def model_available(voice='en_US-ljspeech-medium'):
    path = model_path(voice)
    return path.is_file() and config_path(voice).is_file()


def all_models_available():
    return all(model_available(voice) for voice, _label in VOICES if voice not in ONLINE_VOICES and voice not in PARLER_VOICES and voice != INDICVOICE_ID)


def model_configs_available():
    return all(config_path(voice).is_file() for voice, _label in VOICES if voice not in ONLINE_VOICES and voice not in PARLER_VOICES and voice != INDICVOICE_ID)


def ensure_model(voice_name):
    """Atomically download a missing ONNX model from the configured release."""
    path = model_path(voice_name)
    voice_config = config_path(voice_name)
    if not voice_config.is_file():
        raise TTSUnavailable(f'Voice configuration is missing for {voice_name}.')
    if path.is_file():
        return path
    with _download_lock:
        if path.is_file():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix('.onnx.part')
        url = (f'https://huggingface.co/rhasspy/piper-voices/resolve/main/bn/bn_BD/google/medium/{path.name}'
               if voice_name == PIPER_BANGLA else f'{settings.PIPER_MODEL_BASE_URL}/{path.name}')
        request = Request(url, headers={'User-Agent': 'NeuralVoiceStudio/1.0'})
        try:
            with urlopen(request, timeout=60) as response, open(partial, 'wb') as destination:
                shutil.copyfileobj(response, destination, length=1024 * 1024)
            if partial.stat().st_size < 10 * 1024 * 1024:
                raise TTSUnavailable(f'Downloaded model {voice_name} is unexpectedly small.')
            partial.replace(path)
        except (HTTPError, URLError, OSError) as exc:
            partial.unlink(missing_ok=True)
            raise TTSUnavailable(f'Could not download {voice_name} from the model release: {exc}') from exc
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    return path


def _get_voice(voice_name):
    try:
        from piper import PiperVoice
    except (ImportError, OSError) as exc:
        raise TTSUnavailable('The speech engine is temporarily unavailable.') from exc
    path = ensure_model(voice_name)
    cache_key = voice_name
    with _load_lock:
        if cache_key not in _voices:
            if settings.ON_VERCEL:
                # Keep only one loaded model and its disk cache per instance.
                _voices.clear()
                for cached in Path(settings.PIPER_MODEL_DIR).glob('*.onnx'):
                    if cached != path:
                        cached.unlink(missing_ok=True)
            _voices[cache_key] = PiperVoice.load(str(path), config_path=str(config_path(voice_name)))
    return _voices[cache_key]


def split_text(text, max_chars=3500):
    """Split long scripts on natural boundaries without losing content."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    units = re.split(r'(?<=[।॥。！？])\s*|(?<=[.!?])\s+|\n+', text)
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


async def _fetch_online_audio(text, voice, speed, destination):
    import edge_tts

    rate = f'{round((float(speed) - 1) * 100):+d}%'
    await asyncio.wait_for(
        edge_tts.Communicate(text, ONLINE_VOICES[voice], rate=rate,
                             connect_timeout=10, receive_timeout=60).save(str(destination)),
        timeout=240,
    )


def synthesize_online(text, voice, speed, output_path):
    from asgiref.sync import async_to_sync
    import miniaudio

    output_path = Path(output_path).with_suffix('.wav')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='online-', dir=output_path.parent) as directory:
            source = Path(directory) / 'speech.mp3'
            async_to_sync(_fetch_online_audio)(text, voice, speed, source)
            decoded = miniaudio.decode_file(str(source), nchannels=1, sample_rate=24000)
            with wave.open(str(output_path), 'wb') as destination:
                destination.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                destination.writeframes(decoded.samples.tobytes())
        return len(decoded.samples) / 24000
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise TTSUnavailable('The online Bangla voice service is unavailable. Please try again shortly.') from exc


def synthesize(text, voice, language, speed, output_path, audio_format='wav', emotion='narration'):
    if voice == PIPER_BANGLA:
        return synthesize_bangla_cpu(text, speed, output_path, emotion)
    if voice in PARLER_VOICES:
        from .parler import synthesize_parler
        return synthesize_parler(text, voice, speed, output_path, emotion=emotion)
    if voice == INDICVOICE_ID:
        from .indicvoice import synthesize_indicvoice
        with _synthesis_lock:
            if settings.ON_VERCEL:
                _voices.clear()
            return synthesize_indicvoice(text, speed, output_path)
    if voice in ONLINE_VOICES:
        return synthesize_online(text, voice, speed, output_path)
    try:
        from piper.config import SynthesisConfig
    except (ImportError, OSError) as exc:
        raise TTSUnavailable('The speech engine is temporarily unavailable.') from exc
    output_path = Path(output_path).with_suffix('.wav')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config = SynthesisConfig(length_scale=1 / float(speed), normalize_audio=True)
    try:
        chunks = split_text(text)
        if not chunks:
            raise TTSUnavailable('Enter text to synthesize.')
        # Generate bounded segments, then join their PCM frames into one lossless WAV.
        with _synthesis_lock, tempfile.TemporaryDirectory(prefix='piper-', dir=output_path.parent) as temp_dir:
            loaded_voice = _get_voice(voice)
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
        raise TTSUnavailable(f'Audio generation failed: {exc}') from exc


# Small pacing changes only: this model has no learned emotional style control.
CPU_MOOD_PACE = {'happy': 1.04, 'sad': .92, 'angry': 1.03, 'fear': .97, 'surprise': 1.03}


def synthesize_bangla_cpu(text, speed, output_path, emotion='auto'):
    import miniaudio
    from piper.config import SynthesisConfig
    from .parler import EMOTION_STYLES
    if emotion not in EMOTION_STYLES:
        raise TTSUnavailable('Unsupported story mood.')
    if emotion == 'auto':
        from .story import plan_story
        sections = plan_story(text)
    else:
        sections = [dict(text=chunk, emotion=emotion, pause_ms=250) for chunk in split_text(text, 250)]
    if not sections:
        raise TTSUnavailable('Enter text to synthesize.')
    output = Path(output_path).with_suffix('.wav')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _synthesis_lock, tempfile.TemporaryDirectory(prefix='bangla-cpu-', dir=output.parent) as directory:
            loaded = _get_voice(PIPER_BANGLA)
            with wave.open(str(output), 'wb') as destination:
                destination.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                for index, section in enumerate(sections):
                    part = Path(directory) / 'part.wav'
                    pace = float(speed) * CPU_MOOD_PACE.get(section['emotion'], 1)
                    config = SynthesisConfig(speaker_id=0, length_scale=1 / pace, normalize_audio=True)
                    with wave.open(str(part), 'wb') as wav_file:
                        loaded.synthesize_wav(section['text'], wav_file, syn_config=config)
                    audio = miniaudio.decode_file(str(part), nchannels=1, sample_rate=24000)
                    if index:
                        destination.writeframes(bytes(48 * section['pause_ms']))
                    destination.writeframes(audio.samples.tobytes())
        with wave.open(str(output), 'rb') as wav_file:
            return wav_file.getnframes() / wav_file.getframerate()
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, TTSUnavailable):
            raise
        raise TTSUnavailable('CPU Bangla generation failed. Please try again.') from exc
