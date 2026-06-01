from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("dashboard/", views.delivery_dashboard, name="dashboard"),
    path("order/<int:order_id>/update/", views.update_delivery_status, name="update_status"),
    path("order/<int:order_id>/verify/", views.verify_delivery_code, name="verify_code"),
    path("update-status/<int:order_id>/", views.update_delivery_status, name="update_delivery_status"),
    path("verify-code/<int:order_id>/", views.verify_delivery_code, name="verify_delivery_code"),
]
