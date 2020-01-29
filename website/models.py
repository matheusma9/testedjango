from django.db import models
from django.db.models import F, Sum, Avg, Count
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator

from utils.models import ModelLog

from rest_framework import serializers
from decimal import Decimal
from slugify import slugify
# Create your models here.


class Endereco(ModelLog):
    UF = (('AC', 'Acre'),
          ('AL', 'Alagoas'),
          ('AP', 'Amapá'),
          ('AM', 'Amazonas'),
          ('BA', 'Bahia'),
          ('CE', 'Ceará'),
          ('DF', 'Distrito Federal'),
          ('ES', 'Espírito Santo'),
          ('GO', 'Goiás'),
          ('MA', 'Maranhão'),
          ('MT', 'Mato Grosso'),
          ('MS', 'Mato Grosso do Sul'),
          ('MG', 'Minas Gerais'),
          ('PA', 'Pará'),
          ('PB', 'Paraíba'),
          ('PR', 'Paraná'),
          ('PE', 'Pernambuco'),
          ('PI', 'Piauí'),
          ('RR', 'Roraima'),
          ('RO', 'Rondônia'),
          ('RJ', 'Rio de Janeiro'),
          ('RN', 'Rio Grande do Norte'),
          ('RS', 'Rio Grande do Sul'),
          ('SC', 'Santa Catarina'),
          ('SP', 'São Paulo'),
          ('SE', 'Sergipe'),
          ('TO', 'Tocantins')
          )

    bairro = models.CharField('Bairro', max_length=50)
    rua = models.CharField('Rua', max_length=50)
    numero_casa = models.PositiveIntegerField('Número')
    complemento = models.CharField(
        'Complemento', max_length=50, blank=True, null=True)
    cep = models.CharField('CEP', max_length=10, validators=[
                           RegexValidator(regex=r'^\d{5}\-\d{3}$')])
    cidade = models.CharField('Cidade', max_length=120)
    uf = models.CharField('UF', max_length=2, choices=UF, default='AC')

    def __str__(self):
        return self.cep

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ['cep']


class Categoria(ModelLog):
    nome = models.CharField('Nome', max_length=50)
    slug = models.SlugField(unique=True)
    qtd_acessos = models.PositiveIntegerField(
        'Quantidade de acessos', default=0)

    def __str__(self):
        return self.nome

    class Meta:
        ordering = ['nome']

    @property
    def receita(self):
        expression = models.ExpressionWrapper(
            F('itens_vendas__valor')*F('itens_vendas__quantidade'),
            output_field=models.DecimalField(
                max_digits=10, decimal_places=2,
                default=Decimal('0.00')))

        return self.produtos.annotate(receita=expression).aggregate(
            Sum('receita'))['receita__sum'] or Decimal('0.0')

    @property
    def vendas(self):
        return self.produtos.annotate(n_vendas=Count('itens_vendas')).aggregate(
            Sum('n_vendas'))['n_vendas__sum'] or 0


class Produto(ModelLog):
    descricao = models.CharField('Descrição', max_length=100)
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    qtd_estoque = models.PositiveIntegerField('Quantidade em estoque')
    qtd_limite = models.PositiveIntegerField('Quantidade limite', default=100)
    descricao_completa = models.TextField(
        'Descrição Completa', blank=True, null=True)
    categorias = models.ManyToManyField(
        'website.Categoria', related_name='produtos')
    avaliacoes = models.ManyToManyField(
        'accounts.Cliente', through='AvaliacaoProduto')

    @property
    def capa(self):
        capa = self.imagens.filter(capa=True).first()
        if capa:
            return capa.imagem
        else:
            return None

    @property
    def rating(self):
        return self.avaliacoes_produto.aggregate(rating=Avg('rating'))['rating'] or Decimal('0.00')

    def __str__(self):
        return self.descricao

    def add_categoria(self, categoria):
        c, created = Categoria.objects.get_or_create(
            nome=categoria, slug=slugify(categoria))
        self.categorias.add(c)
        self.save()

    def validar_qtd(self, quantidade, error, messages):
        if self.qtd_estoque == 0:
            messages.append('O item ' +
                            str(self) + ' está fora de estoque')
            error = True
            return 0, error, messages
        if self.qtd_estoque < quantidade:
            quantidade = self.qtd_estoque
            error = True
            messages.append('O item ' +
                            str(self) +
                            ' tem uma quantidade em estoque menor do que a desejada')
        if self.qtd_limite < quantidade:
            quantidade = self.qtd_limite
            error = True
            messages.append('O item ' +
                            str(self) +
                            ' tem uma quantidade limite menor do que a desejada')
        return quantidade, error, messages

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['descricao']


class Carrinho(ModelLog):
    itens = models.ManyToManyField('website.Produto', through='ItemCarrinho')
    valor_total = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, blank=True, default=Decimal('0.00'))

    def associar(self, other):
        if isinstance(other, Carrinho):
            error = []
            messages = []
            if other.pk != self.pk:
                for item in other.itens_carrinho.all():
                    item_carrinho, error, messages = self.adicionar_item(
                        item.produto, item.quantidade, error, messages)
                self.atualizar_valor()
                other.delete()
        else:
            raise TypeError("O objeto 'other' deve ser do tipo Carrinho")
        return error, messages

    def adicionar_item(self, produto, quantidade, error, messages):
        if produto.qtd_estoque:
            item_carrinho, _ = ItemCarrinho.objects.get_or_create(
                carrinho=self, produto=produto)
            quantidade, error, messages = produto.validar_qtd(
                (item_carrinho.quantidade or 0) + quantidade, error, messages)
            item_carrinho.quantidade = quantidade
            item_carrinho.save()
        else:
            error = True
            messages.append('O item ' +
                            str(self) + ' está fora de estoque')
        return self, error, messages

    def atualizar_valor(self):
        self.atualizar_itens()
        expression = Sum(
            F('valor') * F('quantidade'),
            output_field=models.DecimalField(
                max_digits=10, decimal_places=2,
                default=Decimal('0.00')))

        self.valor_total = self.itens_carrinho.aggregate(
            valor_total=expression)['valor_total'] or Decimal('0.00')
        self.save()

    def atualizar_itens(self):
        for item in self.itens_carrinho.all():
            item.atualizar_valor()

    def to_venda(self):
        venda = Venda(cliente=self.cliente,
                      valor_total=self.valor_total)
        venda.save()
        for item in self.itens_carrinho.all():
            if item.produto.qtd_estoque <= 0:
                venda.delete()
                raise serializers.ValidationError(
                    'O item ' + str(item.produto) + ' está fora de estoque.')
            if item.quantidade <= item.produto.qtd_estoque:
                item_venda = ItemVenda(
                    venda=venda, produto=item.produto,
                    valor=item.valor,
                    quantidade=item.quantidade)
                item_venda.save()
                venda.itens.add(item_venda)
            else:
                venda.itens.all().delete()
                venda.delete()
                raise serializers.ValidationError(
                    'O item ' + str(item.produto) + ' tem uma quantidade em estoque menor do que a desejada')

        for item_venda in venda.itens.all():
            item_venda.produto.qtd_estoque -= item_venda.quantidade
            item_venda.produto.save()
        venda.save()
        return venda

    def print_itens(self):
        for item in self.itens_carrinho.all():
            print(item.produto, '-', item.quantidade)

    def __str__(self):
        return str(self.pk) + ' - ' + str(self.valor_total)


class ItemCarrinho(ModelLog):
    carrinho = models.ForeignKey(
        'website.Carrinho', on_delete=models.CASCADE, related_name='itens_carrinho')
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='itens_carrinhos')
    valor = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, null=True)
    quantidade = models.PositiveIntegerField('Quantidade', null=True)

    def atualizar_valor(self):
        queryset = Oferta.objects.filter(
            validade__gte=timezone.now(), produto=self.produto).exclude(pk=self.pk)
        if queryset.exists():
            self.valor = queryset[0].valor
        else:
            self.valor = self.produto.valor
        self.save()

    def __str__(self):
        return str(self.carrinho.pk) + '-' + self.produto.descricao

    class Meta:
        verbose_name = 'Item do carrinho'
        verbose_name_plural = 'Itens dos carrinhos'
        ordering = ['-update_at']
        unique_together = [('carrinho', 'produto')]


class Venda(ModelLog):
    produtos = models.ManyToManyField(
        'website.Produto', through='ItemVenda', related_name='vendas')
    cliente = models.ForeignKey(
        'accounts.Cliente', on_delete=models.CASCADE, verbose_name='Cliente', related_name='vendas')
    valor_total = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, blank=True, default=Decimal('0.00'))
    endereco_entrega = models.ForeignKey(
        'website.Endereco', on_delete=models.CASCADE, related_name='vendas', null=True, blank=True)

    def atualizar_valor(self):
        expression = Sum(F('valor') * F('quantidade'),
                         output_field=models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')))
        self.valor_total = self.vendas_produtos_venda.aggregate(
            valor_total=expression)['valor_total']
        self.save()

    def __str__(self):
        return str(self.pk) + ' - ' + str(self.cliente) + ' - ' + str(self.valor_total)

    class Meta:
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        ordering = ['-update_at']


class ItemVenda(ModelLog):
    venda = models.ForeignKey(
        'website.Venda', on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='itens_vendas')
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField('Quantidade')

    def __str__(self):
        return str(self.venda.pk) + '-' + self.produto.descricao

    class Meta:
        verbose_name = 'Item da venda'
        verbose_name_plural = 'Itens das vendas'
        ordering = ['-update_at']


class AvaliacaoProduto(ModelLog):
    cliente = models.ForeignKey(
        'accounts.Cliente', on_delete=models.CASCADE, related_name="avaliacoes_produto")
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name="avaliacoes_produto")
    rating = models.IntegerField('Rating', default=1, validators=[
        MaxValueValidator(5),
        MinValueValidator(1)
    ])
    comentario = models.TextField('Comentário', blank=True, null=True)

    def __str__(self):
        return '(' + str(self.cliente.user) + ' - ' + str(self.produto) + '): ' + str(self.rating)

    class Meta:
        unique_together = (('cliente', 'produto'),)
        verbose_name = 'Avaliação do Produto'
        verbose_name_plural = 'Avaliações dos Produtos'


class Oferta(ModelLog):

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ofertas')
    descricao = models.TextField('Descrição', null=True, blank=True)
    foto = models.ImageField(
        upload_to='website/images/ofertas', verbose_name='Foto',
        null=True, blank=True)
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='ofertas')
    validade = models.DateTimeField('Validade')
    is_banner = models.BooleanField('É banner?')

    def __str__(self):
        return str(self.produto) + ' - ' + str(self.valor) + ' - ' + str(self.validade)

    class Meta:
        ordering = ['-validade']


class ImagemProduto(ModelLog):
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(
        upload_to='website/images', verbose_name='Imagem',
        null=True, blank=True)
    capa = models.BooleanField('É capa?', default=False, blank=True)

    def __str__(self):
        return str(self.produto) + '-' + str(self.capa)

    class Meta:
        verbose_name = 'Imagem do Produtos'
        verbose_name_plural = 'Imagens dos Produtos'
