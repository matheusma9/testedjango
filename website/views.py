from django.shortcuts import render
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import ObtainJSONWebToken
from .serializers import ClienteSerializer
from .models import Cliente
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User

# Create your views here.
jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER


class LoginView(ObtainJSONWebToken):
    def post(self, request, *args, **kwargs):
        # by default attempts username / passsword combination
        response = super(LoginView, self).post(request, *args, **kwargs)
        # token = response.data['token']  # don't use this to prevent errors
        # below will return null, but not an error, if not found :)
        res = response.data
        token = res.get('token')

        # token ok, get user
        if token:
            user = jwt_decode_handler(token)  # aleady json - don't serialize
            cliente = Cliente.objects.get(user__username=user['username']).pk
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
            cliente = Cliente.objects.get(user__username=user['username']).pk
            
        return Response({'success': True,
                        'message': 'Successfully logged in',
                        'token': token,
                        'cliente': cliente}, 
                        status=status.HTTP_200_OK)