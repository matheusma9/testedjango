from django.db import models
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


class Categoria(ModelDate):
    nome = models.CharField('Nome', max_length=50)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.nome


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


class Loja(ModelDate):
    nome_fantasia = models.CharField('Nome Fantasia', max_length=150)
    cnpj = models.IntegerField('CNPJ', unique=True)
    razao_social = models.CharField(
        'Razão Social', max_length=150, unique=True)
    avaliacoes = models.ManyToManyField(
        Cliente, related_name='avaliacoes', through='Avaliacao')
    logo = models.ImageField(
        upload_to='website/images', verbose_name='Imagem',
        null=True, blank=True)
    categorias = models.ManyToManyField(Categoria)

    @property
    def rating(self):
        return self.avaliacoes_loja.aggregate(rating=Avg('rating'))['rating']

    def __str__(self):
        return self.nome_fantasia

    class Meta:
        verbose_name = 'Loja'
        verbose_name_plural = 'Lojas'
        ordering = ['nome_fantasia']


class Produto(ModelDate):
    descricao = models.CharField('Descrição', max_length=100)
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='produtos')
    qtd_estoque = models.IntegerField('Quantidade em estoque')
    descricao_completa = models.TextField(
        'Descrição Completa', blank=True, null=True)
    logo = models.ImageField(
        upload_to='website/images', verbose_name='Imagem',
        null=True, blank=True)
    categorias = models.ManyToManyField(Categoria)

    def __str__(self):
        return self.descricao

    def add_categoria(self, categoria):
        c, created = Categoria.objects.get_or_create(
            nome=categoria, slug=slugify(categoria))
        if created:
            self.loja.categorias.add(c)
            self.loja.save()
        self.categorias.add(c)
        self.save()

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['descricao']


class Venda(ModelDate):
    produtos = models.ManyToManyField(
        Produto, through='VendaProduto', related_name='vendas')
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, verbose_name='Cliente', related_name='vendas')
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='vendas')
    valor_total = models.DecimalField(
        'Valor', max_digits=10, decimal_places=2, blank=True, default=Decimal('0.00'))

    def atualizar_valor(self):
        expression = Sum(F('valor') * F('quantidade'),
                         output_field=models.DecimalField(max_digits=10, decimal_places=2))
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
        Venda, on_delete=models.CASCADE, related_name='vendas_produtos_venda')
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='vendas_produtos_produto')
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField('Quantidade')

    def __str__(self):
        return str(self.venda.pk) + '-' + self.produto.descricao

    class Meta:
        verbose_name = 'Venda de produto'
        verbose_name_plural = 'Vendas de produtos'
        ordering = ['-update_at']


class Avaliacao(ModelDate):
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='avaliacoes_cliente')
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='avaliacoes_loja')
    rating = models.IntegerField('Rating', default=1, validators=[
        MaxValueValidator(5),
        MinValueValidator(1)
    ])
    comentario = models.TextField('Comentário', blank=True, null=True)

    class Meta:
        unique_together = (('cliente', 'loja'),)
