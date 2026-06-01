from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]
    list_display = ("id", "user", "created_at")

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "delivery_person",
        "delivery_verified",
        "payment_method",
        "is_paid",
        "total_amount",
        "created_at",
    )

    list_filter = ("status", "payment_method", "is_paid", "delivery_verified")
    search_fields = ("user__username", "phone", "delivery_address")

    inlines = [OrderItemInline]

    fieldsets = (
        ("Order Info", {
            "fields": ("user", "status", "total_amount")
        }),
        ("Delivery Info", {
            "fields": (
                "delivery_address",
                "phone",
                "delivery_person",
                "delivery_code",
                "delivery_verified",
            )
        }),
        ("Payment Info", {
            "fields": ("payment_method", "is_paid")
        }),
    )