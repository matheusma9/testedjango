from django.forms import ModelForm
from .models import Cliente

def ClienteForm(models.Model):

    class Meta:
        model = Cliente
        fields = ['nome', 'cpf', 'rg', 'data_nascimento', 'sexo', 'endereco'] 