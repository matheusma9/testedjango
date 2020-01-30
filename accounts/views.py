from django.shortcuts import render
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from rest_framework.response import Response

from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import ObtainJSONWebToken

from .serializers import ClienteSerializer
from .models import Cliente

from website.models import Carrinho

from utils.shortcuts import get_object_or_404
from utils.schemas import CustomSchema

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime
import uuid
from calendar import timegm
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils.decorators import method_decorator
from website.serializers import CarrinhoSerializer
from website.models import Carrinho


# Create your views here.

class UserLoginSerializer(TokenObtainPairSerializer):
    carrinho = CarrinhoSerializer()

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        try:
            token['cliente'] = user.cliente.pk
        except ObjectDoesNotExist:
            token['cliente'] = None
        token['is_staff'] = user.is_staff
        #del token['token_type']
        # ...
        return token

    def validate(self, attrs):
        carrinho = attrs.get('carrinho')
        data = super().validate(attrs)
        error = False
        messages = []
        try:
            cliente = self.user.cliente
        except ObjectDoesNotExist:
            cliente = None
            carrinho_pk = None
        if carrinho and cliente:
            try:
                error, messages = cliente.carrinho.associar_itens(
                    carrinho['itens_carrinho'])
            except ObjectDoesNotExist:
                cliente.carrinho = Carrinho.objects.create()
                error, messages = cliente.carrinho.associar_itens(
                    carrinho['itens_carrinho'])
            carrinho_pk = cliente.carrinho.pk
        refresh = self.get_token(self.user)
        # data['refresh'] = str(refresh)
        del data['refresh']

        data['token'] = str(refresh.access_token)

        del data['access']
        data['carrinho'] = {'id': carrinho_pk,
                            'error': error, 'messages': messages}
        return data


user_login_schema = openapi.Schema(title='UserLogin', type=openapi.TYPE_OBJECT, properties={
    'username': openapi.Schema(type=openapi.TYPE_STRING),
    'password': openapi.Schema(type=openapi.TYPE_STRING),
    'carrinho': openapi.Schema(title='Carrinho', type=openapi.TYPE_OBJECT, properties={
        'itens': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(title='ItemCarrinho', type=openapi.TYPE_OBJECT, properties={
            'produto': openapi.Schema(type=openapi.TYPE_INTEGER),
            'quantidade': openapi.Schema(type=openapi.TYPE_INTEGER)
        }))
    })
}, required=['username', 'password'])


@method_decorator(name='post', decorator=swagger_auto_schema(
    request_body=user_login_schema, responses={200:
                                               openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                                                   'token': openapi.Schema(type=openapi.TYPE_STRING),
                                                   'carrinho': openapi.Schema(type=openapi.TYPE_OBJECT, properties={
                                                       'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                       'error': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                                                       'messages': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING))
                                                   }),
                                               }
                                               )}
))
class AccTokenObtainView(TokenObtainPairView):
    serializer_class = UserLoginSerializer
