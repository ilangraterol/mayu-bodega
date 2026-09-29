from django.db.models import Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import CanAccessResource
from customers.models import Customer
from customers.serializers import CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_model = Customer
    permission_classes = [CanAccessResource]
    filterset_fields = ['is_active']
    search_fields = ['name', 'document_id', 'phone']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('with_balance') == 'true':
            queryset = queryset.annotate(
                debt_total=Sum(
                    'debts__balance_usd',
                    filter=~Q(debts__status__in=['PAID', 'ANULLED']),
                )
            ).order_by('-debt_total')
        return queryset

    @action(detail=True, methods=['get'])
    def statement(self, request, pk=None):
        customer = self.get_object()
        debts = customer.debts.select_related('sale').prefetch_related('payments')
        payload = {
            'customer': CustomerSerializer(customer, context={'request': request}).data,
            'debts': [
                {
                    'id': debt.id,
                    'sale_code': debt.sale.code if debt.sale_id else None,
                    'sale_date': debt.sale.sale_date if debt.sale_id else None,
                    'original_amount_usd': f'{debt.original_amount_usd:.2f}',
                    'balance_usd': f'{debt.balance_usd:.2f}',
                    'status': debt.status,
                    'payments': [
                        {
                            'id': payment.id,
                            'amount': f'{payment.amount:.2f}',
                            'currency': payment.currency,
                            'amount_usd': f'{payment.amount_usd:.2f}',
                            'exchange_rate_applied': f'{payment.exchange_rate_applied:.4f}',
                            'method': payment.method,
                            'paid_at': payment.paid_at,
                        }
                        for payment in debt.payments.filter(is_voided=False).order_by('paid_at')
                    ],
                }
                for debt in debts
            ],
        }
        return Response(payload)
