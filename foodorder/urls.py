from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static 
from django.conf import settings 

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("menu.urls")),
    path("", include("orders.urls")),
    path("accounts/", include("accounts.urls")),
    path("wallet/", include("wallet.urls")),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)