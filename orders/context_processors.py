from .models import Cart

def cart_count(request):
    count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            count = sum(cart.items.values_list('quantity', flat=True))
    return {'cart_count': count}