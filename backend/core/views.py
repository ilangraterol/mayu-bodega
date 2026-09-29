from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.models import StoreConfig
from core.permissions import CanManageStoreConfig
from core.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    StoreConfigSerializer,
    UserSerializer,
    issue_token,
)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    payload = LoginResponseSerializer({'token': issue_token(user), 'user': user})
    return Response(payload.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)


class StoreConfigViewSet(viewsets.GenericViewSet):
    """Singleton configuration: read it and patch the current values."""

    permission_model = StoreConfig
    permission_classes = [CanManageStoreConfig]
    serializer_class = StoreConfigSerializer

    def list(self, request):
        config = StoreConfig.load()
        return Response(self.get_serializer(config).data)

    def partial_update(self, request, pk=None):
        config = StoreConfig.load()
        serializer = self.get_serializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = serializer.save(updated_by=request.user, updated_at=timezone.now())
        return Response(self.get_serializer(config).data)
