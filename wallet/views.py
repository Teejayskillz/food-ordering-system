from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db import transaction
from .models import Wallet, WalletTopUp, WalletTransaction


@login_required
def topup_create(request):
    # Ensure wallet exists (so balance can show on page)
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    if request.method == "POST":
        amount_raw = (request.POST.get("amount") or "").strip()
        reference = (request.POST.get("reference") or "").strip()
        proof = request.FILES.get("proof")

        # Validate amount
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            amount = Decimal("0")

        if amount <= 0:
            return render(request, "wallet/topup_create.html", {
                "wallet": wallet,
                "error": "Enter a valid amount.",
                "amount": amount_raw,
                "reference": reference,
            })

        if not proof:
            return render(request, "wallet/topup_create.html", {
                "wallet": wallet,
                "error": "Please upload a payment screenshot (proof).",
                "amount": amount_raw,
                "reference": reference,
            })

        # Create top-up request as pending
        WalletTopUp.objects.create(
            user=request.user,
            amount=amount,
            proof=proof,
            reference=reference,
            status="pending",
        )

        messages.success(request, "Top-up submitted. Waiting for admin approval.")
        return redirect("wallet:topup_create")

    return render(request, "wallet/topup_create.html", {"wallet": wallet})

@login_required
def dashboard(request):
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    transactions = wallet.transactions.select_related("order", "topup").order_by("-created_at")[:50]
    topups = WalletTopUp.objects.filter(user=request.user).order_by("-created_at")[:20]

    return render(request, "wallet/dashboard.html", {
        "wallet": wallet,
        "transactions": transactions,
        "topups": topups,
    })
