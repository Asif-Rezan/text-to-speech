from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import SpeechForm
from .models import SpeechGeneration
from .services import VOICES, model_configs_available, synthesize


@require_http_methods(['GET', 'POST'])
def studio(request):
    form = SpeechForm(request.POST or None)
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if request.method == 'POST' and form.is_valid():
        item = SpeechGeneration.objects.create(**form.cleaned_data)
        output = Path(settings.MEDIA_ROOT) / 'audio' / item.created_at.strftime('%Y/%m') / f'{item.public_id}.{item.format}'
        try:
            item.duration_seconds = synthesize(item.text, item.voice, item.language, item.speed, output, item.format)
            item.audio_file.name = str(output.relative_to(settings.MEDIA_ROOT)).replace('\\', '/')
            item.status = 'completed'
            item.save(update_fields=['duration_seconds', 'audio_file', 'status'])
            if not wants_json:
                messages.success(request, 'Your audio is ready to play and download.')
        except Exception as exc:
            item.status = 'failed'
            item.error_message = str(exc)[:500]
            item.save(update_fields=['status', 'error_message'])
            if not wants_json:
                messages.error(request, item.error_message)
        if wants_json:
            status_code = 201 if item.status == 'completed' else 503
            return JsonResponse({
                'ok': item.status == 'completed',
                'status': item.status,
                'message': 'Your audio is ready.' if item.status == 'completed' else item.error_message,
                'card_html': render_to_string('studio/_audio_card.html', {'item': item}, request=request),
            }, status=status_code)
        return redirect('studio:home')
    if request.method == 'POST' and wants_json:
        return JsonResponse({'ok': False, 'message': 'Please correct the highlighted fields.', 'errors': form.errors.get_json_data()}, status=422)
    history = SpeechGeneration.objects.all()[:6]
    return render(request, 'studio/home.html', {'form': form, 'history': history, 'site_url': settings.PUBLIC_SITE_URL})


@require_GET
def download(request, public_id):
    item = get_object_or_404(SpeechGeneration, public_id=public_id, status='completed')
    if not item.audio_file or not Path(item.audio_file.path).is_file():
        raise Http404('Audio file not found')
    return FileResponse(open(item.audio_file.path, 'rb'), as_attachment=True, filename=f'{item.display_title[:50]}.{item.format}')


@require_POST
def delete(request, public_id):
    item = get_object_or_404(SpeechGeneration, public_id=public_id)
    if item.audio_file:
        item.audio_file.delete(save=False)
    item.delete()
    messages.success(request, 'Generation removed.')
    return redirect('studio:home')


@require_GET
def health(request):
    ready = model_configs_available()
    return JsonResponse({'status': 'ok' if ready else 'degraded', 'service': 'Free Text to Speech', 'voice_count': len(VOICES)}, status=200 if ready else 503)


@require_GET
def robots(request):
    content = f'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /audio/\nSitemap: {settings.PUBLIC_SITE_URL}/sitemap.xml\n'
    return HttpResponse(content, content_type='text/plain')


@require_GET
def sitemap(request):
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{settings.PUBLIC_SITE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
</urlset>'''
    return HttpResponse(content, content_type='application/xml')
