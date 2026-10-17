from django import forms
from django.conf import settings


from .services import INDICVOICE_ID, LANGUAGES, VOICES


class SpeechForm(forms.Form):
    text = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'এখানে আপনার বাংলা গল্প, কথোপকথন বা ভয়েসওভারের লেখা দিন…', 'autofocus': True}))
    title = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional project title'}))
    language = forms.ChoiceField(choices=LANGUAGES, initial='bn_BD')
    voice = forms.ChoiceField(choices=VOICES, initial='bn_BD-aditi-parler')
    speed = forms.DecimalField(min_value=0.5, max_value=2.0, decimal_places=2, initial=1, widget=forms.NumberInput(attrs={'step': '.05', 'type': 'range'}))
    format = forms.ChoiceField(choices=[('wav', 'WAV — PCM audio')], initial='wav')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.ON_VERCEL:
            self.fields['voice'].choices = [(v, label) for v, label in VOICES if v != INDICVOICE_ID]

    def clean(self):
        data = super().clean()
        voice = data.get('voice', '')
        language = data.get('language')
        if voice and language and not voice.startswith(f'{language}-'):
            self.add_error('voice', 'Select a voice that matches the chosen language/accent.')
        if voice == INDICVOICE_ID and len(data.get('text', '')) > 1000:
            self.add_error('text', 'IndicVoice experimental supports up to 1,000 characters per generation. Other voices support up to 20,000.')
        return data
