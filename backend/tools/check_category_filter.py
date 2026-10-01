"""Read-only check: does GET /api/products/?category=<id> really filter?

Uses the Django test client with an admin so no credentials are needed and the
real database is read. Prints the category names and how many products each one
returns, plus the total without a filter.
"""

import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from catalog.models import Category  # noqa: E402

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
# The test client defaults to host `testserver`, which DEBUG=False rejects.
client = APIClient(HTTP_HOST='localhost')
client.force_authenticate(user=admin)

base = client.get('/api/products/', {'page_size': 1}).json()
print(f'sin filtro: count={base["count"]}')
print()

for category in Category.objects.all().order_by('name'):
    data = client.get('/api/products/', {'category': category.id, 'page_size': 100}).json()
    names = sorted(p['name'] for p in data['results'])
    print(f'{category.name} (id={category.id}): count={data["count"]}')
    for name in names:
        print(f'    - {name}')

print()
uncategorised = client.get('/api/products/', {'page_size': 200}).json()
total_named = sum(
    client.get('/api/products/', {'category': c.id, 'page_size': 1}).json()['count']
    for c in Category.objects.all()
)
print(f'suma por categoria={total_named} vs total={uncategorised["count"]}')
print(f'productos sin categoria={uncategorised["count"] - total_named}')

bad = client.get('/api/products/', {'category': 999999, 'page_size': 1}).status_code
print(f'categoria inexistente -> HTTP {bad}')
