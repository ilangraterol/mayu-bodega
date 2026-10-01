"""
URL configuration.

In development Vite serves the SPA on :5173 and proxies `/api` and `/media` here.
In production there is only this process, so it also answers the three things the
dev server used to:

- ``/`` and any non-API route -> the built React ``index.html`` (BrowserRouter
  needs the app shell for deep links such as ``/productos/42``)
- ``/assets/*`` -> the Vite build
- ``/media/*`` -> product photos, handled by WhiteNoise so it works with DEBUG off
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.static import serve

DIST_DIR = settings.BASE_DIR.parent / 'frontend' / 'dist'
ASSETS_DIR = DIST_DIR / 'assets'


@never_cache
def spa(request):
    """Serve the React shell. ``never_cache`` keeps browsers from pinning a
    stale ``index.html`` after a redeploy, which is the usual cause of a live
    site loading asset hashes that no longer exist."""
    index = DIST_DIR / 'index.html'
    if index.exists():
        return FileResponse(open(index, 'rb'), content_type='text/html')
    return JsonResponse({'error': 'Frontend sin compilar'}, status=503)


def assets(request, ruta):
    """Serve a hashed build file. The resolved path is compared against ASSETS_DIR
    so a crafted ``../../`` request cannot read arbitrary files."""
    base = ASSETS_DIR.resolve()
    archivo = (base / ruta).resolve()
    if base not in archivo.parents or not archivo.is_file():
        return HttpResponse(status=404)
    return FileResponse(open(archivo, 'rb'))


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('rates.urls')),
    path('api/', include('inventory.urls')),
    path('api/', include('customers.urls')),
    path('api/', include('sales.urls')),
    path('assets/<path:ruta>', assets, name='assets'),
    # `static()` below only adds routes when DEBUG is True, which would leave the
    # catalogue without photos in production. WhiteNoise cannot do this job: it
    # mounts `WHITENOISE_ROOT` at `/` with no prefix, so the files would answer at
    # `/products/...` instead of `/media/products/...`. An explicit route keeps
    # the stored paths valid. Good enough for the demo; a real store should move
    # media to object storage, since the free Render disk is ephemeral.
    # The group must be named `path`: that is the keyword `serve` expects.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    # `path('', ...)` only matches the empty remainder, so it would serve the root
    # and 404 on every deep link such as /ventas. A regex is what actually
    # catches them. It must stay last so every real route wins.
    re_path(r'^(?!api/|admin/|assets/|media/|static/).*$', spa, name='spa'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
