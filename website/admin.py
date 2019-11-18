from django.contrib import admin
from .models import *


class VendaProdutoInline(admin.TabularInline):
    model = Venda.produtos.through
    extra = 3


class VendaAdmin(admin.ModelAdmin):
    readonly_fields = ('valor_total', )
    inlines = (
        VendaProdutoInline,
    )


# Register your models here.
admin.site.register(Cliente)
admin.site.register(Produto)
admin.site.register(Venda, VendaAdmin)
admin.site.register(VendaProduto)
admin.site.register(Endereco)
admin.site.register(Loja)
admin.site.register(Categoria)
admin.site.register(AvaliacaoLoja)
admin.site.register(AvaliacaoProduto)
admin.site.register(Carrinho)
