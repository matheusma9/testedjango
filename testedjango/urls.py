# Django
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

# Rest Framework
from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token

# Website
from website import viewsets as website_viewsets

# Accounts
from accounts import viewsets as accounts_viewsets
from accounts.views import AccTokenObtainView

# Utils
from utils.schemas import schema_view

router = routers.DefaultRouter()
router.register(r'clientes', accounts_viewsets.ClienteViewSet)
router.register(r'enderecos', website_viewsets.EnderecoViewSet)
router.register(r'produtos', website_viewsets.ProdutoViewSet)
router.register(r'vendas', website_viewsets.VendaViewSet)
router.register(r'avaliacoes-produtos',
                website_viewsets.AvaliacaoProdutoViewSet)
router.register(r'categorias', website_viewsets.CategoriaViewSet)
router.register(r'ofertas', website_viewsets.OfertaViewSet)
router.register(r'carrinhos', website_viewsets.CarrinhoViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('login/', AccTokenObtainView.as_view(), name='login'),
    path('doc/', schema_view.with_ui('swagger', cache_timeout=0)),
]
urlpatterns += static(settings.MEDIA_URL,
                      document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
