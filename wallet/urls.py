from django.urls import path
from . import views

app_name = "wallet"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("topup/", views.topup_create, name="topup_create"),
]
