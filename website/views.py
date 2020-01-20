from django.shortcuts import render
from django.contrib.auth.models import User

from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from rest_framework.response import Response

from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import ObtainJSONWebToken

from .serializers import ClienteSerializer
from .models import Cliente, Carrinho
from .shortcuts import get_object_or_404
from .schema_view import CustomSchema
# Create your views here.
jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER


class StaffView(APIView):
    """
    View to list all users in the system.

    * Requires token authentication.
    * Only admin users are able to access this view.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, format=None):
        """
        Return a list of all users.
        """
        messages = []
        error = False
        username = request.data.get('username', None)
        password = request.data.get('password', None)
        email = request.data.get('email', None)
        if username is None:
            error = True
            messages.append('O campo username é necessário')
        else:
            if User.objects.filter(username=username).exists():
                error = True
                messages.append('Já exite um usuário com esse nome')

        if password is None:
            error = True
            messages.append('O campo password é necessário')
        if email is None:
            error = True
            messages.append('O campo email é necessário')
        else:
            if User.objects.filter(email=email).exists():
                error = True
                messages.append('Já exite um usuário com esse email')

        if error:
            return Response({'messsages': messages}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=request.data['username'], password=request.data['password'], email=request.data['email'], is_staff=True)

        return Response({'messages': ['Usuário cadastrado com sucesso']})


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
        error, messages = True, []
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


class LoginStaffView(ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        # by default attempts username / passsword combination
        response = super(LoginStaffView, self).post(request, *args, **kwargs)
        # token = response.data['token']  # don't use this to prevent errors
        # below will return null, but not an error, if not found :)
        res = response.data
        token = res.get('token')

        # token ok, get user
        if token:
            # aleady json - don't serialize
            user_data = jwt_decode_handler(token)
            user = User.objects.get(
                username=user_data['username'], is_staff=True)
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
                user = User.objects.get(username=username, is_staff=True)
            except:
                return Response({'success': False,
                                 'message': 'Staff not found',
                                 'data': req},
                                status=status.HTTP_404_NOT_FOUND)

            if not user.check_password(password):
                return Response({'success': False,
                                 'message': 'Incorrect password',
                                 'data': req},
                                status=status.HTTP_403_FORBIDDEN)

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)

        return Response({'success': True,
                         'message': 'Successfully logged in',
                         'token': token,
                         'staff': user.pk},
                        status=status.HTTP_200_OK)
