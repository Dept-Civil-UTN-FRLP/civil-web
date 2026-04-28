import os
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.conf import settings


@login_required
def serve_private_media(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, 'private', path)
    if not os.path.exists(file_path):
        raise Http404

    response = HttpResponse()
    response['Content-Type'] = ''
    response['X-Accel-Redirect'] = f'/protected-media/private/{path}'
    return response
