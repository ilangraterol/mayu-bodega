from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import CanManageRates
from rates.models import ExchangeRate
from rates.serializers import ExchangeRateSerializer, ManualExchangeRateSerializer
from rates.services import (
    BcvRateNotDue,
    BcvSyncError,
    bcv_sync_status,
    register_manual_rate,
    sync_bcv_rate,
)


class ExchangeRateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExchangeRate.objects.select_related('recorded_by').all()
    serializer_class = ExchangeRateSerializer
    permission_model = ExchangeRate
    permission_classes = [CanManageRates]
    filterset_fields = ['source', 'effective_date']
    ordering_fields = ['effective_date', 'rate', 'fetched_at']

    @action(detail=False, methods=['get'])
    def current(self, request):
        rate = ExchangeRate.get_current()
        if rate is None:
            return Response(
                {'detail': 'No hay tasa de cambio registrada todavía.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self.get_serializer(rate).data)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        force = request.query_params.get('force', '').strip().lower() in {'1', 'true', 'yes', 'on'}
        try:
            rate = sync_bcv_rate(force=force)
        except BcvRateNotDue as error:
            return Response(
                {'detail': str(error), 'skipped': True, **bcv_sync_status()},
                status=status.HTTP_409_CONFLICT,
            )
        except BcvSyncError as error:
            return Response({'detail': str(error)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(self.get_serializer(rate).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='sync-status')
    def sync_status(self, request):
        """Last BCV read and the countdown to the next allowed one."""
        return Response(bcv_sync_status())

    @action(detail=False, methods=['post'], url_path='manual')
    def manual(self, request):
        serializer = ManualExchangeRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rate = register_manual_rate(
                rate=serializer.validated_data['rate'],
                effective_date=serializer.validated_data['effective_date'],
                user=request.user,
                notes=serializer.validated_data.get('notes', ''),
            )
        except ValueError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(rate).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='today')
    def today(self, request):
        rate = ExchangeRate.objects.filter(effective_date=timezone.localdate()).first()
        if rate is None:
            return Response(
                {'detail': 'No hay tasa para la fecha de hoy.'}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(self.get_serializer(rate).data)
