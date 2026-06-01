from django.urls import path
from .control_views import (
    dashboard,
    orders_list, order_detail,
    assign_delivery_person,
    update_status,  # ADD THIS IMPORT
    verify_code,    # ADD THIS IMPORT

    menu_list, toggle_food_availability,
    category_create, category_edit,
    food_create, food_edit,

    topups_list, topup_review,
    wallet_transactions,
    toggle_food_archive,
)

app_name = "control"

urlpatterns = [
    path("", dashboard, name="dashboard"),

    # Orders
    path("orders/", orders_list, name="orders_list"),
    path("orders/<int:order_id>/", order_detail, name="order_detail"),
    path("orders/<int:order_id>/assign-delivery/", assign_delivery_person, name="assign_delivery_person"),

    # Delivery/Rider URLs (NEW)
    path("delivery/update-status/<int:order_id>/", update_status, name="update_status"),
    path("delivery/verify-code/<int:order_id>/", verify_code, name="verify_code"),

    # Menu
    path("menu/", menu_list, name="menu_list"),
    path("menu/toggle/<int:food_id>/", toggle_food_availability, name="toggle_food"),
    path("menu/categories/add/", category_create, name="category_add"),
    path("menu/categories/<int:category_id>/edit/", category_edit, name="category_edit"),
    path("menu/foods/add/", food_create, name="food_add"),
    path("menu/foods/<int:food_id>/edit/", food_edit, name="food_edit"),
    path("menu/archive/<int:food_id>/", toggle_food_archive, name="toggle_food_archive"),

    # Wallet
    path("wallet/topups/", topups_list, name="topups_list"),
    path("wallet/topups/<int:topup_id>/", topup_review, name="topup_review"),
    path("wallet/transactions/", wallet_transactions, name="wallet_transactions"),
]