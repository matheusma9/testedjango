# Rest Framework
from rest_framework import serializers

# Django
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

# Website
from website.serializers import EnderecoSerializer
from website.models import Endereco

# Accounts
from .models import Cliente

# Utils
from utils.serializers import UpdateNestedMixin

# Others
from drf_extra_fields.fields import Base64ImageField


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'is_staff']
        required_fields = ['email', 'username', 'password']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_password(self, value):
        validate_password(value)
        return value


class ClienteSerializer(UpdateNestedMixin, serializers.ModelSerializer):
    user = UserSerializer()
    enderecos = EnderecoSerializer(many=True)
    foto = Base64ImageField(allow_null=True, required=False)
    data_nascimento = serializers.DateField(format="%d/%m/%Y")

    class Meta:
        model = Cliente
        fields = ['user', 'foto', 'id', 'nome', 'sobrenome', 'cpf',
                  'rg', 'data_nascimento', 'sexo', 'enderecos', 'carrinho']
        read_only_fields = ['id']

    def create(self, validated_data):
        foto = validated_data.get('foto', None)
        try:
            del validated_data['foto']
        except KeyError:
            pass
        usuario_data = validated_data.pop('user')
        if not usuario_data['email']:
            raise serializers.ValidationError('O campo email é obrigatório')
        enderecos_data = validated_data.pop('enderecos')

        user = User.objects.create_user(**usuario_data)

        cliente = Cliente.objects.create(
            user=user, foto=foto, **validated_data)
        for endereco_data in enderecos_data:
            endereco, _ = Endereco.objects.get_or_create(**endereco_data)
            cliente.enderecos.add(endereco)
        cliente.save()
        return cliente
