"""Semantic story-emotion planning with a pinned, CPU-only ONNX classifier."""
import hashlib
import io
import logging
import re
import threading
from urllib.request import Request, urlopen

MODEL = 'Horizon-Labs/multilingual-emotions-small'
REVISION = '1bc9627f189e5aa08b00cf525c3c86052067b81e'
ASSETS = {
    'onnx/model_quantized.onnx': '7fed4f82f2e1c4039452876e87ef948f5eedfdcf45f351470010e0ed65f1e9ee',
    'tokenizer.json': '4379fe7f4a7af10b1ac15ffc8ae90f446f92082393699e9dd54b8c3b5ec0abad',
}
LABELS = ('admiration amusement anger annoyance approval caring confusion curiosity desire '
          'disappointment disapproval disgust embarrassment excitement fear gratitude grief joy '
          'love nervousness optimism pride realization relief remorse sadness surprise neutral').split()
GROUPS = {
    'happy': ('joy', 'amusement', 'excitement', 'gratitude', 'love', 'relief', 'optimism', 'pride'),
    'sad': ('sadness', 'grief', 'disappointment', 'remorse'),
    'angry': ('anger', 'annoyance'),
    'fear': ('fear', 'nervousness'),
    'surprise': ('surprise',),
}
_lock = threading.Lock()
_classifier = None


def _read_asset(name, expected, max_bytes):
    # Vercel scratch storage may be smaller than this model. Verified assets go
    # straight into memory; no temporary weight files or duplicate disk caches.
    digest = hashlib.sha256()
    buffer = io.BytesIO()
    url = f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}'
    with urlopen(Request(url, headers={'User-Agent': 'NeuralVoiceStudio/1.0'}), timeout=60) as source:
        while chunk := source.read(1024 * 1024):
            if buffer.tell() + len(chunk) > max_bytes:
                raise ValueError('Story model asset is larger than expected.')
            buffer.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError('Story model checksum mismatch.')
    return buffer.getvalue()


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is not None:
            return _classifier
        import onnxruntime as ort
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_str(_read_asset('tokenizer.json', ASSETS['tokenizer.json'], 34363286).decode('utf-8'))
        tokenizer.enable_truncation(max_length=256)
        tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.enable_mem_pattern = False
        session = ort.InferenceSession(
            _read_asset('onnx/model_quantized.onnx', ASSETS['onnx/model_quantized.onnx'], 268449278),
            sess_options=options, providers=['CPUExecutionProvider'])
        _classifier = (tokenizer, session)
        return _classifier


def classify_passages(texts):
    """Return independent GoEmotions probabilities; text never leaves this server."""
    import numpy as np
    tokenizer, session = _load_classifier()
    results = []
    # Tokenizer padding/truncation settings are shared; serialize encode + inference.
    with _lock:
        for start in range(0, len(texts), 8):
            encoded = tokenizer.encode_batch(texts[start:start + 8])
            inputs = {
                'input_ids': np.asarray([row.ids for row in encoded], dtype=np.int64),
                'attention_mask': np.asarray([row.attention_mask for row in encoded], dtype=np.int64),
            }
            logits = session.run(None, {item.name: inputs[item.name] for item in session.get_inputs()})[0]
            probabilities = 1 / (1 + np.exp(-np.clip(logits, -60, 60)))
            results.extend(dict(zip(LABELS, map(float, row))) for row in probabilities)
    return results


def choose_delivery(scores):
    ranked = sorted(((mood, max(scores.get(label, 0) for label in labels))
                     for mood, labels in GROUPS.items()), key=lambda item: item[1], reverse=True)
    mood, confidence = ranked[0]
    # Ambiguous prose is narration, rather than an exaggerated emotional guess.
    if confidence < .35 or confidence < scores.get('neutral', 0) + .08 or confidence - ranked[1][1] < .06:
        return 'narration', confidence
    return mood, confidence


def plan_story(text):
    """Detect sentence moods, use nearby context for ambiguous short lines, then group."""
    from .services import split_text, TTSUnavailable
    if not text.strip() or len(text) > 20000:
        raise TTSUnavailable('Enter a story with 1–20,000 characters.')
    passages = []
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\n', text.strip()) if p.strip()]
    for paragraph_id, paragraph in enumerate(paragraphs):
        cursor = 0
        for sentence in filter(None, (s.strip() for s in re.split(r'(?<=[।!?])\s*|(?<=\.)\s+', paragraph))):
            position = paragraph.find(sentence, cursor)
            passages.append({'text': sentence, 'paragraph': paragraph_id, 'start': position})
            cursor = position + len(sentence)
    try:
        # Each sentence has its own score, plus a bounded paragraph context. Long
        # paragraphs use nearby text rather than silently truncating the whole story.
        contexts = []
        for item in passages:
            paragraph = paragraphs[item['paragraph']]
            if len(paragraph) <= 500:
                contexts.append(paragraph)
            else:
                position = item['start']
                contexts.append(paragraph[max(0, position - 120):position + len(item['text']) + 120])
        unique = list(dict.fromkeys([item['text'] for item in passages] + contexts))
        predictions = dict(zip(unique, classify_passages(unique)))
        moods = []
        for item, context in zip(passages, contexts):
            sentence_mood, sentence_confidence = choose_delivery(predictions[item['text']])
            context_mood, context_confidence = choose_delivery(predictions[context])
            # Clear local emotion can mark a turn inside a paragraph. Otherwise,
            # the paragraph supplies the mood for short dialogue and continuations.
            if sentence_mood != 'narration' and sentence_confidence >= .75:
                moods.append((sentence_mood, sentence_confidence))
            elif context_mood != 'narration':
                moods.append((context_mood, context_confidence))
            elif sentence_mood != 'narration' and sentence_confidence >= .65:
                moods.append((sentence_mood, sentence_confidence))
            else:
                moods.append(('narration', context_confidence))
        plan = []
        previous_paragraph = None
        for passage, (mood, confidence) in zip(passages, moods):
            paragraph_break = previous_paragraph is not None and passage['paragraph'] != previous_paragraph
            for piece in split_text(passage['text'], max_chars=250):
                if (plan and not paragraph_break and plan[-1]['emotion'] == mood
                        and len(plan[-1]['text']) + len(piece) + 1 <= 250):
                    plan[-1]['text'] += ' ' + piece
                else:
                    pause = 500 if paragraph_break else 350 if plan and plan[-1]['emotion'] != mood else 200
                    plan.append({'text': piece, 'emotion': mood,
                                 'confidence': round(confidence, 3), 'pause_ms': pause if plan else 0})
                paragraph_break = False
            previous_paragraph = passage['paragraph']
        return plan
    except Exception as exc:
        if isinstance(exc, TTSUnavailable):
            raise
        logging.getLogger(__name__).exception('Automatic story analysis failed')
        raise TTSUnavailable('Story emotion analysis is unavailable. Please try again shortly.') from exc
