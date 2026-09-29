"""Create the role groups and assign the default permissions."""

from django.core.management.base import BaseCommand

from core.roles import ROLE_CHOICES
from core.services import sync_role_groups


class Command(BaseCommand):
    help = 'Crea los grupos de roles y asigna sus permisos por defecto.'

    def handle(self, *args, **options):
        def warn(missing):
            self.stdout.write(self.style.WARNING(f'  codenames inexistentes ignorados: {missing}'))

        counts = sync_role_groups(warn=warn)
        for code, label in ROLE_CHOICES:
            self.stdout.write(
                self.style.SUCCESS(f'Rol {code} ({label}): {counts[code]} permisos asignados.')
            )
