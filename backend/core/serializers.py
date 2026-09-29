from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from core.models import StoreConfig
from core.roles import ROLE_CHOICES


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'is_active', 'roles']

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username

    def get_roles(self, obj) -> list[str]:
        return list(obj.groups.values_list('name', flat=True))


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            username=attrs['username'],
            password=attrs['password'],
        )
        if user is None:
            raise serializers.ValidationError({'detail': 'Credenciales inválidas.'}, code='authorization')
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'El usuario está inactivo.'}, code='authorization')
        attrs['user'] = user
        return attrs


class LoginResponseSerializer(serializers.Serializer):
    token = serializers.CharField()
    user = UserSerializer()


class StoreConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreConfig
        fields = [
            'store_name',
            'allow_zero_stock_sale',
            'default_surcharge_percentage',
            'updated_at',
        ]
        read_only_fields = ['updated_at']


def issue_token(user: User) -> str:
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


ROLE_LABELS = dict(ROLE_CHOICES)
