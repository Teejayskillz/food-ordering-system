from django.conf import settings
from django.db import models
from django.utils import timezone

class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wallet: {self.user} - ₦{self.balance}"


class WalletTopUp(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_topups",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    proof = models.ImageField(upload_to="wallet_proofs/")
    reference = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_wallet_topups",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)

    def __str__(self):
        return f"TopUp #{self.id} - {self.user} - ₦{self.amount} ({self.status})"


class WalletTransaction(models.Model):
    TYPE_CHOICES = [("credit", "Credit"), ("debit", "Debit")]
    SOURCE_CHOICES = [("topup", "Top up"), ("order", "Order payment"), ("adjustment", "Adjustment")]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    tx_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL)


    topup = models.OneToOneField(
        WalletTopUp,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="transaction",
    )

    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.wallet.user} {self.tx_type} ₦{self.amount} ({self.source})"
