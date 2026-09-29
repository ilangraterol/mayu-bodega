"""DRF exception handler.

Domain services raise ``django.core.exceptions.ValidationError``; DRF only maps
its own exception classes, so without this handler a business rule violation
would surface as a 500 instead of a 400.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DrfValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

INTEGRITY_MESSAGES = {
    'stock_movement_balance_gte_0': 'La operación dejaría el inventario en negativo.',
    'product_stock_gte_0': 'La operación dejaría el inventario en negativo.',
    'debt_balance_gte_0': 'El abono supera el saldo pendiente de la deuda.',
    'unique_rate_per_source_and_date': 'Ya existe una tasa registrada para esa fecha y origen.',
    'one_primary_image_per_product': 'El producto ya tiene una imagen principal.',
}


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = getattr(exc, 'message_dict', None) or {
            'detail': [message for message in exc.messages]
        }
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, IntegrityError):
        message = _integrity_message(exc)
        logger.warning('Integridad violada: %s', message)
        return Response({'detail': message}, status=status.HTTP_409_CONFLICT)

    if isinstance(exc, DrfValidationError):
        return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

    return drf_exception_handler(exc, context)


def _integrity_message(exc: IntegrityError) -> str:
    text = str(exc)
    for constraint, message in INTEGRITY_MESSAGES.items():
        if constraint in text:
            return message
    return 'La operación entra en conflicto con datos existentes.'
