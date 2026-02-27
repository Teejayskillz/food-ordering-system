from django import forms
from .models import Category, FoodItem

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

class FoodItemForm(forms.ModelForm):
    class Meta:
        model = FoodItem
        fields = ["category", "name", "description", "price", "image", "available"]