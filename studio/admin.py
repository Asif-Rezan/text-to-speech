from django.contrib import admin

from .models import SpeechGeneration


@admin.register(SpeechGeneration)
class SpeechGenerationAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'voice', 'format', 'status', 'duration_seconds', 'created_at')
    list_filter = ('status', 'format', 'language', 'voice')
    search_fields = ('title', 'text', 'public_id')
    readonly_fields = ('public_id', 'created_at')
