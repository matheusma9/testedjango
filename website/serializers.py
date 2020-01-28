# Rest Framework
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework.fields import empty

# Django
from django.core.exceptions import ValidationError

# Website
from .models import *
from .recommender import recommender_produtos

# Others
from decimal import Decimal
from drf_extra_fields.fields import Base64ImageField
from slugify import slugify
from collections import OrderedDict


class ItemCarrinhoSerializer(serializers.ModelSerializer):

    class Meta:
        model = ItemCarrinho
        fields = ['id', 'valor', 'quantidade', 'produto']
        read_only_fields = ['id', 'valor']


class CarrinhoSerializer(serializers.ModelSerializer):
    itens = ItemCarrinhoSerializer(source="itens_carrinho", many=True)

    @property
    def data(self):
        if self.instance is not None:
            self.instance.atualizar_valor()
        return super().data

    class Meta:
        model = Carrinho
        fields = ['id', 'valor_total', 'itens']
        read_only_fields = ['id']


class EnderecoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Endereco
        fields = ['id', 'bairro', 'rua', 'numero_casa',
                  'complemento', 'cep', 'cidade', 'uf']
        read_only_fields = ['id']


class CategoriaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'qtd_acessos']
        read_only_fields = ['id', 'slug', 'qtd_acessos']

    def create(self, validated_data):
        nome = validated_data.pop('nome')
        slug = slugify(nome)
        categoria, c = Categoria.objects.get_or_create(
            nome=nome, slug=slug)
        return categoria

    def update(self, instance, validated_data):
        instance.nome = validated_data.get('nome', instance.nome)
        instance.slug = slugify(instance.nome)
        instance.save()
        return instance


class ImagemProdutoSerializer(serializers.ModelSerializer):
    imagem = Base64ImageField()

    class Meta:
        model = ImagemProduto
        fields = ['id', 'imagem', 'produto', 'capa']
        read_only_fields = ['id']

    def create(self, validated_data):
        imagem = validated_data.pop('imagem')
        produto = validated_data.pop('produto')
        capa = validated_data.pop('capa')
        imagem_produto = ImagemProduto.objects.create(
            imagem=imagem, produto=produto)
        if capa:
            produto.imagens.update(capa=False)
            imagem_produto.capa = True
            imagem_produto.save()
        return imagem_produto

    def update(self, instance, validated_data):
        instance.imagem = validated_data.get('imagem', instance.imagem)
        instance.produto = validated_data.get('produto', instance.produto)
        instance.capa = validated_data.get('capa', instance.capa)
        if instance.capa:
            produto.imagens.update(capa=False)
            instance.capa = True
        instance.save()
        return instance


class ProdutoSerializer(serializers.ModelSerializer):
    categorias = CategoriaSerializer(many=True)
    imagens = ImagemProdutoSerializer(
        many=True, required=False)

    class Meta:
        model = Produto
        fields = ['id', 'descricao', 'valor', 'imagens',
                  'qtd_estoque', 'categorias', 'qtd_limite', 'rating']
        read_only_fields = ['id', 'rating']

    def create(self, validated_data):
        categorias = validated_data.pop('categorias')
        imagens = validated_data.get('imagens', None)
        if imagens is None:
            del validated_data['imagens']
        produto = Produto.objects.create(logo=logo, **validated_data)
        if imagens:
            imagem_serializer = ImagemProdutoSerializer(
                data=imagens, many=True)
            imagem_serializer.save()

        serializer = CategoriaSerializer(data=categoria, many=True)
        serializer.is_valid(raise_exception=True)
        categorias = serializer.save()
        produto.categorias.add(*categorias)
        produto.save()
        return produto

    def update(self, instance, validated_data):
        self.instance.descricao = validated_data.get(
            'descricao', self.instance.descricao)
        self.instance.valor = validated_data.get('valor', self.instance.valor)

        self.instance.qtd_estoque = validated_data.get(
            'qtd_estoque', self.instance.qtd_estoque)
        self.instance.qtd_limite = validated_data.get(
            'qtd_limite', self.instance.qtd_limite)
        categorias = validated_data.get('categorias', None)
        imagens = validated_data.get('imagens', None)

        if categorias:
            self.instance.categorias.clear()
            for categoria in categorias:
                c, _ = Categoria.objects.get_or_create(**categoria)
                self.instance.categorias.add(c)

        if imagens:
            self.instance.imagens.delete()
            imgs = ImagemProdutoSerializer(data=imagens, many=True)
            self.instance.imagens.add(*imgs)
        self.instance.save()
        return instance


class ItemVendaSerializer(serializers.ModelSerializer):
    valor = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = ItemVenda
        fields = ['produto', 'valor', 'quantidade']


class VendaSerializer(serializers.ModelSerializer):
    itens = ItemVendaSerializer(many=True)
    valor_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)

    class Meta:
        model = Venda
        fields = ['id', 'cliente', 'valor_total',
                  'itens', 'created_at', 'endereco_entrega']
        read_only_fields = ['id', 'valor_total', 'cliente', 'created_at']

    def criar_itens_vendas(self, itens_vendas_data, venda):
        for item_venda_data in itens_vendas_data:
            item_venda = ItemVenda.objects.create(
                venda=venda, **item_venda_data)
            venda.valor_total += item_venda.valor * item_venda.quantidade
            produto = item_venda_data['produto']
            if produto.qtd_estoque >= item_venda.quantidade:
                produto.qtd_estoque -= item_venda.quantidade
                produto.save()
            else:
                raise serializers.ValidationError(
                    'O item ' + str(produto) + ' tem uma quantidade em estoque menor do que a desejada')
        venda.save()

    def create(self, validated_data):
        user = self.context['request'].user
        cliente = Cliente.objects.get(user=user)
        itens_vendas_data = validated_data['itens']
        del validated_data['itens']
        validated_data['valor_total'] = Decimal('0.0')
        venda = Venda.objects.create(cliente=cliente, **validated_data)
        self.criar_itens_vendas(itens_vendas_data, venda)
        return venda


class AvaliacaoProdutoSerializer(serializers.ModelSerializer):

    class Meta:
        model = AvaliacaoProduto
        fields = ['cliente', 'produto', 'rating', 'comentario']
        read_only_fields = ['cliente']

    def create(self, validated_data):
        user = self.context['request'].user
        cliente = Cliente.objects.get(user=user)
        produto = validated_data['produto']
        avaliacao, _ = AvaliacaoProduto.objects.get_or_create(
            cliente=cliente, produto=produto)
        avaliacao.rating = validated_data['rating']
        avaliacao.comentario = validated_data['comentario']
        avaliacao.save()
        recommender_produtos.fit()
        return avaliacao


class OfertaSerializer(serializers.ModelSerializer):
    foto = Base64ImageField(
        allow_null=True, required=False)
    validade = serializers.DateTimeField(format="%d/%m/%YT%H:%M")

    class Meta:
        model = Oferta
        fields = ['id', 'descricao', 'owner', 'foto', 'valor',
                  'produto', 'validade', 'is_banner']
        read_only_fields = ['id', 'owner']

    def create(self, validated_data):
        foto = validated_data.get('foto', None)
        try:
            del validated_data['foto']
        except KeyError:
            pass
        owner = self.context['request'].user

        oferta = Oferta.objects.create(
            foto=foto, owner=owner, **validated_data)
        return oferta
