import uuid
from pathlib import Path

from django.db import models


def audio_upload_path(instance, filename):
    return f'audio/{instance.created_at:%Y/%m}/{instance.public_id}.{Path(filename).suffix.lstrip(".")}'


class SpeechGeneration(models.Model):
    STATUS_CHOICES = [('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')]
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=120, blank=True)
    text = models.TextField()
    voice = models.CharField(max_length=40, default='en_US-ljspeech-medium')
    language = models.CharField(max_length=8, default='en_US')
    speed = models.DecimalField(max_digits=3, decimal_places=2, default=1.00)
    format = models.CharField(max_length=8, default='wav')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='processing', db_index=True)
    audio_file = models.FileField(upload_to=audio_upload_path, blank=True)
    duration_seconds = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or str(self.public_id)

    @property
    def display_title(self):
        return self.title or self.text[:48] + ('…' if len(self.text) > 48 else '')

    @property
    def duration_label(self):
        if self.duration_seconds is None:
            return ''
        total_seconds = max(0, int(float(self.duration_seconds) + 0.5))
        minutes, seconds = divmod(total_seconds, 60)
        if minutes:
            return f'{minutes} min {seconds} sec'
        return f'{seconds} sec'
