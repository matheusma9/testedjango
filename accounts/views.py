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

# Create your views here.
jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER


class LoginView(ObtainJSONWebToken):
    schema = CustomSchema()

    def post(self, request, *args, **kwargs):
        """
        ---
        method_path:
         /login/
        method_action:
         POST
        desc:
         Logar no sistema.
        input:
        - name: username
          desc: Username do usuário.
          type: str
          required: True
          location: form
        - name: password
          desc: Senha do usuário.
          type: str
          required: True
          location: form
        - name: carrinho
          desc: Id do carrinho que o usuário estava usando antes de logar.
          type: integer
          required: False
          location: form
        """
        # by default attempts username / passsword combination
        response = super(LoginView, self).post(request, *args, **kwargs)
        # token = response.data['token']  # don't use this to prevent errors
        # below will return null, but not an error, if not found :)
        res = response.data
        token = res.get('token')

        # token ok, get user
        if token:
            user = jwt_decode_handler(token)  # aleady json - don't serialize
            cliente = Cliente.objects.get(user__username=user['username'])
        else:  # if none, try auth by email
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
                                 'message': 'User not found',
                                 'data': req},
                                status=status.HTTP_404_NOT_FOUND)

            if not user.check_password(password):
                return Response({'success': False,
                                 'message': 'Incorrect password',
                                 'data': req},
                                status=status.HTTP_403_FORBIDDEN)

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)
            cliente = Cliente.objects.get(user__username=user['username'])
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

        return Response({'success': True,
                         'message': 'Successfully logged in',
                         'token': token,
                         'cliente': cliente.pk,
                         'is_staff': cliente.user.is_staff,
                         'error': error,
                         'messages': messages,
                         'carrinho': cliente.carrinho.pk},
                        status=status.HTTP_200_OK)
