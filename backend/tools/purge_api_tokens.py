"""Borra los tokens de API activos antes de publicar la base de datos.

``db.sqlite3`` se versiona a propósito para que la demo de Render arranque con
catálogo y fotos (ver ``.gitignore`` y ``DEPLOY.md``). El problema es que DRF
guarda los tokens en la propia tabla ``authtoken_token`` y **no dependen del
``SECRET_KEY``**: Render genera una clave nueva en cada despliegue, pero los
tokens que traveling en el repositorio seguirían dando acceso a la API pública
de cualquiera que lea el repo.

Borrarlos es seguro. DRF crea un token nuevo en el siguiente login, así que la
demo sigue entrando con ``admin`` / la contraseña que se haya definido.

Los hashes de contraseña también viajan dentro del snapshot, por eso la
herramienta avisa de la contraseña demo y sugiere cambiarla antes de usar el
servicio con datos reales.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    fail,
    heading,
    ok,
    require_apply,
    setup_django,
    warn,
)

DESCRIPTION = 'borrar los tokens de API almacenados en db.sqlite3'


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Ejecuta el borrado. Sin este flag solo se imprime el plan.',
    )
    args = parser.parse_args()

    setup_django()
    from rest_framework.authtoken.models import Token

    tokens = list(Token.objects.select_related('user').order_by('user__username'))

    heading('Plan: tokens que se borrarían')
    if not tokens:
        ok('No hay tokens almacenados. No hace falta hacer nada.')
        return
    for token in tokens:
        # Solo un prefijo: imprimir el token completo en consola lo filtraría.
        warn(f'{token.user.username}: {token.key[:8]}… creado {token.created:%Y-%m-%d}')

    require_apply(args.apply, DESCRIPTION)

    count = Token.objects.all().delete()[0]
    ok(f'{count} token(s) borrados. Se recrean en el próximo login.')


if __name__ == '__main__':
    main()
