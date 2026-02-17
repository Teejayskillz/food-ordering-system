from django.shortcuts import render, get_object_or_404
from .models import Category, FoodItem

def home(request):
    featured = FoodItem.objects.filter(available=True)[:6]
    return render(request, "home.html", {"featured": featured})

def menu_list(request):
    categories = Category.objects.all()
    foods = FoodItem.objects.filter(available=True)

    cat = request.GET.get("cat")
    if cat:
        foods = foods.filter(category_id=cat)

    return render(request, "menu_list.html", {
        "categories": categories,
        "foods": foods,
        "active_cat": int(cat) if cat and cat.isdigit() else None
    })

def food_detail(request, pk):
    food = get_object_or_404(FoodItem, pk=pk, available=True)
    return render(request, "food_detail.html", {"food": food})
