import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SpeechGeneration
from .services import split_text


class StudioTests(TestCase):
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
