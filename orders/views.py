from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from menu.models import FoodItem
from .models import Cart, CartItem, Order, OrderItem


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart

@login_required
def add_to_cart(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id, available=True)
    cart = _get_or_create_cart(request.user)

    item, created = CartItem.objects.get_or_create(cart=cart, food=food)
    if not created:
        item.quantity += 1
        item.save()

    return redirect("orders:cart")

@login_required
def cart_view(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("food").all()

    subtotal = sum((i.food.price * i.quantity) for i in items) if items else Decimal("0.00")
    delivery_fee = Decimal("0.00")  # keep simple for now
    total = subtotal + delivery_fee

    return render(request, "cart.html", {
        "cart": cart,
        "items": items,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
    })

@login_required
def update_cart_item(request, item_id):
    if request.method != "POST":
        return redirect("orders:cart")

    cart = _get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    qty_raw = request.POST.get("quantity", "1")
    try:
        qty = int(qty_raw)
    except ValueError:
        qty = 1

    if qty <= 0:
        item.delete()
    else:
        item.quantity = qty
        item.save()

    return redirect("orders:cart")

@login_required
def remove_cart_item(request, item_id):
    cart = _get_or_create_cart(request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    return redirect("orders:cart")

@login_required
@transaction.atomic
def checkout(request):
    cart = _get_or_create_cart(request.user)
    items = cart.items.select_related("food").all()

    if not items.exists():
        return redirect("menu:menu_list")

    #  Prefill values from user profile (GET)
    profile = getattr(request.user, "profile", None)
    initial_phone = profile.phone if profile else ""
    initial_address = profile.default_address if profile else ""

    if request.method == "POST":
        address = request.POST.get("delivery_address", "").strip()
        phone = request.POST.get("phone", "").strip()

        if not address or not phone:
            return render(request, "checkout.html", {
                "items": items,
                "error": "Please fill all fields.",
                "initial_phone": phone or initial_phone,
                "initial_address": address or initial_address,
            })

        #  Save defaults back to profile
        if profile:
            profile.phone = phone
            profile.default_address = address
            profile.save()

        subtotal = sum((i.food.price * i.quantity) for i in items)
        total = subtotal  # + delivery fee if you add later

        order = Order.objects.create(
            user=request.user,
            delivery_address=address,
            phone=phone,
            total_amount=total,
            status="pending",
        )

        for i in items:
            OrderItem.objects.create(
                order=order,
                food=i.food,
                quantity=i.quantity,
                price_at_purchase=i.food.price,
            )

        # Clear cart
        items.delete()

        return redirect("orders:order_detail", order_id=order.id)

    #  GET request renders checkout with prefilled values
    return render(request, "checkout.html", {
        "items": items,
        "initial_phone": initial_phone,
        "initial_address": initial_address,
    })


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "order_list.html", {"orders": orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "order_detail.html", {"order": order})
