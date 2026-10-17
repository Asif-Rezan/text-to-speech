import base64
import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .parler import VOICES as PARLER_VOICES, EMOTION_STYLES
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import SpeechForm
from .models import SpeechGeneration
from .services import VOICES, STORY_VOICES, model_configs_available, synthesize


@require_http_methods(['GET', 'POST'])
def studio(request):
    form = SpeechForm(request.POST or None)
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if request.method == 'POST' and form.is_valid():
        segment = request.POST.get('segment_text') if wants_json else None
        if segment is not None and (form.cleaned_data['voice'] not in STORY_VOICES or not segment.strip() or len(segment) > 250):
            return JsonResponse({'ok': False, 'message': 'Invalid speech section.', 'errors': {
                'text': [{'message': 'Please reload the page and try again.'}]}}, status=422)
        delivery = request.POST.get('segment_emotion', form.cleaned_data['emotion'])
        if segment is not None and (delivery not in EMOTION_STYLES or delivery == 'auto'):
            return JsonResponse({'ok': False, 'message': 'Please reload the page to analyze your story first.'}, status=422)
        # Long scripts run as independent browser-coordinated requests. Sections
        # never become separate history entries; the browser saves the merged WAV.
        if segment is not None:
            item = SpeechGeneration(**form.cleaned_data, created_at=timezone.now())
        else:
            item = SpeechGeneration.objects.create(**form.cleaned_data)
        output = Path(settings.MEDIA_ROOT) / 'audio' / item.created_at.strftime('%Y/%m') / f'{item.public_id}.{item.format}'
        try:
            item.duration_seconds = synthesize(segment if segment is not None else item.text, item.voice, item.language, item.speed, output, item.format, emotion=delivery)
            item.audio_file.name = str(output.relative_to(settings.MEDIA_ROOT)).replace('\\', '/')
            item.status = 'completed'
            if segment is None:
                item.save(update_fields=['duration_seconds', 'audio_file', 'status'])
            if not wants_json:
                messages.success(request, 'Your audio is ready to play and download.')
        except Exception as exc:
            item.status = 'failed'
            item.error_message = str(exc)[:500]
            if segment is None:
                item.save(update_fields=['status', 'error_message'])
            if not wants_json:
                messages.error(request, item.error_message)
        if wants_json:
            status_code = 201 if item.status == 'completed' else 503
            payload = {
                'ok': item.status == 'completed',
                'status': item.status,
                'emotion': delivery,
                'message': 'Your audio is ready.' if item.status == 'completed' else item.error_message,
                'card_html': render_to_string('studio/_audio_card.html', {'item': item}, request=request),
            }
            if (settings.ON_VERCEL or segment is not None) and item.status == 'completed':
                payload.update(id=str(item.public_id), filename=f'{item.display_title[:50]}.wav')
                def chunks():
                    try:
                        yield json.dumps(payload) + '\n'
                        # Deliver audio in this request: another instance cannot read /tmp.
                        with output.open('rb') as source:
                            while chunk := source.read(48 * 1024):
                                yield json.dumps({'audio': base64.b64encode(chunk).decode('ascii')}) + '\n'
                        yield '{"complete":true}\n'
                    finally:
                        if segment is not None:
                            output.unlink(missing_ok=True)
                response = StreamingHttpResponse(chunks(), status=201, content_type='application/x-ndjson')
                response['Cache-Control'] = 'no-store'
                return response
            return JsonResponse(payload, status=status_code)
        return redirect('studio:home')
    if request.method == 'POST' and wants_json:
        return JsonResponse({'ok': False, 'message': 'Please correct the highlighted fields.', 'errors': form.errors.get_json_data()}, status=422)
    history = SpeechGeneration.objects.all()[:6]
    return render(request, 'studio/home.html', {'form': form, 'history': history, 'site_url': settings.PUBLIC_SITE_URL, 'temporary_storage': settings.ON_VERCEL})


@require_GET
def download(request, public_id):
    item = get_object_or_404(SpeechGeneration, public_id=public_id, status='completed')
    if not item.audio_file or not Path(item.audio_file.path).is_file():
        raise Http404('Audio file not found')
    return FileResponse(open(item.audio_file.path, 'rb'), as_attachment=True, filename=f'{item.display_title[:50]}.{item.format}')


@require_GET
def stream(request, public_id):
    """Serve generated media in production, where Django's debug media route is disabled."""
    item = get_object_or_404(SpeechGeneration, public_id=public_id, status='completed')
    if not item.audio_file or not Path(item.audio_file.path).is_file():
        raise Http404('Audio file not found')
    response = FileResponse(open(item.audio_file.path, 'rb'), content_type='audio/wav')
    response['Content-Disposition'] = f'inline; filename="{item.public_id}.{item.format}"'
    response['Cache-Control'] = 'private, max-age=3600'
    return response


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
    return JsonResponse({'status': 'ok' if ready else 'degraded', 'service': 'Free Text to Speech', 'voice_count': len(SpeechForm().fields['voice'].choices)}, status=200 if ready else 503)


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


@require_POST
def story_plan(request):
    form = SpeechForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'message': 'Please correct the highlighted fields.',
                             'errors': form.errors.get_json_data()}, status=422)
    if form.cleaned_data['voice'] not in STORY_VOICES:
        return JsonResponse({'ok': False, 'message': 'Select a Bangla story voice.'}, status=422)
    from .story import plan_story
    from .services import TTSUnavailable
    try:
        plan = plan_story(form.cleaned_data['text'])
    except TTSUnavailable as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=503)
    return JsonResponse({'ok': True, 'plan': plan})
