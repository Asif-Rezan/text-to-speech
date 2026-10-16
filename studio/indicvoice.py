"""Optional IndicVoice inference; imports its large runtime only when selected."""
import gc
import hashlib
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
import wave

from django.conf import settings

REVISION = '2cf8fffbdf72a6fdee5cf841323a161d958b2e0a'
FILES = {
    'config.json': '9de52c5827e3d25069077b3da55bb011a1f29568ea15346745657e779720d8f3',
    'voices/hf_beta.pt': '63c0a1a6272e98d43f4511bba40e30dd9c8ceaf5f39af869509b9f51a71c503e',
    'indicvoice-v1_0.pth': '496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4',
}


def ensure_assets():
    root = settings.RUNTIME_DIR / 'models' / 'indicvoice'
    for name, expected_hash in FILES.items():
        path = root / name
        if path.is_file():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f'https://huggingface.co/Bindkushal/IndicVoice-82M/resolve/{REVISION}/{name}'
        partial = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
                partial = Path(target.name)
                digest = hashlib.sha256()
                with urlopen(Request(url, headers={'User-Agent': 'NeuralVoiceStudio/1.0'}), timeout=60) as source:
                    while chunk := source.read(1024 * 1024):
                        target.write(chunk)
                        digest.update(chunk)
            if digest.hexdigest() != expected_hash:
                raise ValueError(f'IndicVoice asset checksum failed: {name}')
            partial.replace(path)
        finally:
            if partial:
                partial.unlink(missing_ok=True)
    return root


class BanglaPhonemizer:
    """Repair the upstream non-English token API without English token objects."""
    def __init__(self):
        from indicg2p.bn import G2P
        self.g2p = G2P()

    def __call__(self, text):
        # Join phonemes within words, and preserve boundaries between words.
        return ' '.join(''.join(self.g2p._word_to_phonemes(word))
                        for word in text.split()), []


def synthesize_indicvoice(text, speed, output_path):
    from .services import TTSUnavailable, split_text

    output = Path(output_path).with_suffix('.wav')
    output.parent.mkdir(parents=True, exist_ok=True)
    model = pipeline = None
    try:
        if not text.strip() or len(text) > 1000:
            raise TTSUnavailable('IndicVoice experimental requires 1–1,000 characters.')
        import numpy as np
        import torch
        from indicvoice import IndicModel, IndicPipeline
        from indicvoice import pipeline as pipeline_module

        root = ensure_assets()
        torch.set_num_threads(2)
        model = IndicModel(repo_id='Bindkushal/IndicVoice-82M',
                           config=str(root / 'config.json'),
                           model=str(root / 'indicvoice-v1_0.pth')).eval()
        # Upstream has a Bengali frontend but omits bn from its validation table.
        pipeline_module.LANG_CODES.setdefault('bn', 'Bengali')
        pipeline = IndicPipeline(lang_code='bn', repo_id='Bindkushal/IndicVoice-82M',
                                 model=model, device='cpu')
        pipeline.g2p = BanglaPhonemizer()
        frames = 0
        with wave.open(str(output), 'wb') as wav_file:
            wav_file.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            # Short chunks prevent upstream's silent phoneme truncation.
            for chunk in split_text(text, max_chars=80):
                for result in pipeline(chunk, voice=str(root / 'voices/hf_beta.pt'), speed=float(speed)):
                    if result.audio is None:
                        raise TTSUnavailable('IndicVoice returned no audio.')
                    audio = result.audio.numpy()
                    if not audio.size or not np.isfinite(audio).all():
                        raise TTSUnavailable('IndicVoice returned invalid audio.')
                    wav_file.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())
                    frames += audio.size
        if not frames:
            raise TTSUnavailable('IndicVoice returned no audio.')
        return frames / 24000
    except Exception as exc:
        output.unlink(missing_ok=True)
        if isinstance(exc, TTSUnavailable):
            raise
        raise TTSUnavailable('IndicVoice experimental is unavailable. Please select another voice.') from exc
    finally:
        # Retain downloaded weights, but release this optional model's RAM.
        del pipeline, model
        gc.collect()
