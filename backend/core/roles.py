"""Role definitions used to build Django permission groups.

Every permission check in the API resolves against one of these groups, so the
role catalogue lives in a single place.
"""

ROLE_ADMIN = 'ADMIN'
ROLE_MANAGER = 'GERENTE'
ROLE_WAREHOUSE = 'ALMACENERO'
ROLE_CASHIER = 'CAJERO'

ROLE_CHOICES = [
    (ROLE_ADMIN, 'Administrador'),
    (ROLE_MANAGER, 'Gerente'),
    (ROLE_WAREHOUSE, 'Almacenero'),
    (ROLE_CASHIER, 'Cajero'),
]

ALL_ROLES = [code for code, _ in ROLE_CHOICES]

# Group names, kept equal to the role code for readability in Django admin.
GROUP_NAMES = {role: role for role in ALL_ROLES}

# Role hierarchy: a role inherits the permissions of the roles listed after it.
# ADMIN implicitly has every permission, so it is not part of the chains.
ROLE_INHERITS = {
    ROLE_MANAGER: [ROLE_WAREHOUSE, ROLE_CASHIER],
    ROLE_WAREHOUSE: [ROLE_CASHIER],
    ROLE_CASHIER: [],
}

# Django codename prefixes per app, used to seed groups.
CATALOG_CODENAMES = [
    'view_product',
    'add_product',
    'change_product',
    'add_productimage',
    'change_productimage',
    'delete_productimage',
]
RATES_CODENAMES = [
    'view_exchangerate',
    'add_exchangerate',
]
INVENTORY_CODENAMES = [
    'view_stockmovement',
    'view_goodsentry',
    'add_goodsentry',
    'change_goodsentry',
    'view_exitnote',
    'add_exitnote',
    'change_exitnote',
]

CUSTOMERS_CODENAMES = [
    'view_customer',
    'add_customer',
    'change_customer',
]
SALES_CODENAMES = [
    'view_sale',
    'add_sale',
    'change_sale',
    'view_customerdebt',
    'view_debtpayment',
    'add_debtpayment',
    'change_debtpayment',
]
CORE_CODENAMES = [
    'view_storeconfig',
    'change_storeconfig',
]

ROLE_PERMISSION_CODENAMES = {
    ROLE_ADMIN: None,  # every permission
    ROLE_MANAGER: (
        CATALOG_CODENAMES
        + RATES_CODENAMES
        + INVENTORY_CODENAMES
        + CUSTOMERS_CODENAMES
        + SALES_CODENAMES
        + CORE_CODENAMES
    ),
    ROLE_WAREHOUSE: CATALOG_CODENAMES + INVENTORY_CODENAMES,
    ROLE_CASHIER: (
        ['view_product']
        + ['view_customer', 'add_customer', 'change_customer']
        + [
            'view_sale',
            'add_sale',
            'change_sale',
            'view_customerdebt',
            'view_debtpayment',
            'add_debtpayment',
            'change_debtpayment',
        ]
    ),
}
