import base64
import json
import tempfile
import array
import wave
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SpeechGeneration
from .services import INDICVOICE_ID, ONLINE_VOICES, TTSUnavailable, _fetch_online_audio, split_text, synthesize
from .forms import SpeechForm


class StudioTests(TestCase):
    @override_settings(ON_VERCEL=True)
    def test_vercel_delivers_audio_in_generation_response(self):
        audio = b'RIFF' + bytes(range(256)) * 20000
        def generate(text, voice, language, speed, output, fmt):
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(audio)
            return 43.0
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            with patch('studio.views.synthesize', side_effect=generate):
                response = self.client.post(reverse('studio:home'), {
                    'text': 'চলুন একটি নতুন গল্প শুনি।', 'language': 'bn_BD',
                    'voice': 'bn_BD-aditi-parler', 'speed': '1', 'format': 'wav',
                }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(response.status_code, 201)
                self.assertTrue(response.streaming)
                packets = [json.loads(line) for line in b''.join(response.streaming_content).splitlines()]
                self.assertTrue(packets[0]['ok'])
                self.assertTrue(packets[-1]['complete'])
                self.assertEqual(b''.join(base64.b64decode(p['audio']) for p in packets if 'audio' in p), audio)

    def test_indicvoice_is_additional_and_has_its_own_text_limit(self):
        from .services import VOICES
        self.assertEqual(len(VOICES), 23)
        self.assertEqual(len(ONLINE_VOICES), 4)
        self.assertEqual(len([v for v, _ in VOICES if v.startswith('bn_BD-')]), 7)
        values = {'text': 'আমি বাংলায় কথা বলি।', 'language': 'bn_BD',
                  'voice': INDICVOICE_ID, 'speed': '1.00', 'format': 'wav'}
        self.assertTrue(SpeechForm(values).is_valid())
        values['text'] = 'ক' * 1001
        self.assertIn('text', SpeechForm(values).errors)
        values['voice'] = 'bn_BD-nabanita-neural'
        self.assertTrue(SpeechForm(values).is_valid())

    @patch('studio.indicvoice.synthesize_indicvoice', return_value=2.0)
    @patch('studio.services.synthesize_online')
    def test_indicvoice_does_not_fall_back_to_an_online_model(self, online, local):
        self.assertEqual(synthesize('চলো গল্প শুনি।', INDICVOICE_ID, 'bn_BD', 1, '/tmp/indic.wav'), 2.0)
        local.assert_called_once()
        online.assert_not_called()

    def test_bangla_online_voices_validate(self):
        for voice in ONLINE_VOICES:
            form = SpeechForm({'text': 'চলো গল্প শুনি।', 'language': 'bn_BD',
                               'voice': voice, 'speed': '1.10', 'format': 'wav'})
            self.assertTrue(form.is_valid(), form.errors)

    @patch('edge_tts.Communicate')
    def test_online_voice_and_pace_are_sent_correctly(self, communicate):
        from asgiref.sync import async_to_sync
        communicate.return_value.save = AsyncMock()
        for voice, provider_voice in ONLINE_VOICES.items():
            async_to_sync(_fetch_online_audio)('চলো গল্প শুনি।', voice, 1.1, '/tmp/test.mp3')
            self.assertEqual(communicate.call_args.args[1], provider_voice)
            self.assertEqual(communicate.call_args.kwargs['rate'], '+10%')

    @patch('miniaudio.decode_file')
    @patch('studio.services._fetch_online_audio', new_callable=AsyncMock)
    def test_online_audio_becomes_valid_wav(self, fetch, decode):
        decode.return_value = SimpleNamespace(samples=array.array('h', [100] * 2400))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'audio.wav'
            duration = synthesize('চলো গল্প শুনি।', 'bn_BD-nabanita-neural', 'bn_BD', 1, output)
            self.assertAlmostEqual(duration, 0.1)
            with wave.open(str(output)) as audio:
                self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getframerate()), (1, 2, 24000))

    @patch('studio.services._fetch_online_audio', new_callable=AsyncMock, side_effect=TimeoutError)
    def test_online_failure_removes_partial_audio(self, fetch):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'audio.wav'
            output.write_bytes(b'partial')
            with self.assertRaisesMessage(TTSUnavailable, 'online Bangla voice service is unavailable'):
                synthesize('চলো গল্প শুনি।', 'bn_BD-nabanita-neural', 'bn_BD', 1, output)
            self.assertFalse(output.exists())

    def test_home_and_health(self):
        home = self.client.get(reverse('studio:home'))
        self.assertContains(home, 'Free Text to Speech Online')
        self.assertContains(home, 'FAQPage')
        health = self.client.get(reverse('studio:health'))
        self.assertEqual(health.status_code, 200)
        self.assertNotIn('engine', health.json())

    @override_settings(PUBLIC_SITE_URL='https://voice.example.com')
    def test_search_engine_files(self):
        robots = self.client.get(reverse('studio:robots'))
        self.assertContains(robots, 'Sitemap: https://voice.example.com/sitemap.xml')
        sitemap = self.client.get(reverse('studio:sitemap'))
        self.assertEqual(sitemap['Content-Type'], 'application/xml')
        self.assertContains(sitemap, '<loc>https://voice.example.com/</loc>')

    def test_home_shows_only_six_latest_generations(self):
        for index in range(8):
            SpeechGeneration.objects.create(title=f'Project {index}', text=f'Audio text {index}', status='failed')
        response = self.client.get(reverse('studio:home'))
        self.assertEqual(response.content.count(b'data-generation-id='), 6)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('studio.views.synthesize', return_value=2.5)
    def test_generation_is_persisted(self, synthesize):
        response = self.client.post(reverse('studio:home'), {'text': 'Hello from the studio.', 'title': 'Test', 'language': 'en_US', 'voice': 'en_US-ljspeech-medium', 'speed': '1.00', 'format': 'wav'})
        self.assertRedirects(response, reverse('studio:home'))
        self.assertEqual(SpeechGeneration.objects.get().status, 'completed')
        synthesize.assert_called_once()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('studio.views.synthesize', return_value=2.5)
    def test_ajax_generation_returns_audio_card(self, synthesize):
        response = self.client.post(
            reverse('studio:home'),
            {'text': 'Generated without a reload.', 'title': 'AJAX Test', 'language': 'en_US', 'voice': 'en_US-ljspeech-medium', 'speed': '1.00', 'format': 'wav'},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['ok'])
        self.assertIn('<audio', response.json()['card_html'])
        self.assertIn('preload="metadata"', response.json()['card_html'])
        self.assertIn('Download WAV', response.json()['card_html'])
        self.assertIn('3 sec', response.json()['card_html'])

    def test_rejects_mismatched_voice(self):
        self.client.post(reverse('studio:home'), {'text': 'Hello', 'language': 'en_GB', 'voice': 'en_US-ljspeech-medium', 'speed': '1', 'format': 'wav'})
        self.assertFalse(SpeechGeneration.objects.exists())

    def test_ajax_validation_returns_field_details(self):
        response = self.client.post(
            reverse('studio:home'),
            {'text': '', 'language': 'en_GB', 'voice': 'en_US-ljspeech-medium', 'speed': '3', 'format': 'mp3'},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn('text', response.json()['errors'])
        self.assertIn('voice', response.json()['errors'])

    def test_long_text_is_split_on_safe_boundaries(self):
        text = ('A complete sentence with several words. ' * 220).strip()
        chunks = split_text(text, max_chars=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 500 for chunk in chunks))
        self.assertEqual(' '.join(chunks).split(), text.split())

    def test_duration_is_formatted_as_minutes_and_seconds(self):
        item = SpeechGeneration(duration_seconds=125.7)
        self.assertEqual(item.duration_label, '2 min 6 sec')

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('studio.views.synthesize', return_value=180.0)
    def test_accepts_more_than_five_thousand_characters(self, synthesize):
        long_text = ('This is a long narration sentence. ' * 200).strip()
        self.assertGreater(len(long_text), 5000)
        response = self.client.post(
            reverse('studio:home'),
            {'text': long_text, 'language': 'en_US', 'voice': 'en_US-ljspeech-medium', 'speed': '1', 'format': 'wav'},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SpeechGeneration.objects.get().text, long_text)


class ExpressiveBanglaTests(TestCase):
    def test_bangla_is_default_and_expressive_limit_is_validated(self):
        form = SpeechForm()
        self.assertEqual(form.fields['language'].initial, 'bn_BD')
        self.assertEqual(form.fields['voice'].initial, 'bn_BD-aditi-parler')
        values = {'text': 'ক' * 1001, 'language': 'bn_BD', 'voice': 'bn_BD-aditi-parler', 'speed': '1', 'format': 'wav'}
        self.assertIn('text', SpeechForm(values).errors)
        values['voice'] = 'bn_BD-nabanita-neural'
        self.assertTrue(SpeechForm(values).is_valid())

    @override_settings(ON_VERCEL=True)
    def test_vercel_excludes_local_gpu_runtime(self):
        choices = dict(SpeechForm().fields['voice'].choices)
        self.assertNotIn(INDICVOICE_ID, choices)
        self.assertIn('bn_BD-aditi-parler', choices)

    def test_bangla_sentences_without_spaces_still_split(self):
        chunks = split_text('আমি ভালো আছি।তুমি কেমন আছো? আজ বৃষ্টি হবে।', max_chars=20)
        self.assertEqual(chunks[0], 'আমি ভালো আছি।')
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))

    @patch('studio.parler.urlopen')
    def test_gpu_quota_error_is_actionable(self, urlopen):
        import io
        from studio.parler import _generate
        import time
        urlopen.side_effect = [io.BytesIO(b'{"event_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'),
                               io.BytesIO(b'event: error\ndata: "quota exceeded"\n\n')]
        with self.assertRaisesMessage(TTSUnavailable, 'quota is exhausted'):
            _generate('বাংলা কথা।', 'Aditi', 1, time.monotonic() + 10)

    @patch('studio.parler.urlopen')
    def test_remote_file_path_cannot_escape_gradio(self, urlopen):
        import io
        from studio.parler import _generate
        import time
        urlopen.side_effect = [io.BytesIO(b'{"event_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'),
                               io.BytesIO(b'event: complete\ndata: [{"path":"/etc/passwd"}]\n\n')]
        with self.assertRaisesMessage(TTSUnavailable, 'did not return audio'):
            _generate('বাংলা কথা।', 'Aditi', 1, time.monotonic() + 10)

    @patch('studio.parler._generate', side_effect=TimeoutError)
    def test_failed_expressive_generation_leaves_no_partial_download(self, generate):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'speech.wav'
            with self.assertRaises(TTSUnavailable):
                synthesize('বাংলা কথা।', 'bn_BD-aditi-parler', 'bn_BD', 1, output)
            self.assertFalse(output.exists())
