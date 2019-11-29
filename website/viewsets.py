from rest_framework import viewsets
from rest_framework import generics, mixins
from rest_framework.views import APIView
from .models import *
from .serializers import *
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from website.recommender import recommender_produtos
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from website.permissions import IsStaffAndOwnerOrReadOnly, IsOwnerOrCreateOnly
from .filters import *
from .schema_view import CustomSchema
from django.db.models import F, Count
from rest_framework import status
from django.utils import timezone
from django.db.models.functions import Coalesce


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
    permission_classes = (IsOwnerOrCreateOnly, )

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
        - name: endereco
          desc: Id do Endereco de entrega
          type: int
          required: True
          location: form
        """
        try:
            if request.user.is_authenticated:
                cliente = Cliente.objects.get(user=request.user)
                carrinho = Carrinho.objects.get(cliente=cliente)
                endereco_pk = request.data.get('endereco', None)
                if endereco_pk:
                    endereco = cliente.enderecos.get(pk=endereco_pk)
                    itens = request.data.get('itens', [])
                    for item in itens:
                        carrinho.itens_carrinho.filter(
                            produto__pk=item['produto']).update(quantidade=item['quantidade'])
                        carrinho.save()
                    carrinho.atualizar_valor()
                    venda = carrinho.to_venda()
                    venda.endereco_entrega = endereco
                    venda.save()
                    carrinho.itens_carrinho.all().delete()
                    carrinho.atualizar_valor()
                    serializer = VendaSerializer(venda)
                    return Response(serializer.data)
                else:
                    data = {'detail': 'O campo endereço é obrigatório'}
                    return Response(data, status=status.HTTP_400_BAD_REQUEST)
            else:
                raise NotAuthenticated
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
                    item.valor = oferta.valor
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
        slugs = request.GET.get('tags', None)
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
        inicio = request.GET.get('inicio', None)
        fim = request.GET.get('fim', None)
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
    permission_classes = (IsAuthenticatedOrReadOnly,)
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
        n = int(request.GET.get('quantidade', 20))
        qs = self.queryset.order_by('-qtd_acessos')[:n]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(methods=['get'], detail=True)
    def produtos(self, request, pk, *args, **kwargs):
        """
        ---
        method_path:
         /categorias/id/produtos/
        method_action:
         GET
        desc:
         Categorias mais acessadas.
        input:
        - name: search
          desc: Número de categorias listadas.
          type: integer
          required: False
          location: query 

        """
        search = request.GET.get('search', None)
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

    @action(methods=['get'], detail=True)
    def info(self, request, pk):
        c = self.get_object()
        data = self.serializer_class(c).data
        expression = models.ExpressionWrapper(F('itens_vendas__valor')*F('itens_vendas__quantidade'), output_field=models.DecimalField(
            max_digits=10, decimal_places=2, default=Decimal('0.00')))
        res = c.produtos.annotate(n_vendas=Count('itens_vendas'), receita=expression).aggregate(
            Sum('receita'), Sum('n_vendas')
        )
        data['n_vendas'] = res['n_vendas__sum'] or 0
        data['receita'] = res['receita__sum'] or 0
        return Response(data)

    @action(methods=['get'], detail=True, url_path='compras', url_name='compras')
    def n_vendas(self, request, pk, *args, **kwargs):
        c = self.get_object()
        data = self.serializer_class(c).data
        n_vendas = c.produtos.annotate(n_vendas=Count('itens_vendas')).aggregate(
            Sum('n_vendas'))['n_vendas__sum']
        data['n_vendas'] = n_vendas or 0
        return Response(data)

    @action(methods=['get'], detail=True,  url_path='receita', url_name='receita')
    def categoria_receita(self, request, pk, *args, **kwargs):
        c = self.get_object()
        data = self.serializer_class(c).data
        expression = models.ExpressionWrapper(F('itens_vendas__valor')*F('itens_vendas__quantidade'), output_field=models.DecimalField(
            max_digits=10, decimal_places=2, default=Decimal('0.00')))
        receita = c.produtos.annotate(receita=expression).aggregate(
            Sum('receita'))['receita__sum']
        data['receita'] = receita or Decimal('0.0')
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
        n = int(request.GET.get('quantidade', 20))
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
        n = int(request.GET.get('quantidade', 20))
        expression = models.ExpressionWrapper(F('produtos__itens_vendas__valor')*F('produtos__itens_vendas__quantidade'), output_field=models.DecimalField(
            max_digits=10, decimal_places=2, default=Decimal('0.00')))
        top_categorias = qs = Categoria.objects.annotate(receita_item=expression).values('slug').annotate(
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
        Oferta.objects.filter(produto__pk=request.data['produto']).delete()
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        oferta = self.get_object()
        oferta.produto.categorias.update(qtd_acessos=F('qtd_acessos') + 1)
        serializer = self.get_serializer(oferta)
        return Response(serializer.data)
