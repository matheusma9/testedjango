import django_filters
from .models import Produto, Categoria


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
