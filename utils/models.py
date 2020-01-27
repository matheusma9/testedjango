from django.db import models

# Create your models here.


class ModelLog(models.Model):
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    update_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        abstract = True
