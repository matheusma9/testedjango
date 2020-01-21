# Rest Framework
from rest_framework import viewsets, generics, mixins, filters, status
from rest_framework.views import APIView
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated

# Django
from django.http import Http404
from django.db.models import F, Count
from django.utils import timezone
from django.db.models.functions import Coalesce
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend


# Website
from .recommender import recommender_produtos
from .permissions import IsStaffAndOwnerOrReadOnly, IsOwnerOrCreateOnly, IsStaff, CarrinhoPermission
from .models import *
from .serializers import *
from .filters import *
from .schema_view import CustomSchema
from .shortcuts import get_object_or_404
from .tokens import account_activation_token
from .fields import get_fields


def list_response(viewset, model_serializer, qs, request):
    page = viewset.paginate_queryset(qs)
    if page is not None:
        serializer = model_serializer(
            page, many=True, context={"request": request})
        return viewset.get_paginated_response(serializer.data)
    serializer = model_serializer(qs, many=True)
    return Response(serializer.data)


class EnderecoViewSet(viewsets.ModelViewSet):
    """

    Endpoint relacionado aos endereços.

    """
    serializer_class = EnderecoSerializer
    queryset = Endereco.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

    @action(methods=['get'], detail=True)
    def clientes(self, request, pk):
        """

        Obter os clientes que possuem um determinado endereço.

        """
        endereco = self.get_object()
        serializer = ClienteSerializer(endereco.clientes.all(), many=True)
        return Response(serializer.data)


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
                print(cliente)
                oferta = Oferta.objects.filter(validade__gte=timezone.now()).get(
                    pk=request.data['oferta'])
                print(oferta)
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


class ProdutoViewSet(mixins.CreateModelMixin,
                     mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):

    """

    Endpoint relacionado aos produtos.

    """
    schema = CustomSchema()
    serializer_class = ProdutoSerializer
    queryset = Produto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    search_fields = ['descricao']
    filter_backends = (filters.SearchFilter,)

    def list(self, request, *args, **kwargs):
        """
        ---
        desc:
         Listar produtos.
        input:
        - name: tags
          desc: Categorias dos produtos(separadas por virgulas).
          type: string
          required: false
          location: query
        """

        queryset = self.filter_queryset(self.get_queryset())
        slugs = request.query_params.get('tags', None)
        if slugs:
            slugs = slugs.split(',')
            categorias = Categoria.objects.filter(slug__in=slugs)
            categorias.update(qtd_acessos=F('qtd_acessos') + 1)
            queryset = queryset.filter(categorias__in=categorias).distinct()
        return list_response(self, self.get_serializer, queryset, request)

    def retrieve(self, request, *args, **kwargs):
        produto = self.get_object()
        produto.categorias.update(qtd_acessos=F('qtd_acessos') + 1)
        serializer = self.get_serializer(produto)
        return Response(serializer.data)

    @action(methods=['post', 'delete'], detail=True)
    def categorias(self, request, pk, *args, **kwargs):
        if request.user.is_staff:
            produto = Produto.objects.get(pk=pk)

            if request.method == "POST":
                try:
                    data = request.data['categorias']
                    for categoria in data:
                        slug = slugify(categoria)
                        c, _ = Categoria.objects.get_or_create(
                            nome=categoria, slug=slug)
                        produto.categorias.add(c)
                    produto.save()
                except KeyError:
                    data = {'detail': 'O campo categoria é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)

            if request.method == "DELETE":
                try:
                    data = request.data['categorias']
                    for categoria in data:
                        c = produto.categorias.get(slug=categoria)
                        produto.categorias.remove(c)
                    produto.save()
                except KeyError:
                    data = {'detail': 'O campo categoria é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.serializer_class(produto)
            return Response(serializer.data)
        else:
            raise PermissionDenied

    @action(methods=['post', 'delete'], detail=True)
    def imagens(self, request, pk, *args, **kwargs):
        if request.user.is_staff:
            produto = Produto.objects.get(pk=pk)

            if request.method == "POST":
                try:
                    data = request.data['imagens']

                    for imagem in data:
                        imagem['produto'] = produto.pk
                        print(imagem)

                    imgs_serializer = ImagemProdutoSerializer(
                        data=data, many=True)
                    imgs_serializer.is_valid(raise_exception=True)
                    imgs_serializer.save()
                except KeyError:
                    data = {'detail': 'O campo imagens é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)

            if request.method == "DELETE":
                try:
                    data = request.data['imagens']
                    qs = ImagemProduto.objects.filter(pk__in=data)
                    if not qs.filter(capa=True).exists():
                        qs.remove()
                        nova_capa = ImagemProduto.objects.first()
                        nova_capa.capa = True
                        nova_capa.save()
                    else:
                        qs.remove()
                except KeyError:
                    data = {'detail': 'O campo imagens é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.serializer_class(produto)
            return Response(serializer.data)
        else:
            raise PermissionDenied


class VendaViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):

    """
    Endpoint relacionado as vendas.
    """
    schema = CustomSchema()
    serializer_class = VendaSerializer
    queryset = Venda.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def list(self, request, *args, **kwargs):
        """
        ---
        desc:
         Listar vendas.
        input:
        - name: inicio
          desc: Data inicial.
          type: string
          required: false
          location: query
        - name: fim
          desc: Data fim.
          type: string
          required: false
          location: query
        """
        inicio = request.query_params.get('inicio', None)
        fim = request.query_params.get('fim', None)
        qs = self.get_queryset()
        if inicio is not None and fim is not None:
            qs = qs.filter(created_at__range=(inicio, fim))
        elif inicio is not None:
            qs = qs.filter(created_at__gte=inicio)
        elif fim is not None:
            qs = qs.filter(created_at__lte=fim)
        return list_response(self, self.get_serializer, qs, request)


class AvaliacaoProdutoViewSet(mixins.CreateModelMixin,
                              mixins.ListModelMixin,
                              mixins.RetrieveModelMixin,
                              viewsets.GenericViewSet):

    serializer_class = AvaliacaoProdutoSerializer
    queryset = AvaliacaoProduto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)


class CategoriaViewSet(viewsets.ModelViewSet):
    """
    Endpoint relacionado as categorias.
    """
    serializer_class = CategoriaSerializer
    queryset = Categoria.objects.all()
    permission_classes = (IsStaff,)
    schema = CustomSchema()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=False)
    def acessos(self, request, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/acessos/
        method_action:
         GET
        desc:
         Categorias mais acessadas.
        input:
        - name: quantidade
          desc: Número de categorias listadas.
          type: integer
          required: False
          location: query 

        """
        n = int(request.query_params.get('quantidade', 20))
        qs = self.queryset.order_by('-qtd_acessos')[:n]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=True)
    def produtos(self, request, pk, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/{id}/produtos/
        method_action:
         GET
        desc:
         Produtos da categoria.
        """
        search = request.query_params.get('search', None)
        categoria = self.get_object()
        categoria.qtd_acessos += 1
        categoria.save()
        if search:
            qs = categoria.produtos.filter(
                descricao__icontains=search)
        else:
            qs = categoria.produtos.all()
        serializer = ProdutoSerializer(qs, many=True)
        return list_response(self, ProdutoSerializer, qs, request)

    @action(methods=['get'], detail=True,  url_path='info', url_name='info')
    def info(self, request, pk, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/{id}/info/
        method_action:
         GET
        desc:
         Informação de uma categoria.
        """
        c = self.get_object()
        data = self.serializer_class(c).data
        data['receita'] = c.receita
        data['n_vendas'] = c.vendas
        return Response(data)

    @action(methods=['get'], detail=False)
    def compras(self, request, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/compras/
        method_action:
         GET
        desc:
         Categorias mais compradas.
        input:
        - name: quantidade
          desc: Número de categorias listadas.
          type: integer
          required: False
          location: query
        - name: page
          desc: Número da página.
          type: integer
          required: False
          location: query 
        - name: limit
          desc: Quantidade de itens por páginas.
          type: integer
          required: False
          location: query 
        """
        n = int(request.query_params.get('quantidade', 20))
        top_categorias = self.get_queryset().annotate(n_vendas=Count('produtos__itens_vendas')
                                                      ).values('nome', 'slug', 'qtd_acessos', 'n_vendas').order_by('-n_vendas')
        return Response(top_categorias[:n])

    @action(methods=['get'], detail=False)
    def receita(self, request, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/receita/
        method_action:
         GET
        desc:
         Categorias que geraram uma maior receita.
        input:
        - name: quantidade
          desc: Número de categorias listadas.
          type: integer
          required: False
          location: query
        - name: page
          desc: Número da página.
          type: integer
          required: False
          location: query 
        - name: limit
          desc: Quantidade de itens por páginas.
          type: integer
          required: False
          location: query 
        """

        n = int(request.query_params.get('quantidade', 20))
        expression = models.ExpressionWrapper(F('produtos__itens_vendas__valor')*F('produtos__itens_vendas__quantidade'), output_field=models.DecimalField(
            max_digits=10, decimal_places=2, default=Decimal('0.00')))
        top_categorias = Categoria.objects.annotate(receita_item=expression).values('slug').annotate(
            receita=Coalesce(Sum('receita_item'), 0)).values('nome', 'slug', 'qtd_acessos', 'receita')
        return Response(top_categorias.order_by('-receita')[:n])


class OfertaViewSet(viewsets.ModelViewSet):
    serializer_class = OfertaSerializer
    queryset = Oferta.objects.filter(validade__gte=timezone.now())
    permission_classes = (IsStaffAndOwnerOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('is_banner',)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        oferta = Oferta.objects.filter(
            produto__pk=request.data['produto']).delete()
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        oferta = self.get_object()
        oferta.produto.categorias.update(qtd_acessos=F('qtd_acessos') + 1)
        serializer = self.get_serializer(oferta)
        return Response(serializer.data)


class CarrinhoViewSet(mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """
    Endpoint relacionado aos carrinhos.
    """
    schema = CustomSchema()
    serializer_class = CarrinhoSerializer
    queryset = Carrinho.objects.all()
    permission_classes = [CarrinhoPermission]

    def adicionar_item(self, request, item, quantidade, pk=0):
        error, messages = False, []
        if request.user.is_authenticated:
            cliente = get_object_or_404(Cliente, user=request.user)
            if pk and cliente.carrinho.pk != pk:
                raise PermissionDenied(
                    'O cliente não tem permissão para alterar esse carrinho')
            carrinho = cliente.carrinho
        else:
            carrinho = Carrinho.objects.get(
                pk=pk) if pk else Carrinho.objects.create()
        produto = get_object_or_404(Produto, pk=item)
        carrinho, error, messages = carrinho.adicionar_item(
            produto, quantidade, error, messages)
        # carrinho.atualizar_valor()
        return carrinho, error, messages

    @action(methods=['post'], detail=False, url_path='itens')
    def first_itens(self, request):
        """
        ---
        method_path:
         /carrinhos/itens/
        method_action:
         POST
        desc:
         Adicionar produto no carrinho pela primeira vez.
        input:
        - name: produto
          desc: Id do produto que vai ser adicionado.
          type: integer
          required: True
          location: form
        - name: quantidade
          desc: Quantidade de itens que serão adicionados.
          type: integer
          required: True
          location: form
          elements:
            produto: integer
            quantidade: integer
        """
        carrinho, error, messages = self.adicionar_item(
            request, request.data['produto'], request.data['quantidade'])
        serializer = self.get_serializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    @action(methods=['post', 'patch'], detail=True)
    def itens(self, request, pk):
        """
        ---
        method_path:
         /carrinhos/{id}/itens/
        method_action:
         POST
        desc:
         Adicionar produto no carrinho.
        input:
        - name: produto
          desc: Id do produto que vai ser adicionado.
          type: integer
          required: True
          location: form
        - name: quantidade
          desc: Quantidade de itens que serão adicionados.
          type: integer
          required: True
          location: form
          elements:
            produto: integer
            quantidade: integer
        ---
        method_action:
         PATCH
        desc:
         Editar produto do carrinho.
        input:
        - name: produto
          desc: Id do produto que vai ser alterado.
          type: integer
          required: True
          location: form
        - name: quantidade
          desc: Nova quantidade de itens.
          type: integer
          required: True
          location: form
        """
        if request.method == 'POST':
            carrinho, error, messages = self.adicionar_item(
                request, request.data['produto'], request.data['quantidade'], int(pk))

        elif request.method == 'PATCH':
            error, messages = False, []
            carrinho = self.get_object()
            produto = Produto.objects.get(pk=request.data['produto'])
            quantidade = request.data['quantidade']
            quantidade, error, messages = produto.validar_qtd(
                quantidade, error, messages)
            item = get_object_or_404(
                ItemCarrinho, carrinho=carrinho, produto=produto)
            item.quantidade = quantidade
            item.save()
            # carrinho.atualizar_valor()

        serializer = self.get_serializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    @action(methods=['delete'], detail=True, url_path='itens/(?P<produto_id>[^/.]+)')
    def remover_item(self, request, pk, produto_id):
        """
        ---
        method_path:
         /carrinhos/{id}/itens/{produto_id}/
        method_action:
         DELETE
        desc:
         Remover produto do carrinho.
        input:
        - name: produto_id
          desc: Id do produto que vai ser removido.
          type: integer
          required: True
          location: path
        """
        carrinho = self.get_object()
        error = False
        messages = []
        created = False
        produto = get_object_or_404(Produto, pk=produto_id)
        item = get_object_or_404(
            ItemCarrinho, carrinho=carrinho, produto=produto)
        item.delete()
        # carrinho.atualizar_valor()
        serializer = CarrinhoSerializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    @action(methods=['post'], detail=True)
    def compra(self, request, pk):
        """
        ---
        method_path:
         /carrinhos/{id}/compra/
        method_action:
         POST
        desc:
         Comprar produtos do carrinho.
        input:
        - name: itens
          desc: Lista de itens(produto, quantidade) que serão comprados.
          type: array
          required: False
          location: form
        - name: endereco
          desc: Id do Endereco de entrega
          type: integer
          required: True
          location: form
        """
        if request.user.is_authenticated:
            messages = []
            error = []
            cliente = Cliente.objects.get(user=request.user)
            created = False
            endereco_pk, *_ = get_fields(request.data, ['endereco'])
            endereco = cliente.enderecos.get(pk=endereco_pk)
            if cliente.carrinho.itens_carrinho.count():
                # cliente.carrinho.atualizar_valor()
                venda = cliente.carrinho.to_venda()
                venda.endereco_entrega = endereco
                venda.save()
                cliente.carrinho.itens_carrinho.all().delete()
                cliente.carrinho.atualizar_valor()
                serializer = VendaSerializer(venda)
                data = serializer.data
                data['messages'] = messages
                data['error'] = error
                return Response(data)
            else:
                data = {'detail': 'O carrinho está vazio'}
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
        else:
            raise NotAuthenticated
