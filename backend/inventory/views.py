from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import CanAccessResource
from inventory import services
from inventory.models import ExitNote, ExitNoteReason, GoodsEntry, StockMovement
from inventory.serializers import (
    CancelDocumentSerializer,
    ExitNoteCreateSerializer,
    ExitNoteSerializer,
    GoodsEntryCreateSerializer,
    GoodsEntrySerializer,
    StockMovementSerializer,
)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related('product', 'created_by')
    serializer_class = StockMovementSerializer
    permission_model = StockMovement
    permission_classes = [CanAccessResource]
    filterset_fields = ['product', 'movement_type', 'origin', 'origin_id']
    search_fields = ['product__name', 'product__code', 'notes']
    ordering_fields = ['occurred_at', 'quantity', 'balance_after']

    def get_queryset(self):
        queryset = super().get_queryset()
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset


class GoodsEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GoodsEntry.objects.select_related('created_by').prefetch_related('items__product')
    serializer_class = GoodsEntrySerializer
    permission_model = GoodsEntry
    permission_classes = [CanAccessResource]
    action_permissions = {'cancel': 'inventory.change_goodsentry'}
    filterset_fields = ['is_cancelled', 'currency', 'entry_date']
    search_fields = ['code', 'supplier_name', 'notes']
    ordering_fields = ['entry_date', 'created_at', 'total_usd']

    def create(self, request):
        serializer = GoodsEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.register_entry(user=request.user, **serializer.validated_data)
        return Response(
            GoodsEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        entry = self.get_object()
        serializer = CancelDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_entry(user=request.user, entry=entry, reason=serializer.validated_data['reason'])
        entry.refresh_from_db()
        return Response(self.get_serializer(entry).data)


class ExitNoteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExitNote.objects.select_related('created_by').prefetch_related('items__product')
    serializer_class = ExitNoteSerializer
    permission_model = ExitNote
    permission_classes = [CanAccessResource]
    action_permissions = {'cancel': 'inventory.change_exitnote'}
    filterset_fields = ['is_cancelled', 'reason', 'exit_date']
    search_fields = ['code', 'description']
    ordering_fields = ['exit_date', 'created_at']

    def create(self, request):
        serializer = ExitNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = services.register_exit_note(user=request.user, **serializer.validated_data)
        return Response(self.get_serializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='reasons')
    def reasons(self, request):
        return Response([{'value': value, 'label': label} for value, label in ExitNoteReason.choices])

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        note = self.get_object()
        serializer = CancelDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_exit_note(user=request.user, note=note, reason=serializer.validated_data['reason'])
        note.refresh_from_db()
        return Response(self.get_serializer(note).data)
