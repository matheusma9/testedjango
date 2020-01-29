from django.shortcuts import render
from django.contrib.auth.models import User

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
# Create your views here.


def jwt_payload_handler(cliente):
    username = cliente.user.username

    payload = {
        'user_id': cliente.user.pk,
        'username': username,
        'cliente': cliente.pk,
        'is_staff': cliente.user.is_staff,
        'exp': datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA
    }
    if hasattr(cliente.user, 'email'):
        payload['email'] = cliente.user.email
    if isinstance(cliente.user.pk, uuid.UUID):
        payload['user_id'] = str(cliente.user.pk)

    payload['username'] = username

    # Include original issued at time for a brand new token,
    # to allow token refresh
    return payload


#jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER


class LoginView(ObtainJSONWebToken):

    schema = CustomSchema()

    login_request_schema = openapi.Schema(title='Login', type=openapi.TYPE_OBJECT, properties={
        'username': openapi.Schema(type=openapi.TYPE_STRING),
        'password': openapi.Schema(type=openapi.TYPE_STRING),
        'carrinho': openapi.Schema(type=openapi.TYPE_INTEGER),
    },
        required=['username', 'password'])
    login_response_schema = openapi.Schema(type=openapi.TYPE_OBJECT, properties={
        'token': openapi.Schema(type=openapi.TYPE_STRING),
        'error': openapi.Schema(type=openapi.TYPE_BOOLEAN),
        'carrinho': openapi.Schema(type=openapi.TYPE_INTEGER),
        'messages': openapi.Schema(type=openapi.TYPE_ARRAY,
                                   items=openapi.Schema(type=openapi.TYPE_STRING))
    })

    @swagger_auto_schema(request_body=login_request_schema, responses={200: login_response_schema})
    def post(self, request, *args, **kwargs):
        req = request.data  # try and find email in request
        password = req.get('password')
        username = req.get('username')
        if username is None and password is None:
            return Response({'success': False,
                             'message': 'Missing or incorrect credentials',
                             'data': req},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(username=username)
        except:
            return Response({'success': False,
                             'message': 'Usuário e/ou senha inválidos.',
                             'data': req},
                            status=status.HTTP_404_NOT_FOUND)

        if not user.check_password(password):
            return Response({'success': False,
                             'message': 'Usuário e/ou senha inválidos.',
                             'data': req},
                            status=status.HTTP_403_FORBIDDEN)

        cliente = Cliente.objects.get(user=user)
        print(cliente)
        payload = jwt_payload_handler(cliente)
        token = jwt_encode_handler(payload)

        carrinho_pk = request.data.get('carrinho', 0)
        carrinho = get_object_or_404(Carrinho,
                                     pk=carrinho_pk) if carrinho_pk else None
        error, messages = False, []
        if not cliente.carrinho:
            cliente.carrinho = carrinho or Carrinho.objects.create()
            cliente.save()
        else:
            if carrinho:
                error, messages = cliente.carrinho.associar(carrinho)

        if cliente.carrinho.itens_carrinho.count():
            cliente.carrinho.atualizar_valor()

        return Response({'token': token,
                         'error': error,
                         'messages': messages,
                         'carrinho': cliente.carrinho.pk},
                        status=status.HTTP_200_OK)
