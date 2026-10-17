from django import forms
from django.conf import settings

from .parler import EMOTION_CHOICES, VOICES as PARLER_VOICES

from .services import INDICVOICE_ID, LANGUAGES, VOICES


class SpeechForm(forms.Form):
    text = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'Enter your Bangla story, dialogue, or voiceover script here…', 'autofocus': True}))
    title = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional project title'}))
    language = forms.ChoiceField(choices=LANGUAGES, initial='bn_BD')
    voice = forms.ChoiceField(choices=VOICES, initial='bn_BD-nabanita-neural')
    emotion = forms.ChoiceField(choices=EMOTION_CHOICES, initial='auto', required=False, widget=forms.HiddenInput())
    speed = forms.DecimalField(min_value=0.5, max_value=2.0, decimal_places=2, initial=1, widget=forms.NumberInput(attrs={'step': '.05', 'type': 'range'}))
    format = forms.ChoiceField(choices=[('wav', 'WAV — PCM audio')], initial='wav')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.ON_VERCEL:
            self.fields['voice'].choices = [(v, label) for v, label in VOICES if v != INDICVOICE_ID]

    def clean_emotion(self):
        return self.cleaned_data.get('emotion') or 'auto'

    def clean(self):
        data = super().clean()
        voice = data.get('voice', '')
        language = data.get('language')
        if voice and language and not voice.startswith(f'{language}-'):
            self.add_error('voice', 'Select a voice that matches the chosen language/accent.')
        if voice and voice not in PARLER_VOICES and data.get('emotion', 'auto') not in ('auto', 'narration'):
            self.add_error('emotion', 'Select Aditi or Arjun for emotion control.')
        if voice == INDICVOICE_ID and len(data.get('text', '')) > 1000:
            self.add_error('text', 'IndicVoice experimental supports up to 1,000 characters per generation. Other voices support up to 20,000.')
        return data
