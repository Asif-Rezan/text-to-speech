from django import forms

from .services import LANGUAGES, VOICES


class SpeechForm(forms.Form):
    text = forms.CharField(max_length=20000, widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'Paste a script, article, narration, or announcement…', 'autofocus': True}))
    title = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional project title'}))
    language = forms.ChoiceField(choices=LANGUAGES, initial='en_US')
    voice = forms.ChoiceField(choices=VOICES, initial='en_US-ljspeech-medium')
    speed = forms.DecimalField(min_value=0.5, max_value=2.0, decimal_places=2, initial=1, widget=forms.NumberInput(attrs={'step': '.05', 'type': 'range'}))
    format = forms.ChoiceField(choices=[('wav', 'WAV — lossless')], initial='wav')

    def clean(self):
        data = super().clean()
        voice = data.get('voice', '')
        language = data.get('language')
        if voice and language and not voice.startswith(f'{language}-'):
            self.add_error('voice', 'Select a voice that matches the chosen language/accent.')
        return data
