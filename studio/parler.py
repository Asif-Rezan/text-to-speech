"""Small HTTP client for AI4Bharat's public, GPU-hosted Indic Parler demo.

No model weights or GPU libraries are loaded inside the Vercel function.
"""
import json
import re
import tempfile
import time
import wave
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOST = 'https://ai4bharat-indic-parler-tts.hf.space'
VOICES = {'bn_BD-aditi-parler': 'Aditi', 'bn_BD-arjun-parler': 'Arjun'}
MAX_CHARS = 20000
MAX_SECONDS = 220

EMOTION_STYLES = {
    'auto': ('স্বয়ংক্রিয় আবেগ / Automatic', 'natural story narration, matching the emotion expressed in the text'),
    'narration': ('গল্প বলা / Storytelling', 'an expressive storytelling tone, with varied intonation and natural dramatic pauses'),
    'conversation': ('কথোপকথন / Conversation', 'a friendly, conversational tone, sounding engaged and natural'),
    'happy': ('আনন্দ / Happy', 'a cheerful, happy tone, sounding joyful and animated'),
    'sad': ('দুঃখ / Sad', 'a sad, subdued tone, sounding sorrowful with a gentle, soft delivery'),
    'angry': ('রাগ / Angry', 'an angry, forceful tone, sounding frustrated and emphatic'),
    'fear': ('ভয় / Fear', 'a fearful, nervous tone, sounding tense and worried'),
    'surprise': ('বিস্ময় / Surprise', 'a surprised, astonished tone, with lively changes in pitch'),
    'news': ('সংবাদ / News', 'a clear, composed newsreader tone, sounding professional and confident'),
    'neutral': ('স্বাভাবিক / Neutral', 'a clear, neutral tone, with no emotional emphasis'),
}
EMOTION_CHOICES = [(key, label) for key, (label, _) in EMOTION_STYLES.items()]


def voice_description(speaker, speed, emotion='narration'):
    if emotion not in EMOTION_STYLES:
        raise ValueError('Unsupported Bangla emotion.')
    pace = 'slow' if float(speed) < .9 else 'fast' if float(speed) > 1.1 else 'moderate'
    return (
        f'{speaker} speaks with {EMOTION_STYLES[emotion][1]}, at a {pace} speaking pace. '
        'The voice is clear and close, and the recording is very high quality with no background noise.'
    )


def _generate(text, speaker, speed, deadline, emotion='narration'):
    from .services import TTSUnavailable

    description = voice_description(speaker, speed, emotion)
    endpoint = f'{HOST}/gradio_api/call/generate_finetuned'

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TTSUnavailable('The expressive Bangla service took too long. Try a shorter script.')
        return min(60, seconds)

    request = Request(endpoint, data=json.dumps({'data': [text, description]}).encode(),
                      headers={'Content-Type': 'application/json', 'User-Agent': 'NeuralVoiceStudio/1.0'})
    with urlopen(request, timeout=remaining()) as response:
        event_id = json.load(response).get('event_id', '')
    if not re.fullmatch(r'[a-f0-9]{32}', event_id):
        raise TTSUnavailable('The expressive Bangla service returned an invalid job.')
    event = ''
    with urlopen(f'{endpoint}/{event_id}', timeout=remaining()) as response:
        for raw in response:
            remaining()
            line = raw.decode('utf-8').strip()
            if line.startswith('event:'):
                event = line[6:].strip()
            elif line.startswith('data:') and event == 'error':
                # Do not expose upstream traces or internal paths.
                raise TTSUnavailable('The free Bangla GPU service is busy or its quota is exhausted. '
                                     'Try again later, or select Nabanita / Pradeep.')
            elif line.startswith('data:') and event == 'complete':
                result = json.loads(line[5:])
                item = result[0] if isinstance(result, list) and result else None
                if not isinstance(item, dict):
                    break
                # Gradio's returned URL can contain an erroneous /c/ prefix;
                # use its file path only, and never follow an arbitrary host.
                path = item.get('path', '')
                if not path.startswith('/tmp/gradio/') or '..' in path or '?' in path or '#' in path:
                    break
                return f'{HOST}/gradio_api/file={path}'
    raise TTSUnavailable('The expressive Bangla service did not return audio.')


def synthesize_parler(text, voice, speed, output_path, emotion='narration'):
    import miniaudio
    from .services import TTSUnavailable, split_text

    output = Path(output_path).with_suffix('.wav')
    output.parent.mkdir(parents=True, exist_ok=True)
    if voice not in VOICES or not text.strip() or len(text) > MAX_CHARS:
        raise TTSUnavailable('Expressive Bangla supports 1–20,000 characters per generation.')
    deadline = time.monotonic() + MAX_SECONDS
    frames = 0
    try:
        if emotion == 'auto':
            from .story import plan_story
            sections = plan_story(text)
        else:
            sections = [{'text': chunk, 'emotion': emotion, 'pause_ms': 200}
                        for chunk in split_text(text, max_chars=250)]
        with tempfile.TemporaryDirectory(prefix='parler-', dir=output.parent) as directory:
            with wave.open(str(output), 'wb') as destination:
                destination.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                for index, section in enumerate(sections):
                    url = _generate(section['text'], VOICES[voice], speed, deadline, emotion=section['emotion'])
                    source = Path(directory) / f'{index}.audio'
                    if time.monotonic() >= deadline:
                        raise TimeoutError
                    with urlopen(url, timeout=min(30, deadline - time.monotonic())) as response, source.open('wb') as target:
                        if urlsplit(response.url).netloc != urlsplit(HOST).netloc:
                            raise ValueError('Unexpected audio host')
                        # Bound downloads from the public service to 12 MB per segment.
                        data = response.read(12 * 1024 * 1024 + 1)
                        if len(data) > 12 * 1024 * 1024:
                            raise ValueError('Audio response too large')
                        target.write(data)
                    decoded = miniaudio.decode_file(str(source), nchannels=1, sample_rate=24000)
                    if not len(decoded.samples):
                        raise ValueError('Empty audio')
                    if frames:
                        # A short sentence pause avoids abrupt joins between GPU calls.
                        pause_frames = round(section.get('pause_ms', 200) * 24)
                        destination.writeframes(b'\0\0' * pause_frames)
                        frames += pause_frames
                    destination.writeframes(decoded.samples.tobytes())
                    frames += len(decoded.samples)
        return frames / 24000
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, TTSUnavailable):
            raise
        raise TTSUnavailable('The expressive Bangla service is unavailable. Try again later, '
                             'or select Nabanita / Pradeep.') from exc
