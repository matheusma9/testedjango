from rest_framework import serializers
from .models import *
from decimal import Decimal
from django.contrib.auth.models import User
from drf_extra_fields.fields import Base64ImageField
from website.recommender import recommender
from taggit_serializer.serializers import (TagListSerializerField,
                                           TaggitSerializer)
from slugify import slugify


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email']
        required_fields = ['email', 'username', 'password']
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class EnderecoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = ['id', 'bairro', 'rua', 'numero_casa',
                  'complemento', 'cep', 'cidade', 'uf']
        read_only_fields = ['id']


class ClienteSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    endereco = EnderecoSerializer()
    foto = Base64ImageField(allow_null=True)
    data_nascimento = serializers.DateField(format="%d/%m/%Y")

    class Meta:
        model = Cliente
        fields = ['user', 'foto', 'id', 'nome', 'sobrenome', 'cpf',
                  'rg', 'data_nascimento', 'sexo', 'endereco']
        read_only_fields = ['id']
        extra_kwargs = {'foto': {'required': False,
                                 'allow_blank': True, 'allow_null': True}}

    def create(self, validated_data):
        foto = validated_data.pop('foto')
        usuario_data = validated_data.pop('user')
        if not usuario_data['email']:
            raise serializers.ValidationError('O campo email é obrigatório')
        endereco_data = validated_data.pop('endereco')
        user = User.objects.create_user(**usuario_data)
        endereco, _ = Endereco.objects.get_or_create(**endereco_data)
        cliente = Cliente.objects.create(
            user=user, endereco=endereco, foto=foto, **validated_data)
        return cliente

    def update_endereco(self, instance, endereco):
        if endereco:
            instance.endereco.bairro = endereco['bairro']
            instance.endereco.rua = endereco['rua']
            instance.endereco.numero_casa = endereco['numero_casa']
            instance.endereco.complemento = endereco['complemento']
            instance.endereco.cep = endereco['cep']
            instance.endereco.cidade = endereco['cidade']
            instance.endereco.uf = endereco['uf']
            instance.endereco.save()

    def update(self, instance, validated_data):
        instance.foto = validated_data.get('foto', instance.foto)
        user = validated_data.get('user', None)
        if user:
            instance.user.email = validated_data['user'].get(
                'email', instance.user.email)
            instance.user.set_password(validated_data['user'].get(
                'password', instance.user.password))
            instance.user.save()
        instance.nome = validated_data.get('nome', instance.nome)
        instance.sobrenome = validated_data.get(
            'sobrenome', instance.sobrenome)
        instance.cpf = validated_data.get('cpf', instance.cpf)
        instance.rg = validated_data.get('rg', instance.rg)
        instance.data_nascimento = validated_data.get(
            'data_nascimento', instance.data_nascimento)
        instance.sexo = validated_data.get('sexo', instance.sexo)
        self.update_endereco(instance, validated_data.get('endereco', None))
        instance.save()
        return instance


class CategoriaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Categoria
        fields = ['nome', 'slug']
        read_only_fields = ['slug']

    def create(self, validated_data):

        nome = validated_data.pop('nome')
        slug = slugify(nome)
        categoria = Categoria.objects.create(nome=nome, slug=slug)
        return categoria


class LojaSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(allow_null=True)
    categorias = CategoriaSerializer(many=True)

    class Meta:
        model = Loja
        fields = ['id', 'nome_fantasia', 'logo',
                  'cnpj', 'razao_social', 'categorias']
        read_only_fields = ['id']

    def create(self, validated_data):
        logo = validated_data.pop('logo')
        categorias = validated_data.pop('categorias')
        loja = Loja.objects.create(logo=logo, **validated_data)

        for categoria in categorias:
            c, _ = Categoria.objects.get_or_create(**categoria)
            loja.categorias.add(c)
        loja.save()
        return loja

    def update(self, instance, validated_data):
        self.instance.nome_fantasia = validated_data.get(
            'nome_fantasia', self.instance.nome_fantasia)
        self.instance.cnpj = validated_data.get('cnpj', self.instance.cnpj)
        self.instance.logo = validated_data.get('logo', self.instance.logo)
        self.instance.razao_social = validated_data.get(
            'razao_social', self.instance.razao_social)
        categorias = validated_data.get('categorias', None)
        if categorias:
            for categoria in categorias:
                c, _ = Categoria.objects.get_or_create(**categoria)
                self.instance.categorias.add(c)
        self.instance.save()
        return instance


class ProdutoSerializer(serializers.ModelSerializer):
    logo = Base64ImageField(allow_null=True)
    categorias = CategoriaSerializer(many=True)

    class Meta:
        model = Produto
        fields = ['id', 'descricao', 'valor',
                  'logo', 'loja', 'qtd_estoque', 'categorias']
        read_only_fields = ['id']
        extra_kwargs = {'logo': {'allow_blank': True}}

    def create(self, validated_data):
        logo = validated_data.pop('logo')
        categorias = validated_data.pop('categorias')
        produto = Produto.objects.create(logo=logo, **validated_data)

        for categoria in categorias:
            c, _ = Categoria.objects.get_or_create(**categoria)
            produto.categorias.add(c)
        produto.save()
        return produto

    def update(self, instance, validated_data):
        self.instance.descricao = validated_data.get(
            'descricao', self.instance.descricao)
        self.instance.valor = validated_data.get('valor', self.instance.valor)
        self.instance.logo = validated_data.get('logo', self.instance.logo)
        self.instance.loja = validated_data.get('loja', self.instance.loja)
        self.instance.qtd_estoque = validated_data.get(
            'qtd_estoque', self.instance.qtd_estoque)
        categorias = validated_data.get('categorias', None)
        if categorias:
            for categoria in categorias:
                c, _ = Categoria.objects.get_or_create(**categoria)
                self.instance.categorias.add(c)
        self.instance.save()
        return instance


class VendaProdutoSerializer(serializers.ModelSerializer):
    valor = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = VendaProduto
        fields = ['produto', 'valor', 'quantidade']


class VendaSerializer(serializers.ModelSerializer):
    vendas_produtos = VendaProdutoSerializer(
        source='vendas_produtos_venda', many=True)
    valor_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)

    class Meta:
        model = Venda
        fields = ['id', 'cliente', 'loja', 'valor_total', 'vendas_produtos']
        read_only_fields = ['id', 'valor_total', 'cliente']

    def criar_vendas_produtos(self, vendas_produtos_data, venda):
        for venda_produto_data in vendas_produtos_data:
            venda_produto = VendaProduto.objects.create(
                venda=venda, **venda_produto_data)
            venda.valor_total += venda_produto.valor * venda_produto.quantidade
            produto = venda_produto_data['produto']
            if produto.qtd_estoque >= venda_produto.quantidade:
                produto.qtd_estoque -= venda_produto.quantidade
                produto.save()
            else:
                raise serializers.ValidationError(
                    'O item ' + str(produto) + ' tem uma quantidade em estoque menor do que a desejada')

        venda.save()

    def create(self, validated_data):
        user = self.context['request'].user
        cliente = Cliente.objects.get(user=user)

        vendas_produtos_data = validated_data['vendas_produtos_venda']
        del validated_data['vendas_produtos_venda']
        validated_data['valor_total'] = Decimal('0.0')

        venda = Venda.objects.create(cliente=cliente, **validated_data)
        self.criar_vendas_produtos(vendas_produtos_data, venda)
        return venda


class AvaliacaoSerializer(serializers.ModelSerializer):

    class Meta:
        model = Avaliacao
        fields = ['cliente', 'loja', 'rating', 'comentario']
        read_only_fields = ['cliente']

    def create(self, validated_data):
        print(validated_data)
        user = self.context['request'].user
        cliente = Cliente.objects.get(user=user)
        loja = validated_data['loja']
        avaliacao, _ = Avaliacao.objects.get_or_create(
            cliente=cliente, loja=loja)
        avaliacao.rating = validated_data['rating']
        avaliacao.comentario = validated_data['comentario']
        avaliacao.save()
        recommender.fit()
        return avaliacao
