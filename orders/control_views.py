from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from menu.models import FoodItem, Category
from wallet.models import WalletTopUp, Wallet, WalletTransaction
from menu.forms import CategoryForm, FoodItemForm
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Coalesce
from orders.models import Order, OrderItem
from django.contrib.auth.models import User
import random
import string


# =========================
# STAFF CHECK (MUST BE FIRST)
# =========================
def staff_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.is_staff,
        login_url="accounts:login"
    )(view_func)


# =========================
# DELIVERY HELPERS
# =========================
def _generate_delivery_code():
    return ''.join(random.choices(string.digits, k=6))


# =========================
# DELIVERY ASSIGNMENT (NEW)
# =========================
@staff_required
def assign_delivery_person(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    delivery_guys = User.objects.filter(profile__is_delivery_guy=True)

    if request.method == "POST":
        rider_id = request.POST.get("delivery_person")
        rider = get_object_or_404(User, id=rider_id)

        order.delivery_person = rider
        order.status = "assigned"

        if not order.delivery_code:
            order.delivery_code = _generate_delivery_code()

        order.save(update_fields=["delivery_person", "status", "delivery_code"])

        messages.success(request, f"Order assigned to {rider.username}")
        return redirect("control:order_detail", order_id=order.id)

    return render(request, "control/assign_delivery.html", {
        "order": order,
        "delivery_guys": delivery_guys
    })


# =========================
# TOPUPS LIST
# =========================
@staff_required
def topups_list(request):
    status = (request.GET.get("status") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()

    qs = WalletTopUp.objects.select_related("user", "reviewed_by").order_by("-created_at")
    allowed = {"pending", "approved", "rejected"}

    if status in allowed:
        qs = qs.filter(status=status)

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(reference__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "control/topups_list.html", {
        "page_obj": page_obj,
        "status": status,
        "q": q,
    })


# =========================
# FOOD ARCHIVE
# =========================
@staff_required
def toggle_food_archive(request, food_id):
    if request.method != "POST":
        return redirect("control:menu_list")

    food = get_object_or_404(FoodItem, id=food_id)

    food.is_archived = not food.is_archived
    food.archived_at = timezone.now() if food.is_archived else None
    food.save(update_fields=["is_archived", "archived_at"])

    messages.success(request, f"{'Archived' if food.is_archived else 'Unarchived'}: {food.name}")
    return redirect("control:menu_list")


# =========================
# DASHBOARD
# =========================
@staff_required
def dashboard(request):
    today = timezone.localdate()
    last_7 = timezone.now() - timedelta(days=7)

    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    preparing_orders = Order.objects.filter(status="preparing").count()
    assigned_orders = Order.objects.filter(status="assigned").count()
    on_the_way_orders = Order.objects.filter(status="on_the_way").count()
    delivered_today = Order.objects.filter(status="delivered", created_at__date=today).count()
    delivered_orders = Order.objects.filter(status="delivered").count()
    cancelled_orders = Order.objects.filter(status="cancelled").count()

    paid_orders = Order.objects.filter(is_paid=True).count()

    today_revenue = (
        Order.objects.filter(is_paid=True, created_at__date=today)
        .aggregate(v=Coalesce(Sum("total_amount"), Decimal("0.00")))["v"]
    )

    last7_revenue = (
        Order.objects.filter(is_paid=True, created_at__gte=last_7)
        .aggregate(v=Coalesce(Sum("total_amount"), Decimal("0.00")))["v"]
    )

    pending_topups = WalletTopUp.objects.filter(status="pending").count()

    total_food = FoodItem.objects.count()
    available_food = FoodItem.objects.filter(available=True).count()

    top_foods = (
        OrderItem.objects.select_related("food")
        .values("food__name")
        .annotate(qty=Coalesce(Sum("quantity"), 0))
        .order_by("-qty")[:5]
    )

    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:8]
    recent_topups = WalletTopUp.objects.select_related("user", "reviewed_by").order_by("-created_at")[:8]

    return render(request, "control/dashboard.html", {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "preparing_orders": preparing_orders,
        "assigned_orders": assigned_orders,
        "on_the_way_orders": on_the_way_orders,
        "delivered_today": delivered_today,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,
        "paid_orders": paid_orders,
        "today_revenue": today_revenue,
        "last7_revenue": last7_revenue,
        "pending_topups": pending_topups,
        "total_food": total_food,
        "available_food": available_food,
        "top_foods": top_foods,
        "recent_orders": recent_orders,
        "recent_topups": recent_topups,
    })


# =========================
# ORDERS LIST
# =========================
@staff_required
def orders_list(request):
    status = (request.GET.get("status") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()

    qs = Order.objects.select_related("user").order_by("-created_at")

    allowed_statuses = {"pending", "preparing", "assigned", "on_the_way", "delivered", "cancelled"}
    if status in allowed_statuses:
        qs = qs.filter(status=status)

    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(phone__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "control/orders_list.html", {
        "page_obj": page_obj,
        "status": status,
        "q": q,
        "allowed_statuses": sorted(list(allowed_statuses)),
    })


# =========================
# WALLET DEBIT
# =========================
def _wallet_debit_for_order_once(staff_user, order) -> bool:
    already = WalletTransaction.objects.filter(
        order=order, source="order", tx_type="debit"
    ).exists()

    if already:
        return False

    wallet = Wallet.objects.select_for_update().filter(user=order.user).first()
    if wallet is None:
        raise ValueError("User does not have a wallet.")

    if wallet.balance < order.total_amount:
        raise ValueError("Insufficient wallet balance.")

    wallet.balance -= order.total_amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        tx_type="debit",
        source="order",
        amount=order.total_amount,
        order=order,
        note=f"Order payment approved by {staff_user}",
    )
    return True


# =========================
# ORDER DETAIL + DELIVERY FLOW
# =========================
@staff_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__food"),
        id=order_id
    )

    allowed_statuses = {"pending", "preparing", "assigned", "on_the_way", "delivered", "cancelled"}

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        # ---------------------------
        # UPDATE ORDER STATUS
        # ---------------------------
        if action == "update_status":
            new_status = (request.POST.get("status") or "").strip().lower()

            if new_status not in allowed_statuses:
                messages.error(request, "Invalid status.")
            else:
                order.status = new_status
                order.save(update_fields=["status"])
                messages.success(request, "Order status updated.")

            return redirect("control:order_detail", order_id=order.id)

        # ---------------------------
        # MARK PAID
        # ---------------------------
        elif action == "mark_paid":
            if order.is_paid:
                messages.warning(request, "Already paid.")
                return redirect("control:order_detail", order_id=order.id)

            with transaction.atomic():
                order = Order.objects.select_for_update().get(id=order.id)

                if order.payment_method == "wallet":
                    try:
                        _wallet_debit_for_order_once(request.user, order)
                    except ValueError as e:
                        messages.error(request, str(e))
                        return redirect("control:order_detail", order_id=order.id)

                order.is_paid = True
                order.save(update_fields=["is_paid"])
                messages.success(request, "Order marked as paid.")

            return redirect("control:order_detail", order_id=order.id)

        # ---------------------------
        # UNMARK PAID
        # ---------------------------
        elif action == "unmark_paid":
            order.is_paid = False
            order.save(update_fields=["is_paid"])
            messages.success(request, "Order unmarked as paid.")
            return redirect("control:order_detail", order_id=order.id)

        # ---------------------------
        # ASSIGN DELIVERY PERSON
        # ---------------------------
        elif action == "assign_delivery":
            delivery_id = request.POST.get("delivery_person")

            if not delivery_id:
                messages.error(request, "Select delivery person.")
                return redirect("control:order_detail", order_id=order.id)

            delivery_user = get_object_or_404(User, id=delivery_id)

            order.delivery_person = delivery_user
            order.status = "assigned"

            if not order.delivery_code:
                order.delivery_code = _generate_delivery_code()

            order.save(update_fields=["delivery_person", "status", "delivery_code"])

            messages.success(request, "Delivery assigned.")
            return redirect("control:order_detail", order_id=order.id)

        # ---------------------------
        # UPDATE DELIVERY STATUS
        # ---------------------------
        elif action == "delivery_status":
            new_status = (request.POST.get("status") or "").strip().lower()

            if new_status in ["picked_up", "on_the_way", "delivered"]:
                order.status = new_status
                order.save(update_fields=["status"])
                messages.success(request, "Delivery status updated.")

            return redirect("control:order_detail", order_id=order.id)

        # ---------------------------
        # ADMIN VERIFY DELIVERY
        # ---------------------------
        elif action == "verify_delivery":
            order.delivery_verified = True
            order.status = "delivered"
            order.save(update_fields=["delivery_verified", "status"])

            messages.success(request, "Delivery verified.")
            return redirect("control:order_detail", order_id=order.id)

    delivery_people = User.objects.filter(profile__is_delivery_guy=True)

    return render(request, "control/order_detail.html", {
        "order": order,
        "allowed_statuses": sorted(list(allowed_statuses)),
        "delivery_people": delivery_people,
    })


# =========================
# RIDER UPDATE STATUS (FIXED WITH BETTER HANDLING)
# =========================
@staff_required
def update_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # ensure rider owns order
    if order.delivery_person != request.user:
        messages.error(request, "Not your delivery.")
        return redirect("delivery:dashboard")

    if request.method == "POST":
        new_status = request.POST.get("status")
        
        # Debug: Log the current status and requested status
        print(f"Current status: {order.status}, Requested status: {new_status}")
        
        # Define valid status transitions
        valid_transitions = {
            "assigned": ["picked_up"],
            "picked_up": ["on_the_way"],
            "on_the_way": ["delivered"],
        }
        
        # Check if the transition is valid
        if new_status in valid_transitions.get(order.status, []):
            old_status = order.status
            order.status = new_status
            order.save(update_fields=["status"])
            
            # Add success message based on status
            if new_status == "picked_up":
                messages.success(request, f"Order #{order.id} picked up successfully!")
            elif new_status == "on_the_way":
                messages.success(request, f"Order #{order.id} is on the way!")
            elif new_status == "delivered":
                messages.success(request, f"Order #{order.id} delivered successfully!")
        else:
            # Provide more helpful error message
            if order.status == new_status:
                messages.error(request, f"Order #{order.id} is already {new_status.replace('_', ' ')}.")
            else:
                messages.error(request, f"Cannot change order #{order.id} from '{order.status.replace('_', ' ')}' to '{new_status.replace('_', ' ')}'.")
        
        return redirect("delivery:dashboard")
    
    messages.error(request, "Invalid request method.")
    return redirect("delivery:dashboard")


# =========================
# VERIFY DELIVERY CODE (RIDER)
# =========================
@staff_required
def verify_code(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.delivery_person != request.user:
        messages.error(request, "Not your delivery.")
        return redirect("delivery:dashboard")

    if request.method == "POST":
        code = request.POST.get("code")

        if not code:
            messages.error(request, "Please enter the delivery code.")
            return redirect("delivery:dashboard")
        
        if code != order.delivery_code:
            messages.error(request, f"Invalid delivery code. Expected: {order.delivery_code}")
            return redirect("delivery:dashboard")

        order.status = "delivered"
        order.delivery_verified = True
        order.save(update_fields=["status", "delivery_verified"])

        messages.success(request, f"Order #{order.id} delivery completed successfully!")
        return redirect("delivery:dashboard")
    
    messages.error(request, "Invalid request method.")
    return redirect("delivery:dashboard")


# =========================
# MENU MANAGEMENT
# =========================
@staff_required
def menu_list(request):
    q = (request.GET.get("q") or "").strip()
    show_archived = (request.GET.get("archived") or "").strip() == "1"

    foods = FoodItem.objects.select_related("category").order_by("name")
    categories = Category.objects.order_by("name")

    if not show_archived:
        foods = foods.filter(is_archived=False)

    if q:
        foods = foods.filter(
            Q(name__icontains=q) |
            Q(category__name__icontains=q)
        )

    paginator = Paginator(foods, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "control/menu_list.html", {
        "categories": categories,
        "page_obj": page_obj,
        "q": q,
        "show_archived": show_archived,
    })


@staff_required
def toggle_food_availability(request, food_id):
    if request.method == "POST":
        food = get_object_or_404(FoodItem, id=food_id)
        food.available = not food.available
        food.save(update_fields=["available"])
        messages.success(request, "Updated availability.")
    return redirect("control:menu_list")


@staff_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect("control:menu_list")
    return render(request, "control/category_form.html", {"form": form})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    form = CategoryForm(request.POST or None, instance=category)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Updated.")
        return redirect("control:menu_list")

    return render(request, "control/category_form.html", {"form": form})


@staff_required
def food_create(request):
    form = FoodItemForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Food created.")
        return redirect("control:menu_list")

    return render(request, "control/food_form.html", {"form": form})


@staff_required
def food_edit(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    form = FoodItemForm(request.POST or None, request.FILES or None, instance=food)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Food updated.")
        return redirect("control:menu_list")

    return render(request, "control/food_form.html", {"form": form})


# =========================
# WALLET TOPUPS
# =========================
def _credit_wallet_once(staff_user, topup) -> bool:
    if hasattr(topup, "transaction") and topup.transaction is not None:
        return False

    wallet, _ = Wallet.objects.get_or_create(user=topup.user)

    wallet.balance += topup.amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        tx_type="credit",
        source="topup",
        amount=topup.amount,
        topup=topup,
        note=f"Approved by {staff_user}",
    )
    return True


@staff_required
def topup_review(request, topup_id):
    topup = get_object_or_404(WalletTopUp, id=topup_id)

    if request.method == "POST":
        action = request.POST.get("action")

        with transaction.atomic():
            topup = WalletTopUp.objects.select_for_update().get(id=topup.id)

            if action == "approve":
                _credit_wallet_once(request.user, topup)
                topup.status = "approved"
            elif action == "reject":
                topup.status = "rejected"

            topup.reviewed_by = request.user
            topup.reviewed_at = timezone.now()
            topup.save()

        return redirect("control:topups_list")

    return render(request, "control/topup_review.html", {"topup": topup})


@staff_required
def wallet_transactions(request):
    txs = WalletTransaction.objects.select_related(
        "wallet", "wallet__user", "order", "topup"
    ).order_by("-created_at")[:400]

    return render(request, "control/transactions.html", {"txs": txs})