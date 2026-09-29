"""Role aware DRF permission classes.

Rules:
- ADMIN has full access to everything.
- Viewers only need Django's ``view_*`` permission for the resource.
- Writers need ``add_*`` (create) or ``change_*`` (update) on the resource.
- An authenticated user with no role is rejected: access is never implicit.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.roles import GROUP_NAMES


def user_roles(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(user.groups.values_list('name', flat=True))


def has_role(user, role: str) -> bool:
    return role in user_roles(user)


def has_any_role(user, roles) -> bool:
    return bool(user_roles(user) & set(roles))


def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or has_role(user, GROUP_NAMES['ADMIN'])))


def has_model_permission(user, model, action: str) -> bool:
    """Return True when the user is allowed to run ``action`` on ``model``."""
    if is_admin(user):
        return True
    if action not in {'view', 'add', 'change', 'delete'}:
        return False
    codename = f'{action}_{model._meta.model_name}'
    return user.has_perm(f'{model._meta.app_label}.{codename}')


class IsAuthenticatedActiveUser(BasePermission):
    message = 'Debe iniciar sesión.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class CanAccessResource(BasePermission):
    """Generic permission driven by the HTTP method.

    ``view`` -> ``view_*``, ``POST`` -> ``add_*``, ``PUT``/``PATCH`` ->
    ``change_*``, ``DELETE`` -> ``delete_*``.

    Custom actions that do not follow that mapping declare an explicit codename
    in the view's ``action_permissions`` dict, e.g. registering a credit payment
    needs ``add_debtpayment`` even though the method is POST.
    """

    message = 'No tiene permisos para realizar esta acción.'

    def has_permission(self, request, view):
        if not IsAuthenticatedActiveUser().has_permission(request, view):
            return False

        if is_admin(request.user):
            return True

        explicit = (getattr(view, 'action_permissions', None) or {}).get(
            getattr(view, 'action', None)
        )
        if explicit:
            return request.user.has_perm(explicit)

        model = getattr(view, 'permission_model', None)
        if model is None:
            return True

        if request.method in SAFE_METHODS:
            action = 'view'
        elif request.method == 'POST':
            action = 'add'
        elif request.method in {'PUT', 'PATCH'}:
            action = 'change'
        elif request.method == 'DELETE':
            action = 'delete'
        else:
            return False

        return has_model_permission(request.user, model, action)


class CanManageRates(CanAccessResource):
    message = 'Sólo un administrador o gerente puede consultar o registrar tasas.'


class CanManageStoreConfig(CanAccessResource):
    message = 'Sólo un administrador o gerente puede modificar la configuración de la tienda.'
