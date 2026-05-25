from django.shortcuts import render, get_object_or_404
from .models import Category, FoodItem
from orders.models import Cart, CartItem

def home(request):
    featured = FoodItem.objects.filter(is_archived=False, available=True)[:6]

    cart_item_ids = set()
    cart_quantities = {}

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            items = cart.items.select_related('food').all()
            cart_item_ids = {item.food_id for item in items}
            cart_quantities = {item.food_id: item.quantity for item in items}

    return render(request, 'home.html', {
        'featured': featured,
        'cart_item_ids': cart_item_ids,
        'cart_quantities': cart_quantities,
       
    })

def menu_list(request):
    categories = Category.objects.all()
    foods = FoodItem.objects.filter(available=True, is_archived=False)

    cat = request.GET.get("cat")
    if cat:
        foods = foods.filter(category_id=cat)

    cart_item_ids = set()
    cart_quantities = {}

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            items = cart.items.select_related('food').all()
            cart_item_ids = {item.food_id for item in items}
            cart_quantities = {item.food_id: item.quantity for item in items}

    return render(request, "menu_list.html", {
        "categories": categories,
        "foods": foods,
        "active_cat": int(cat) if cat and cat.isdigit() else None,
        "cart_item_ids": cart_item_ids,
        "cart_quantities": cart_quantities,
    })

def food_detail(request, pk):
    food = get_object_or_404(FoodItem, pk=pk, available=True)
    return render(request, "food_detail.html", {"food": food})

from django.shortcuts import render

def service_worker(request):
    response = render(request, "sw.js", content_type="application/javascript")
    return response
