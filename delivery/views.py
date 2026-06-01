from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order


# ---------------------------
# DELIVERY DASHBOARD
# ---------------------------
@login_required
def delivery_dashboard(request):
    user = request.user

    orders = Order.objects.filter(
        delivery_person=user
    ).order_by("-created_at")

    assigned = orders.filter(status="assigned")
    picked_up = orders.filter(status="picked_up")
    on_the_way = orders.filter(status="on_the_way")
    delivered = orders.filter(status="delivered")

    today = timezone.localdate()
    today_delivered = orders.filter(
        status="delivered",
        created_at__date=today
    )

    return render(request, "delivery/dashboard.html", {
        "orders": orders,
        "assigned": assigned,
        "picked_up": picked_up,
        "on_the_way": on_the_way,
        "delivered": delivered,
        "today_delivered": today_delivered,
        "total_assigned": orders.count(),
    })


# ---------------------------
# UPDATE DELIVERY STATUS (STEP FLOW)
# ---------------------------
@login_required
@require_POST
def update_delivery_status(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        delivery_person=request.user
    )

    action = request.POST.get("action")

    # STEP 1 → picked up
    if action == "picked_up":
        if order.status != "assigned":
            messages.error(request, "Order not ready for pickup.")
            return redirect("delivery:dashboard")

        order.status = "picked_up"
        order.save(update_fields=["status"])
        messages.success(request, "Order picked up.")

    # STEP 2 → on the way
    elif action == "on_the_way":
        if order.status != "picked_up":
            messages.error(request, "You must pick up first.")
            return redirect("delivery:dashboard")

        order.status = "on_the_way"
        order.save(update_fields=["status"])
        messages.success(request, "Order is now on the way.")

    else:
        messages.error(request, "Invalid action.")

    return redirect("delivery:dashboard")


# ---------------------------
# VERIFY DELIVERY CODE (FINAL STEP)
# ---------------------------
@login_required
@require_POST
def verify_delivery_code(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        delivery_person=request.user
    )

    code = request.POST.get("code")

    if order.status != "on_the_way":
        messages.error(request, "Order is not out for delivery yet.")
        return redirect("delivery:dashboard")

    if code != order.delivery_code:
        messages.error(request, "Invalid delivery code.")
        return redirect("delivery:dashboard")

    order.status = "delivered"
    order.delivery_verified = True
    order.save(update_fields=["status", "delivery_verified"])

    messages.success(request, "Delivery completed successfully.")
    return redirect("delivery:dashboard")