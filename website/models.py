from django.db import models
from rest_framework import serializers
from django.db.models import F, Sum, Avg
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from taggit.managers import TaggableManager
from slugify import slugify
# Create your models here.


class ModelDate(models.Model):
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    update_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        abstract = True


class Endereco(ModelDate):
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
    numero_casa = models.CharField('Número', max_length=5)
    complemento = models.CharField(
        'Complemento', max_length=50, blank=True, null=True)
    cep = models.CharField('CEP', max_length=10)
    cidade = models.CharField('Cidade', max_length=120)
    uf = models.CharField('UF', max_length=2, choices=UF, default='AC')

    def __str__(self):
        return self.cep

    class Meta:
        verbose_name = "Endereço"
        verbose_name_plural = "Endereços"
        ordering = ['cep']


class Categoria(ModelDate):
    nome = models.CharField('Nome', max_length=50)
    slug = models.SlugField(unique=True)
    qtd_acessos = models.PositiveIntegerField(
        'Quantidade de acessos', default=0)

    def __str__(self):
        return self.nome

    class Meta:
        ordering = ['nome']


class Produto(ModelDate):
    descricao = models.CharField('Descrição', max_length=100)
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    qtd_estoque = models.PositiveIntegerField('Quantidade em estoque')
    qtd_limite = models.PositiveIntegerField('Quantidade limite', default=100)
    descricao_completa = models.TextField(
        'Descrição Completa', blank=True, null=True)
    logo = models.ImageField(
        upload_to='website/images', verbose_name='Imagem',
        null=True, blank=True)
    categorias = models.ManyToManyField(
        'website.Categoria', related_name='produtos')
    avaliacoes = models.ManyToManyField(
        'website.Cliente', through='AvaliacaoProduto')

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
                            ' tem uma quantidade em estoque menor do que a desejada')
        return quantidade, error, messages

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['descricao']


class Carrinho(ModelDate):
    itens = models.ManyToManyField('website.Produto', through='ItensCarrinho')
    valor_total = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, blank=True, default=Decimal('0.00'))

    def atualizar_valor(self):
        expression = Sum(F('produto__valor') * F('quantidade'),
                         output_field=models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00')))
        self.valor_total = self.itens_carrinho.aggregate(
            valor_total=expression)['valor_total'] or Decimal('0.00')
        self.save()

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
                venda_produto = VendaProduto(
                    venda=venda, produto=item.produto, valor=item.valor, quantidade=item.quantidade)
                venda_produto.save()
                venda.vendas_produtos_venda.add(venda_produto)
            else:
                venda.vendas_produtos_venda.all().delete()
                venda.delete()
                raise serializers.ValidationError(
                    'O item ' + str(item.produto) + ' tem uma quantidade em estoque menor do que a desejada')

        for venda_produto in venda.vendas_produtos_venda.all():
            venda_produto.produto.qtd_estoque -= venda_produto.quantidade
            venda_produto.produto.save()
        venda.save()
        return venda


class ItensCarrinho(ModelDate):
    carrinho = models.ForeignKey(
        'website.Carrinho', on_delete=models.CASCADE, related_name='itens_carrinho')
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='itens_carrinhos')
    valor = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, null=True)
    quantidade = models.PositiveIntegerField('Quantidade', null=True)

    def __str__(self):
        return str(self.carrinho.pk) + '-' + self.produto.descricao

    class Meta:
        verbose_name = 'Item do carrinho'
        verbose_name_plural = 'Itens dos carrinhos'
        ordering = ['-update_at']


class Cliente(ModelDate):
    SEXO = (('M', 'Masculino'), ('F', 'Feminino'))

    nome = models.CharField('Nome', max_length=50)
    foto = models.ImageField(
        upload_to='website/images/profile', verbose_name='Foto',
        null=True, blank=True)
    sobrenome = models.CharField('Sobrenome', max_length=150)
    cpf = models.IntegerField('CPF', unique=True)
    rg = models.IntegerField('RG', unique=True, blank=True, null=True)
    data_nascimento = models.DateField(
        'Data de Nascimento', blank=True, null=True)
    sexo = models.CharField('Sexo', max_length=1, choices=SEXO, default='M')
    endereco = models.ForeignKey(
        Endereco, on_delete=models.CASCADE, related_name='clientes')
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='cliente')
    carrinho = models.OneToOneField(
        'website.Carrinho', on_delete=models.CASCADE, null=True, blank=True
    )

    @property
    def idade(self):
        now = timezone.now()
        idade = (timezone.now().date() - self.data_nascimento).days//365
        return idade

    def __str__(self):
        return self.nome + ' ' + self.sobrenome

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nome']


class Venda(ModelDate):
    produtos = models.ManyToManyField(
        'website.Produto', through='VendaProduto', related_name='vendas')
    cliente = models.ForeignKey(
        'website.Cliente', on_delete=models.CASCADE, verbose_name='Cliente', related_name='vendas')
    valor_total = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, blank=True, default=Decimal('0.00'))

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


class VendaProduto(ModelDate):
    venda = models.ForeignKey(
        'website.Venda', on_delete=models.CASCADE, related_name='vendas_produtos_venda')
    produto = models.ForeignKey(
        'website.Produto', on_delete=models.CASCADE, related_name='vendas_produtos_produto')
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField('Quantidade')

    def __str__(self):
        return str(self.venda.pk) + '-' + self.produto.descricao

    class Meta:
        verbose_name = 'Venda de produto'
        verbose_name_plural = 'Vendas de produtos'
        ordering = ['-update_at']


class AvaliacaoProduto(ModelDate):
    cliente = models.ForeignKey(
        'website.Cliente', on_delete=models.CASCADE, related_name="avaliacoes_produto")
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
