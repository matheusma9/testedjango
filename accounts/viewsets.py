
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


class ClienteViewSet(viewsets.ModelViewSet):
    """

    Endpoint relacionado aos clientes.

    """
    schema = CustomSchema()
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.all()
    permission_classes = (IsOwnerOrCreateOnly, )

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

    @action(methods=['post'], detail=False)
    def reset(self, request):
        """
        ---
        method_path:
         /clientes/reset/
        method_action:
         POST
        desc:
         Alterar senha.
        input:
        - name: uid
          desc: Uid do usuário.
          type: str
          required: True
          location: form
        - name: token
          desc: token do usuário.
          type: str
          required: True
          location: form
        - name: password
          desc: Nova senha do usuário.
          type: str
          required: True
          location: form
        """
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

    @action(methods=['get', 'post'], detail=False)
    def enderecos(self, request):
        try:
            if request.user.is_authenticated:
                cliente = Cliente.objects.get(user=request.user)
                if request.method == "GET":
                    enderecos = cliente.enderecos.all()
                    return list_response(self, EnderecoSerializer, enderecos, request)
                if request.method == "POST":
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

    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        try:
            cliente = self.get_object()
            return list_response(self, AvaliacaoProdutoSerializer, cliente.avaliacoes_produto.all(), request)
        except models.ObjectDoesNotExist:
            raise Http404

    @action(methods=['post'], detail=False)
    def oferta(self, request):
        """
        ---
        method_path:
         /clientes/oferta/
        method_action:
         POST
        desc:
         Adicionar oferta de produto no carrinho.
        input:
        - name: oferta
          desc: Id da oferta.
          type: integer
          required: True
          location: form
        - name: quantidade
          desc: Quantidade de itens que serão adicionados.
          type: integer
          required: True
          location: form
        """
        try:
            if request.user.is_authenticated:
                error = False
                messages = []
                cliente = self.get_queryset().get(user=request.user)
                oferta = Oferta.objects.filter(validade__gte=timezone.now()).get(
                    pk=request.data['oferta'])
                created = False
                if not cliente.carrinho:
                    created = True
                    cliente.carrinho = Carrinho.objects.create()
                    cliente.save()
                produto = oferta.produto
                quantidade = request.data['quantidade']
                if created:
                    quantidade, error, messages = produto.validar_qtd(
                        quantidade, error, messages)
                    if quantidade:
                        cliente.carrinho.itens_carrinho.create(produto=produto, carrinho=cliente.carrinho,
                                                               valor=oferta.valor, quantidade=quantidade)
                        cliente.carrinho.save()
                else:
                    item, c = cliente.carrinho.itens_carrinho.get_or_create(
                        produto=produto, carrinho=cliente.carrinho)
                    item.quantidade, error, messages = produto.validar_qtd(
                        ((item.quantidade or 0) + quantidade), error, messages)
                    if item.quantidade:
                        item.save()
                    else:
                        item.delete()
                cliente.carrinho.atualizar_valor()
                serializer = CarrinhoSerializer(cliente.carrinho)
                data = serializer.data
                data['messages'] = messages
                data['error'] = error
                return Response(data)
            else:
                raise NotAuthenticated()
        except models.ObjectDoesNotExist:
            raise Http404
