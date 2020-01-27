from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

from utils.models import ModelLog

# Create your models here.


class Cliente(ModelLog):
    SEXO = (('M', 'Masculino'), ('F', 'Feminino'))

    nome = models.CharField('Nome', max_length=50)
    foto = models.ImageField(
        upload_to='website/images/profile', verbose_name='Foto',
        null=True, blank=True)
    sobrenome = models.CharField('Sobrenome', max_length=150)
    cpf = models.CharField('CPF', unique=True, max_length=14, validators=[
                           RegexValidator(regex=r'^\d{3}\.\d{3}\.\d{3}\-\d{2}$')])
    rg = models.CharField(
        'RG', unique=True, max_length=20, blank=True, null=True,  validators=[
            RegexValidator(regex=r'^\d+$')])
    data_nascimento = models.DateField(
        'Data de Nascimento', blank=True, null=True)
    sexo = models.CharField('Sexo', max_length=1, choices=SEXO, default='M')
    enderecos = models.ManyToManyField(
        'website.Endereco', related_name='clientes')
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
