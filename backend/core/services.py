"""Role and permission seeding.

Shared by the ``seed_roles`` management command and the test suite so both
resolve the same groups.
"""

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from core.roles import GROUP_NAMES, ROLE_CHOICES, ROLE_PERMISSION_CODENAMES

LOCAL_APPS = ['core', 'catalog', 'rates', 'inventory', 'customers', 'sales']


@transaction.atomic
def sync_role_groups(warn=None) -> dict[str, int]:
    """Create the role groups and assign their permissions. Idempotent."""
    result = {}
    for code, _label in ROLE_CHOICES:
        group, _ = Group.objects.get_or_create(name=GROUP_NAMES[code])
        codenames = ROLE_PERMISSION_CODENAMES[code]
        if codenames is None:
            permissions = Permission.objects.filter(
                content_type__app_label__in=LOCAL_APPS
            )
        else:
            permissions = Permission.objects.filter(
                content_type__app_label__in=LOCAL_APPS, codename__in=codenames
            )
            if warn is not None:
                missing = set(codenames) - set(permissions.values_list('codename', flat=True))
                if missing:
                    warn(sorted(missing))
        group.permissions.set(permissions)
        result[code] = permissions.count()
    return result
