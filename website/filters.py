import django_filters
from .models import Produto, Categoria, Loja


class ProdutoFilter(django_filters.FilterSet):
    tags = django_filters.CharFilter(method='tag_filter')

    class Meta:
        model = Produto
        fields = ['tags']

    def tag_filter(self, queryset, name, value):
        slugs = value.split(',')
        categorias = Categoria.objects.filter(slug__in=slugs)
        queryset = queryset.filter(categorias__in=categorias)
        return queryset


class ProdutoLojaFilter(django_filters.FilterSet):
    categorias = django_filters.CharFilter(method='tag_filter')

    class Meta:
        model = Loja
        fields = ['categorias']

    def tag_filter(self, queryset, name, value):

        return queryset
