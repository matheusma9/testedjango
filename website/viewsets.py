from rest_framework import viewsets
from rest_framework import generics, mixins
from .models import *
from .serializers import *
from rest_framework.exceptions import NotAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission, IsAdminUser
from website.recommender import recommender
from django.http import Http404
from rest_framework.filters import BaseFilterBackend
import coreapi
import coreschema
from rest_framework.schemas import AutoSchema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .filters import *
from .schema_view import CustomSchema
from django.db.models import F
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
    def lojas(self, request, pk):
        """
        Obter lojas recomendadas para um usuário.
        """
        try:
            if not recommender.is_fitted:
                recommender.fit()
            lojasId = recommender.get_topk_lojas(int(pk))
            lojas = [Loja.objects.get(id=lojaId) for lojaId in lojasId]
            return list_response(self, LojaSerializer, lojas, request)
        except models.ObjectDoesNotExist:
            raise Http404

    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        try:
            cliente = Cliente.objects.get(pk=pk)
            serializer_data = AvaliacaoSerializer(
                cliente.avaliacoes_cliente.all(), many=True, context={"request": request}).data
            return Response(serializer_data)
        except models.ObjectDoesNotExist:
            raise Http404


class LojaViewSet(viewsets.ModelViewSet):
    """
    Endpoint relacionado as lojas.
    """
    serializer_class = LojaSerializer
    queryset = Loja.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = [DjangoFilterBackend,
                       filters.SearchFilter]
    search_fields = ['nome_fantasia']

    @action(methods=['get'], detail=True, schema=tag_schema)
    def produtos(self, request, pk):
        """
        Produtos de uma loja
        """
        try:
            loja = self.get_queryset().get(pk=pk)
            slugs = request.GET.get('tags', None)
            if slugs:
                slugs = slugs.split(',')
                categorias = loja.categorias.filter(slug__in=slugs)
                categorias.update(qtd_acessos=F('qtd_acessos') + 1)
                qs = loja.produtos.filter(categorias__in=categorias).distinct()
            else:
                qs = loja.produtos.all()
            return list_response(self, ProdutoSerializer, qs, request)
        except models.ObjectDoesNotExist:
            raise Http404

    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        """
        Obter as avaliações de uma loja.
        """
        try:
            loja = self.get_queryset().get(pk=pk)
        except models.ObjectDoesNotExist:
            raise Http404
        qs = loja.avaliacoes_loja.all()
        return list_response(self, AvaliacaoSerializer, qs, request)

    @action(methods=['get'], detail=True)
    def categorias(self, request, pk):
        """
        Obter as categorias de uma loja.
        """
        try:
            loja = self.get_queryset().get(pk=pk)
        except models.ObjectDoesNotExist:
            raise Http404
        qs = loja.categorias.all()
        return Response(CategoriaSerializer(
            qs, many=True, context={"request": request}).data)

    @action(methods=['post', 'get', 'patch', 'delete'], detail=True)
    def carrinho(self, request, pk):
        if request.method == 'GET':
            if request.user.is_authenticated:
                try:
                    loja = self.get_queryset().get(pk=pk)
                    cliente = Cliente.objects.get(user=request.user)
                    carrinho, _ = loja.carrinhos.get_or_create(
                        loja=loja, cliente=cliente)
                    serializer = CarrinhoSerializer(carrinho)
                    return Response(serializer.data)
                except models.ObjectDoesNotExist:
                    raise Http404
            else:
                raise NotAuthenticated()
        if request.method == 'POST':
            try:
                loja = self.get_queryset().get(pk=pk)
                cliente = Cliente.objects.get(user=request.user)
                carrinho, created = Carrinho.objects.get_or_create(
                    loja=loja, cliente=cliente)
                produto = Produto.objects.get(pk=request.data['produto'])
                quantidade = request.data['quantidade']
                if created:
                    item = ItensCarrinho(produto=produto, carrinho=carrinho,
                                         valor=produto.valor, quantidade=quantidade)
                    item.save()
                    carrinho.itens_carrinho.add(item)
                    carrinho.save()
                else:
                    item, c = carrinho.itens_carrinho.get_or_create(
                        produto=produto, carrinho=carrinho)
                    item.valor = produto.valor
                    if c:
                        item.quantidade = quantidade
                    else:
                        item.quantidade += quantidade
                    item.save()
                carrinho.atualizar_valor()
                serializer = CarrinhoSerializer(carrinho)
                return Response(serializer.data)
            except models.ObjectDoesNotExist:
                raise Http404
        if request.method == 'PATCH':
            try:
                itens = request.data['itens']
                loja = self.get_queryset().get(pk=pk)
                carrinho = loja.carrinhos.get(cliente__user=request.user)

                for item in itens:
                    carrinho.itens_carrinho.filter(
                        produto__pk=item['produto']).update(quantidade=item['quantidade'])
                    carrinho.save()
                carrinho.atualizar_valor()
                serializer = CarrinhoSerializer(carrinho)
                return Response(serializer.data)
            except models.ObjectDoesNotExist:
                raise Http404
        if request.method == 'DELETE':
            try:
                loja = self.get_queryset().get(pk=pk)
                carrinho = loja.carrinhos.get(cliente__user=request.user)
                carrinho.itens_carrinho.filter(
                    produto__pk=request.data['produto']).delete()
                carrinho.save()
                carrinho.atualizar_valor()
                serializer = CarrinhoSerializer(carrinho)
                return Response(serializer.data)
            except models.ObjectDoesNotExist:
                raise Http404

    @action(methods=['post'], detail=True)
    def compra(self, request, pk):
        try:
            loja = self.get_queryset().get(pk=pk)
            carrinho = loja.carrinhos.get(cliente__user=request.user)
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
    serializer_class = VendaSerializer
    queryset = Venda.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)


class AvaliacaoLojaViewSet(mixins.CreateModelMixin,
                           mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):

    serializer_class = AvaliacaoLojaSerializer
    queryset = AvaliacaoLoja.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)


class AvaliacaoProdutoViewSet(mixins.CreateModelMixin,
                              mixins.ListModelMixin,
                              mixins.RetrieveModelMixin,
                              viewsets.GenericViewSet):

    serializer_class = AvaliacaoProdutoSerializer
    queryset = AvaliacaoProduto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)


class CategoriaViewSet(viewsets.ModelViewSet):
    serializer_class = CategoriaSerializer
    queryset = Categoria.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    pagination_class = None

    @action(methods=['get'], detail=False)
    def top(self, request, *args, **kwargs):
        qs = self.queryset.order_by('-qtd_acessos')[:5]
        serializer = self.serializer_class(qs, many=True)
        return Response(serializer.data)
