"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

if os.environ.get('VERCEL') == '1':
    # Each serverless instance starts with an empty, writable scratch directory.
    # Never ship the development database or copy its history into production.
    import fcntl
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections

    settings.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with (settings.RUNTIME_DIR / 'database.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        call_command('migrate', interactive=False, verbosity=0)
        connections.close_all()
