# Rest Framework
from rest_framework import viewsets, mixins, filters, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly

# Django
from django.db.models import F, Count
from django.utils import timezone
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend


# Website
from .recommender import recommender_produtos
from .permissions import IsStaffAndOwnerOrReadOnly, IsStaff, CarrinhoPermission
from .models import *
from .serializers import *

# Accounts
from accounts.models import Cliente
from accounts.serializers import ClienteSerializer

# Utils
from utils.shortcuts import get_object_or_404
from utils.fields import get_fields
from utils.schemas import CustomSchema, Schema
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.decorators import method_decorator


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


class ProdutoViewSet(mixins.CreateModelMixin,
                     mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):

    """

    Endpoint relacionado aos produtos.

    """
    serializer_class = ProdutoSerializer
    queryset = Produto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    search_fields = ['descricao']
    filter_backends = (filters.SearchFilter,)

    # @swagger_auto_schema(operation_description="")
    tags = openapi.Parameter(name='tags',
                             in_=openapi.IN_QUERY,
                             type=openapi.TYPE_STRING,
                             description='Categorias dos produtos(separadas por virgulas)')

    @swagger_auto_schema(manual_parameters=[tags])
    def list(self, request, *args, **kwargs):
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
    serializer_class = VendaSerializer
    queryset = Venda.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

    data_inicial = openapi.Parameter(name='inicio',
                                     in_=openapi.IN_QUERY,
                                     type=openapi.TYPE_STRING,
                                     description='Data inicial')
    data_fim = openapi.Parameter(name='fim',
                                 in_=openapi.IN_QUERY,
                                 type=openapi.TYPE_STRING,
                                 description='Data fim')

    @swagger_auto_schema(manual_parameters=[data_inicial, data_fim])
    def list(self, request, *args, **kwargs):
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

    quantidade_parameter = openapi.Parameter(name='quantidade',
                                             in_=openapi.IN_QUERY,
                                             type=openapi.TYPE_INTEGER,
                                             description='Número de categorias listadas')

    @swagger_auto_schema(mathod='get', manual_parameters=[quantidade_parameter])
    @action(methods=['get'], detail=False)
    def acessos(self, request, *args, **kwargs):
        n = int(request.query_params.get('quantidade', 20))
        qs = self.queryset.order_by('-qtd_acessos')[:n]
        return list_response(self, self.get_serializer, qs, request)

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
        c = self.get_object()
        data = self.serializer_class(c).data
        data['receita'] = c.receita
        data['n_vendas'] = c.vendas
        return Response(data)

    @swagger_auto_schema(mathod='get', manual_parameters=[quantidade_parameter])
    @action(methods=['get'], detail=False)
    def compras(self, request, *args, **kwargs):
        n = int(request.query_params.get('quantidade', 20))
        top_categorias = self.get_queryset().annotate(n_vendas=Count('produtos__itens_vendas')
                                                      ).values('nome', 'slug', 'qtd_acessos', 'n_vendas').order_by('-n_vendas')
        return list_response(self, self.get_serializer, top_categorias[:n], request)

    @swagger_auto_schema(mathod='get', manual_parameters=[quantidade_parameter])
    @action(methods=['get'], detail=False)
    def receita(self, request, *args, **kwargs):
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
        return carrinho, error, messages

    @swagger_auto_schema(method='post', request_body=ItemCarrinhoSerializer)
    @action(methods=['post'], detail=False, url_path='itens')
    def first_itens(self, request):
        produto, quantidade = get_fields(
            request.data, ['produto', 'quantidade'])
        carrinho, error, messages = self.adicionar_item(
            request, request.data['produto'], request.data['quantidade'])
        serializer = self.get_serializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    response_carrinho = openapi.Schema(
        title='Carrinho',
        type=openapi.TYPE_OBJECT,
        properties={
            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
            'valor_total': openapi.Schema(type=openapi.TYPE_NUMBER),
            'itens': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(
                title='ItemCarrinho',
                type=openapi.TYPE_OBJECT,
                properties={
                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'valor': openapi.Schema(type=openapi.TYPE_NUMBER),
                    'quantidade': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'produto': openapi.Schema(type=openapi.TYPE_INTEGER),
                }
            )),
            'error': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'messages': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING))

        }
    )
    @swagger_auto_schema(methods=['post', 'patch'], request_body=ItemCarrinhoSerializer, responses={201: response_carrinho})
    @action(methods=['post', 'patch'], detail=True)
    def itens(self, request, pk):
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

        serializer = self.get_serializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    @action(methods=['delete'], detail=True, url_path='itens/(?P<produto_id>[^/.]+)')
    def remover_item(self, request, pk, produto_id):
        carrinho = self.get_object()
        error = False
        messages = []
        created = False
        produto = get_object_or_404(Produto, pk=produto_id)
        item = get_object_or_404(
            ItemCarrinho, carrinho=carrinho, produto=produto)
        item.delete()
        serializer = CarrinhoSerializer(carrinho)
        data = serializer.data
        data['messages'] = messages
        data['error'] = error
        return Response(data)

    compra_response = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'endereco': openapi.Schema(type=openapi.TYPE_INTEGER)
        })

    @swagger_auto_schema(method='post', request_body=compra_response, responses={200: VendaSerializer})
    @action(methods=['post'], detail=True)
    def compra(self, request, pk):
        if request.user.is_authenticated:
            messages = []
            error = []
            cliente = Cliente.objects.get(user=request.user)
            created = False
            endereco_pk, *_ = get_fields(request.data, ['endereco'])
            endereco = cliente.enderecos.get(pk=endereco_pk)
            if cliente.carrinho.itens_carrinho.count():
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
