from rest_framework import viewsets
from rest_framework import generics, mixins
from .models import *
from .serializers import *
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission, IsAdminUser
from website.recommender import recommender_produtos
from django.http import Http404
from rest_framework.filters import BaseFilterBackend
import coreapi
import coreschema
from rest_framework.schemas import AutoSchema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .filters import *
from .schema_view import CustomSchema
from django.db.models import F, Count
from rest_framework import status

tag_schema = AutoSchema(manual_fields=[coreapi.Field('tags', required=False,
                                                     location='query',
                                                     description='Categorias dos produtos(separadas por virgulas).',
                                                     schema=coreschema.String(),
                                                     )
                                       ])


def list_response(viewset, model_serializer, qs, request):
    page = viewset.paginate_queryset(qs)
    if page is not None:
        serializer = model_serializer(
            page, many=True, context={"request": request})
        return viewset.get_paginated_response(serializer.data)
    serializer = viewset.get_serializer(qs, many=True)
    return Response(serializer.data)


class IsOwnerdOrCreateOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_object_permission(self, request, view, obj):
        return request.method == 'POST' or obj.user == request.user


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
        cliente = Cliente.objects.get(pk=pk)
        serializer_data = VendaSerializer(cliente.vendas.all(), many=True).data
        return Response(serializer_data)


class ClienteViewSet(viewsets.ModelViewSet):
    """

    Endpoint relacionado aos clientes.

    """
    schema = CustomSchema()
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.all()
    permission_classes = (IsOwnerdOrCreateOnly, )

    @action(methods=['get'], detail=True)
    def vendas(self, request, pk):
        """
        Obter vendas relacionadas a um determinado cliente.
        """
        try:
            cliente = Cliente.objects.get(pk=pk)
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
            cliente = Cliente.objects.get(pk=pk)
            return list_response(self, AvaliacaoProdutoSerializer, cliente.avaliacoes_produto.all(), request)
        except models.ObjectDoesNotExist:
            raise Http404

    @action(methods=['post', 'get', 'patch', 'delete'], detail=False)
    def carrinho(self, request):
        """
        ---
        method_path:
         /clientes/carrinho/
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
        method_path:
         /clientes/carrinho/
        method_action:
         GET
        desc:
         Visualizar carrinho de cliente.
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
        ---
        method_path:
         /clientes/carrinho/
        method_action:
         DELETE
        desc:
         Remover produto do carrinho.
        input:
        - name: produto
          desc: Id do produto que vai ser removido.
          type: integer
          required: True
          location: form
        """
        try:
            if request.user.is_authenticated:
                cliente = self.get_queryset().get(user=request.user)
                error = False
                messages = []
                created = False
                if not cliente.carrinho:
                    created = True
                    cliente.carrinho = Carrinho.objects.create()
                    cliente.save()

                if request.method == 'POST':
                    produto = Produto.objects.get(pk=request.data['produto'])
                    quantidade = request.data['quantidade']
                    if created:
                        quantidade, error, messages = produto.validar_qtd(
                            quantidade, error, messages)
                        if quantidade:
                            cliente.carrinho.itens_carrinho.create(produto=produto, carrinho=cliente.carrinho,
                                                                   valor=produto.valor, quantidade=quantidade)
                            cliente.carrinho.save()

                    else:
                        item, c = cliente.carrinho.itens_carrinho.get_or_create(
                            produto=produto, carrinho=cliente.carrinho)
                        item.valor = produto.valor
                        item.quantidade, error, messages = produto.validar_qtd(
                            ((item.quantidade or 0) + quantidade), error, messages)
                        if item.quantidade:
                            item.save()
                        else:
                            item.delete()

                if request.method == 'PATCH':
                    produto = Produto.objects.get(pk=request.data['produto'])
                    quantidade = request.data['quantidade']
                    quantidade, error, messages = produto.validar_qtd(
                        quantidade, error, messages)
                    item = cliente.carrinho.itens_carrinho.get(produto=produto)
                    item.quantidade = quantidade
                    item.save()

                if request.method == 'DELETE':
                    produto = Produto.objects.get(pk=request.data['produto'])
                    item = cliente.carrinho.itens_carrinho.get(produto=produto)
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

    @action(methods=['post'], detail=False)
    def compra(self, request):
        """
        ---
        method_path:
         /clientes/compra/
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
        """
        try:
            carrinho = Carrinho.objects.get(cliente__user=request.user)
            itens = request.data.get('itens', [])
            for item in itens:
                carrinho.itens_carrinho.filter(
                    produto__pk=item['produto']).update(quantidade=item['quantidade'])
                carrinho.save()
            carrinho.atualizar_valor()
            venda = carrinho.to_venda()
            carrinho.itens_carrinho.all().delete()
            carrinho.atualizar_valor()
            serializer = VendaSerializer(venda)
            return Response(serializer.data)
        except models.ObjectDoesNotExist:
            raise Http404


class ProdutoViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):

    """


    Endpoint relacionado aos produtos.


    """
    schema = CustomSchema()
    serializer_class = ProdutoSerializer
    queryset = Produto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

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
        slugs = request.GET.get('tags', None)
        if slugs:
            slugs = slugs.split(',')
            categorias = Categoria.objects.filter(slug__in=slugs)
            categorias.update(qtd_acessos=F('qtd_acessos') + 1)
            queryset = queryset.filter(categorias__in=categorias).distinct()
        return list_response(self, self.get_serializer, queryset, request)


class VendaViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
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
        inicio = request.GET.get('inicio', None)
        fim = request.GET.get('fim', None)
        qs = self.get_queryset()
        if inicio is not None and fim is not None:
            qs = qs.filter(created_at__range=(inicio, fim))
        elif inicio is not None:
            qs = qs.filter(created_at__gte=inicio)
        elif fim is not None:
            qs = qs.filter(created_at__gte=fim)
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
    permission_classes = (IsAuthenticatedOrReadOnly,)
    pagination_class = None
    schema = CustomSchema()

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
        n = int(request.GET.get('quantidade', 5))
        qs = self.queryset.order_by('-qtd_acessos')[:n]
        serializer = self.serializer_class(qs, many=True)
        return Response(serializer.data)

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
        """
        n = int(request.GET.get('quantidade', 5))
        qs = ItemVenda.objects.all()
        qs_categorias = qs.annotate(nome=F('produto__categorias__nome'), slug=F('produto__categorias__slug')).values(
            'nome', 'slug').exclude(nome=None).order_by()
        top_categorias = qs_categorias.annotate(
            n_vendas=Count('pk')).order_by('-n_vendas')
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
        """
        n = int(request.GET.get('quantidade', 5))
        qs = ItemVenda.objects.select_related(
            'produto').prefetch_related('produto__categorias')
        expression = models.ExpressionWrapper(F('valor')*F('quantidade'), output_field=models.DecimalField(
            max_digits=10, decimal_places=2, default=Decimal('0.00')))
        qs_categorias = qs.annotate(nome=F('produto__categorias__nome'), slug=F('produto__categorias__slug'), valor_total=expression).values(
            'nome', 'slug').exclude(nome=None).order_by()

        top_categorias = qs_categorias.annotate(
            receita=Sum('valor_total')).order_by('-receita')
        return Response(top_categorias[:n])
