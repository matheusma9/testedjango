
# Rest Framework
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

# Django
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings

# Accounts
from .permissions import IsOwnerOrCreateOnly
from .tokens import account_activation_token
from .models import Cliente
from .serializers import ClienteSerializer

# Website
from website.models import Oferta, Endereco, Carrinho, Produto
from website.serializers import (EnderecoSerializer, AvaliacaoProdutoSerializer,
                                 VendaSerializer, ProdutoSerializer, CarrinhoSerializer)

# Utils
from utils.shortcuts import get_object_or_404
from utils.fields import get_fields
from utils.schemas import CustomSchema
from utils.viewsets import list_response, paginated_schema

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


class ClienteViewSet(viewsets.ModelViewSet):
    """

    Endpoint relacionado aos clientes.

    """
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.all()
    permission_classes = (IsOwnerOrCreateOnly, )

    @swagger_auto_schema(method='post', request_body=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'email': openapi.Schema(type=openapi.TYPE_STRING)}), responses={200: openapi.Schema(type=openapi.TYPE_STRING)})
    @action(methods=['post'], detail=False)
    def solicitar(self, request):
        """
        ---
        method_path:
         /clientes/solicitar/
        method_action:
         POST
        desc:
         Solicitar alteração de senha.
        input:
        - name: email
          desc: Email do usuário.
          type: str
          required: True
          location: form
        """
        to_email, *_ = get_fields(request.data, ['email'])
        user = get_object_or_404(User, email=to_email)
        mail_subject = 'Solicitação para alteração de senha.'
        message = render_to_string('website/pass_reset.html', {
            'user': user,
            'domain': settings.FRONT_END_HOST,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        email = EmailMessage(
            mail_subject, message, to=[to_email]
        )
        email.send()
        return Response({'message': 'A solicitação será enviada para o seu email.'})

    reset_body = openapi.Schema(type=openapi.TYPE_OBJECT,
                                properties={
                                    'uid': openapi.Schema(type=openapi.TYPE_STRING),
                                    'token': openapi.Schema(type=openapi.TYPE_STRING),
                                    'password': openapi.Schema(type=openapi.TYPE_STRING),
                                })

    @swagger_auto_schema(method='post', request_body=reset_body, responses={200: openapi.Schema(type=openapi.TYPE_STRING)})
    @action(methods=['post'], detail=False)
    def reset(self, request):
        uidb64, token, password = get_fields(
            request.data, ['uid', 'token', 'password'])
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = get_object_or_404(User, pk=uid)
        except(TypeError, ValueError, OverflowError):
            user = None
        if user is not None and account_activation_token.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({'message': 'Senha alterada com sucesso'})
        return Response({'message': 'Token ou uid inválido'}, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(method='post', request_body=reset_body, responses={200: ClienteSerializer})
    @action(methods=['post'], detail=False)
    def enderecos(self, request):
        try:
            if request.user.is_authenticated:
                cliente = Cliente.objects.get(user=request.user)
                endereco_pk = request.data.get('endereco', None)
                if endereco_pk:
                    endereco = Endereco.objects.get(pk=endereco_pk)
                    cliente.enderecos.add(endereco)
                    cliente.save()
                    serializer = self.serializer_class(cliente)
                    return Response(serializer.data)
                else:
                    data = {'detail': 'O campo endereço é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
            else:
                raise NotAuthenticated
        except models.ObjectDoesNotExist:
            raise Http404

    venda_schema = openapi.Schema(
        title='Venda',
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'cliente': openapi.Schema(type=openapi.TYPE_INTEGER),
            'valor_total': openapi.Schema(type=openapi.TYPE_NUMBER),
            'created_at': openapi.Schema(type=openapi.TYPE_STRING),
            'endereco_entrega': openapi.Schema(type=openapi.TYPE_INTEGER),
            'itens': openapi.Schema(type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_OBJECT,
                                                         properties={
                                                             'valor': openapi.Schema(type=openapi.TYPE_NUMBER),
                                                             'quantidade': openapi.Schema(type=openapi.TYPE_STRING),
                                                             'produto': openapi.Schema(type=openapi.TYPE_INTEGER)
                                                         }
                                                         )
                                    )
        }
    )
    @swagger_auto_schema(method='get', responses={200: paginated_schema(venda_schema)})
    @action(methods=['get'], detail=True)
    def vendas(self, request, pk):
        """
        Obter vendas relacionadas a um determinado cliente.
        """
        try:
            cliente = self.get_object()
            return list_response(self, VendaSerializer, cliente.vendas.all(), request)
        except models.ObjectDoesNotExist:
            raise Http404

    produto_schema = openapi.Schema(
        title='Produto',
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'descricao': openapi.Schema(type=openapi.TYPE_STRING),
            'valor': openapi.Schema(type=openapi.TYPE_NUMBER),
            'imagens': openapi.Schema(type=openapi.TYPE_ARRAY,
                                      items=openapi.Schema(type=openapi.TYPE_OBJECT,
                                                           properties={
                                                               'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                               'imagem': openapi.Schema(type=openapi.TYPE_STRING),
                                                               'produto': openapi.Schema(type=openapi.TYPE_INTEGER),
                                                               'capa': openapi.Schema(type=openapi.TYPE_BOOLEAN)
                                                           }
                                                           )
                                      ),
            'qtd_acessos': openapi.Schema(type=openapi.TYPE_INTEGER),
            'n_vendas': openapi.Schema(type=openapi.TYPE_INTEGER),
        }
    )
    @swagger_auto_schema(method='get', responses={200: paginated_schema(produto_schema)})
    @action(methods=['get'], detail=True)
    def produtos(self, request, pk):
        """
        Obter produtos recomendados para um usuário.
        """
        try:
            if not recommender_produtos.is_fitted:
                recommender_produtos.fit()
            produtosId = recommender_produtos.get_topk(int(pk))
            produtos = Produto.objects.filter(id__in=produtosId)
            return list_response(self, ProdutoSerializer, produtos, request)
        except models.ObjectDoesNotExist:
            raise Http404

    avaliacao_schema = openapi.Schema(
        title='AvaliacaoProduto', type=openapi.TYPE_OBJECT,
        properties={
            'cliente': openapi.Schema(type=openapi.TYPE_INTEGER),
            'produto': openapi.Schema(type=openapi.TYPE_INTEGER),
            'rating': openapi.Schema(type=openapi.TYPE_NUMBER),
            'comentario': openapi.Schema(type=openapi.TYPE_STRING)
        }
    )

    @swagger_auto_schema(method='get', responses={200: paginated_schema(avaliacao_schema)})
    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        cliente = self.get_object()
        return list_response(self, AvaliacaoProdutoSerializer, cliente.avaliacoes_produto.all(), request)
