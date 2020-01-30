# Generated by Django 3.0.2 on 2020-01-30 14:53

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_auto_20200124_1501'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cliente',
            name='cpf',
            field=models.CharField(max_length=11, unique=True, validators=[django.core.validators.RegexValidator(regex='^\\d{11}$')], verbose_name='CPF'),
        ),
    ]
