from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from rest_framework import routers
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token

from website.viewsets import *
from website.views import LoginView, StaffView, LoginStaffView
from website.schema_view import schema_view

router = routers.DefaultRouter()
router.register(r'enderecos', EnderecoViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'produtos', ProdutoViewSet)
router.register(r'vendas', VendaViewSet)
router.register(r'avaliacoes-produtos', AvaliacaoProdutoViewSet)
router.register(r'categorias', CategoriaViewSet)
router.register(r'ofertas', OfertaViewSet)
router.register(r'carrinhos', CarrinhoViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    # path('refresh-token/', refresh_jwt_token),
    path('doc/', schema_view),
    path('staff/', StaffView.as_view()),
    path('login-staff/', LoginStaffView.as_view(), name='login-staff'),
]
urlpatterns += static(settings.MEDIA_URL,
                      document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),

        # For django versions before 2.0:
        # url(r'^__debug__/', include(debug_toolbar.urls)),

    ] + urlpatterns
