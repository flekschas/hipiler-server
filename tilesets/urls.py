from django.conf.urls import url, include
from tilesets import views
from rest_framework.routers import SimpleRouter
from rest_framework_swagger.views import get_swagger_view

schema_view = get_swagger_view(title='Pastebin API')
# Create a router and register our viewsets with it.
router = SimpleRouter()

router.register(r'tilesets', views.TilesetsViewSet)


# The API URLs are now determined automatically by the router.
# Additionally, we include the login URLs for the browsable API.
urlpatterns = [
    url(r'^viewconf', views.viewconfs),
    url(r'^tiles/$', views.tiles),
    url(r'^tileset_info/$', views.tileset_info),
    url(r'^suggest/$', views.suggest),
    url(r'^', include(router.urls)),
    url(
        r'^api-auth/',
        include(
            'rest_framework.urls', namespace='rest_framework'
        )
    ),
]
