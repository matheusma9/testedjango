import django_filters
from .models import Produto, Categoria, Venda


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


class VendaFilter(django_filters.FilterSet):
    inicio = django_filters.DateFilter(
        field_name="created_at", lookup_expr='date__gt')
    fim = django_filters.DateFilter(
        field_name="created_at", lookup_expr='date__lt')
    date = django_filters.RangeFilter(field_name='created_at')

    class Meta:
        model = Venda
        fields = ['inicio', 'fim', 'date']
