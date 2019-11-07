from rest_framework import viewsets
from rest_framework import generics, mixins
from .models import *
from .serializers import *
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, BasePermission
from website.recommender import recommender


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
    permission_classes = [IsOwnerdOrCreateOnly]

    @action(methods=['get'], detail=True)
    def vendas(self, request, pk):
        """
        Obter vendas relacionadas a um determinado cliente.
        """
        cliente = Cliente.objects.get(pk=pk)
        serializer_data = VendaSerializer(cliente.vendas.all(), many=True).data
        return Response(serializer_data)

    @action(methods=['get'], detail=True)
    def lojas(self, request, pk):
        """
        Obter lojas recomendadas para um usuário.
        """
        lojasId = recommender.get_topk_lojas(int(pk))
        lojas = [Loja.objects.get(id=lojaId) for lojaId in lojasId]
        serializer_data = LojaSerializer(
            lojas, many=True, context={"request": request}).data
        return Response(serializer_data)

    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        cliente = Cliente.objects.get(pk=pk)
        serializer_data = AvaliacaoSerializer(
            cliente.avaliacoes_cliente.all(), many=True, context={"request": request}).data
        return Response(serializer_data)


class LojaViewSet(viewsets.ModelViewSet):
    """
    Endpoint relacionado as lojas.
    """
    serializer_class = LojaSerializer
    queryset = Loja.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)

    @action(methods=['get'], detail=True)
    def produtos(self, request, pk):
        """
        Obter os produtos de uma loja
        """
        loja = Loja.objects.get(pk=pk)
        serializer_data = ProdutoSerializer(
            loja.produtos.all(), many=True, context={"request": request}).data
        return Response(serializer_data)

    @action(methods=['get'], detail=True)
    def avaliacoes(self, request, pk):
        loja = Loja.objects.get(pk=pk)
        serializer_data = AvaliacaoSerializer(
            loja.avaliacoes_loja.all(), many=True, context={"request": request}).data
        return Response(serializer_data)


class ProdutoViewSet(mixins.CreateModelMixin,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):

    """
    Endpoint relacionado aos produtos.
    """
    serializer_class = ProdutoSerializer
    queryset = Produto.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)


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


class AvaliacaoViewSet(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):

    serializer_class = AvaliacaoSerializer
    queryset = Avaliacao.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
