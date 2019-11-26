"""testedjango URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from website.viewsets import *
from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token
from django.views.generic import TemplateView
#from rest_framework_swagger.views import get_swagger_view
from website.views import LoginView, StaffView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from website.schema_view import schema_view

#schema_view = get_swagger_view(title='Loja API')

router = routers.DefaultRouter()
router.register(r'enderecos', EnderecoViewSet)
router.register(r'clientes', ClienteViewSet)
router.register(r'produtos', ProdutoViewSet)
router.register(r'vendas', VendaViewSet)
router.register(r'avaliacoes-produtos', AvaliacaoProdutoViewSet)
router.register(r'categorias', CategoriaViewSet)
router.register(r'ofertas', OfertaViewSet)

urlpatterns = [

    path('accounts/login/', auth_views.LoginView.as_view()),
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    path('refresh-token/', refresh_jwt_token),
    path('doc/', schema_view),
    path('staff/', StaffView.as_view())
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),

        # For django versions before 2.0:
        # url(r'^__debug__/', include(debug_toolbar.urls)),

    ] + urlpatterns
