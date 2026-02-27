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


def staff_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.is_staff,
        login_url="accounts:login"
    )(view_func)

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



# ---------------------------
# DASHBOARD

@staff_required
def dashboard(request):
    today = timezone.localdate()
    last_7 = timezone.now() - timedelta(days=7)

    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status="pending").count()
    preparing_orders = Order.objects.filter(status="preparing").count()
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

    # Top selling foods (by qty) based on OrderItem
    top_foods = (
        OrderItem.objects.select_related("food")
        .values("food__name")
        .annotate(qty=Coalesce(Sum("quantity"), 0))
        .order_by("-qty")[:5]
    )

    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:8]
    recent_topups = (
        WalletTopUp.objects.select_related("user", "reviewed_by")
        .order_by("-created_at")[:8]
    )

    context = {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "preparing_orders": preparing_orders,
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
    }
    return render(request, "control/dashboard.html", context)


# ---------------------------
# ORDERS (list + detail + status update)
# ---------------------------
@staff_required
def orders_list(request):
    status = (request.GET.get("status") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()

    qs = Order.objects.select_related("user").order_by("-created_at")

    allowed_statuses = {"pending", "preparing", "delivered", "cancelled"}
    if status in allowed_statuses:
        qs = qs.filter(status=status)

    if q:
        # Search by order id, username/email, phone
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(phone__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "control/orders_list.html", {
        "page_obj": page_obj,
        "status": status,
        "q": q,
        "allowed_statuses": sorted(list(allowed_statuses)),
    })

def _wallet_debit_for_order_once(staff_user, order) -> bool:
    """
    Debit customer's wallet for this order exactly once.
    Returns True if debited now, False if already debited before.
    """
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

    wallet.balance = wallet.balance - order.total_amount
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


@staff_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__food"),
        id=order_id
    )
    allowed_statuses = {"pending", "preparing", "delivered", "cancelled"}

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        # 1) Update status
        if action == "update_status":
            new_status = (request.POST.get("status") or "").strip().lower()
            if new_status not in allowed_statuses:
                messages.error(request, "Invalid status.")
            else:
                order.status = new_status
                order.save(update_fields=["status"])
                messages.success(request, "Order status updated.")
                return redirect("control:order_detail", order_id=order.id)

        # 3) Mark as paid (COD just marks paid; WALLET debits then marks paid)
        elif action == "mark_paid":
            if order.is_paid:
                messages.warning(request, "This order is already marked as paid.")
                return redirect("control:order_detail", order_id=order.id)

            with transaction.atomic():
                # lock order row
                order = Order.objects.select_for_update().get(id=order.id)

                if order.is_paid:
                    messages.warning(request, "This order is already marked as paid.")
                    return redirect("control:order_detail", order_id=order.id)

                if order.payment_method == "wallet":
                    try:
                        debited_now = _wallet_debit_for_order_once(request.user, order)
                    except ValueError as e:
                        messages.error(request, str(e))
                        return redirect("control:order_detail", order_id=order.id)

                    order.is_paid = True
                    order.save(update_fields=["is_paid"])

                    if debited_now:
                        messages.success(request, "Wallet debited and order marked as paid.")
                    else:
                        messages.success(request, "Order marked as paid (wallet already debited).")

                else:
                    # COD (or anything else): just mark paid
                    order.is_paid = True
                    order.save(update_fields=["is_paid"])
                    messages.success(request, "Order marked as paid.")
                return redirect("control:order_detail", order_id=order.id)

        # Optional: unmark paid (careful, we won't auto-refund)
        elif action == "unmark_paid":
            if not order.is_paid:
                messages.warning(request, "This order is not marked as paid.")
            else:
                order.is_paid = False
                order.save(update_fields=["is_paid"])
                messages.success(request, "Order unmarked as paid. (No wallet refund was done.)")
            return redirect("control:order_detail", order_id=order.id)

    return render(request, "control/order_detail.html", {
        "order": order,
        "allowed_statuses": sorted(list(allowed_statuses)),
    })


# ---------------------------
# (2) MENU MANAGEMENT
# ---------------------------
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
    if request.method != "POST":
        return redirect("control:menu_list")

    food = get_object_or_404(FoodItem, id=food_id)
    food.available = not food.available
    food.save(update_fields=["available"])
    messages.success(request, f"Availability updated for: {food.name}")
    return redirect("control:menu_list")


@staff_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect("control:menu_list")
    return render(request, "control/category_form.html", {"form": form, "mode": "create"})


@staff_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category updated.")
        return redirect("control:menu_list")
    return render(request, "control/category_form.html", {"form": form, "mode": "edit", "category": category})


@staff_required
def food_create(request):
    form = FoodItemForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Food item created.")
        return redirect("control:menu_list")
    return render(request, "control/food_form.html", {"form": form, "mode": "create"})


@staff_required
def food_edit(request, food_id):
    food = get_object_or_404(FoodItem, id=food_id)
    form = FoodItemForm(request.POST or None, request.FILES or None, instance=food)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Food item updated.")
        return redirect("control:menu_list")
    return render(request, "control/food_form.html", {"form": form, "mode": "edit", "food": food})


# ---------------------------
# (1) WALLET TOPUPS REVIEW + TRANSACTIONS
# ---------------------------
def _credit_wallet_once(staff_user, topup) -> bool:
    """
    Credit wallet for this topup exactly once.
    Returns True if credited now, False if already credited.
    """
    if hasattr(topup, "transaction") and topup.transaction is not None:
        return False

    wallet, _ = Wallet.objects.get_or_create(user=topup.user)

    wallet.balance = wallet.balance + topup.amount
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
def topups_list(request):
    status = (request.GET.get("status") or "").strip().lower()

    qs = WalletTopUp.objects.select_related("user", "reviewed_by").order_by("-created_at")
    allowed = {"pending", "approved", "rejected"}
    if status in allowed:
        qs = qs.filter(status=status)

    topups = qs[:250]
    return render(request, "control/topups_list.html", {"topups": topups, "status": status})


@staff_required
def topup_review(request, topup_id):
    topup = get_object_or_404(
        WalletTopUp.objects.select_related("user", "reviewed_by"),
        id=topup_id
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        note = (request.POST.get("admin_note") or "").strip()

        with transaction.atomic():
            topup = WalletTopUp.objects.select_for_update().select_related("user").get(id=topup.id)

            if topup.status != "pending":
                messages.warning(request, "This top-up has already been reviewed.")
                return redirect("control:topup_review", topup_id=topup.id)

            if action == "approve":
                credited_now = _credit_wallet_once(request.user, topup)

                topup.status = "approved"
                topup.reviewed_by = request.user
                topup.reviewed_at = timezone.now()
                topup.admin_note = note
                topup.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

                messages.success(
                    request,
                    "Top-up approved and wallet credited." if credited_now else "Top-up approved (already credited)."
                )
                return redirect("control:topups_list")

            if action == "reject":
                topup.status = "rejected"
                topup.reviewed_by = request.user
                topup.reviewed_at = timezone.now()
                topup.admin_note = note or "Rejected by admin."
                topup.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

                messages.success(request, "Top-up rejected.")
                return redirect("control:topups_list")

            messages.error(request, "Invalid action.")

    return render(request, "control/topup_review.html", {"topup": topup})


@staff_required
def wallet_transactions(request):
    txs = WalletTransaction.objects.select_related(
        "wallet", "wallet__user", "order", "topup"
    ).order_by("-created_at")[:400]
    return render(request, "control/transactions.html", {"txs": txs})