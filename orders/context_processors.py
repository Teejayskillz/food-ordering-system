from django.db.models import Sum

from .models import Cart

def cart_count(request):
    """
    Adds `cart_count` to every template.
    cart_count = total quantity of items in the user's cart.
    """
    if not request.user.is_authenticated:
        return {"cart_count": 0}

    cart = Cart.objects.filter(user=request.user).first()
    if not cart:
        return {"cart_count": 0}

    total_qty = cart.items.aggregate(total=Sum("quantity"))["total"] or 0
    return {"cart_count": total_qty}
