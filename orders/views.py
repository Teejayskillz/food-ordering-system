from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from menu.models import FoodItem
from .models import Cart, CartItem, Order, OrderItem
from django.contrib import messages
from wallet.models import Wallet, WalletTransaction


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme

@login_required
def add_to_cart(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id, available=True)
    cart = _get_or_create_cart(request.user)

    item, created = CartItem.objects.get_or_create(cart=cart, food=food)
    if not created:
        item.quantity += 1
        item.save()
    else:
        # created = True means quantity is likely 1 already, but make it explicit
        item.quantity = 1
        item.save()

    # Redirect back to where the user came from (best UX)
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER")

    # Safety: only allow redirects to your own site
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)

    # Fallback
    return redirect("menu:menu_list")

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

    profile = getattr(request.user, "profile", None)
    initial_phone = profile.phone if profile else ""
    initial_address = profile.default_address if profile else ""

    subtotal = sum((i.food.price * i.quantity) for i in items)
    total = subtotal  # + delivery fee later if you want

    # Wallet info for template (safe even if wallet doesn't exist yet)
    wallet = Wallet.objects.filter(user=request.user).first()
    wallet_balance = wallet.balance if wallet else Decimal("0.00")

    if request.method == "POST":
        address = request.POST.get("delivery_address", "").strip()
        phone = request.POST.get("phone", "").strip()
        payment_method = request.POST.get("payment_method", "cod")  # cod or wallet

        if not address or not phone:
            return render(request, "checkout.html", {
                "items": items,
                "subtotal": subtotal,
                "total": total,
                "wallet_balance": wallet_balance,
                "error": "Please fill all fields.",
                "initial_phone": phone or initial_phone,
                "initial_address": address or initial_address,
                "selected_payment": payment_method,
            })

        if profile:
            profile.phone = phone
            profile.default_address = address
            profile.save()

        # ✅ If user chose Wallet, validate balance and debit first
        if payment_method == "wallet":
            wallet = Wallet.objects.select_for_update().filter(user=request.user).first()
            if not wallet:
                return render(request, "checkout.html", {
                    "items": items,
                    "subtotal": subtotal,
                    "total": total,
                    "wallet_balance": Decimal("0.00"),
                    "error": "You don't have a wallet yet. Fund your wallet first.",
                    "initial_phone": phone or initial_phone,
                    "initial_address": address or initial_address,
                    "selected_payment": payment_method,
                })

            if wallet.balance < total:
                return render(request, "checkout.html", {
                    "items": items,
                    "subtotal": subtotal,
                    "total": total,
                    "wallet_balance": wallet.balance,
                    "error": "Insufficient wallet balance. Please fund your wallet.",
                    "initial_phone": phone or initial_phone,
                    "initial_address": address or initial_address,
                    "selected_payment": payment_method,
                })

            # Debit wallet
            wallet.balance = wallet.balance - total
            wallet.save(update_fields=["balance", "updated_at"])

        # Create order
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

        # Log wallet transaction only if wallet was used
        if payment_method == "wallet":
            WalletTransaction.objects.create(
                wallet=wallet,
                tx_type="debit",
                source="order",
                amount=total,
                order=order,  # only if you included this FK in WalletTransaction
                note=f"Payment for Order #{order.id}",
            )
            messages.success(request, "Paid with wallet successfully.")

        items.delete()
        return redirect("orders:order_detail", order_id=order.id)

    return render(request, "checkout.html", {
        "items": items,
        "subtotal": subtotal,
        "total": total,
        "wallet_balance": wallet_balance,
        "initial_phone": initial_phone,
        "initial_address": initial_address,
        "selected_payment": "cod",
    })


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "order_list.html", {"orders": orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "order_detail.html", {"order": order})
