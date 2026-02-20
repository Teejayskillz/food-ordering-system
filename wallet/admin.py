from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from .models import Wallet, WalletTopUp, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "updated_at")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user",)


@admin.register(WalletTopUp)
class WalletTopUpAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "status", "created_at", "reviewed_at", "reference")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "reference")
    list_select_related = ("user", "reviewed_by")
    readonly_fields = ("created_at", "reviewed_by", "reviewed_at")

    actions = ["approve_topups", "reject_topups"]

    def _credit_wallet_once(self, request, topup) -> bool:
        """
        Credit wallet for this topup exactly once.
        Returns True if credited now, False if already credited.
        """
        # OneToOne: if exists, it was already credited
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
            note=f"Approved by {request.user}",
        )
        return True

    @admin.action(description="Approve selected top-ups (credit wallet)")
    def approve_topups(self, request, queryset):
        pending = queryset.filter(status="pending")

        if not pending.exists():
            self.message_user(request, "No pending top-ups selected.", level=messages.WARNING)
            return

        credited_count = 0
        skipped_already_done = 0

        with transaction.atomic():
            for topup in pending.select_for_update().select_related("user"):
                # Extra safety
                if topup.status != "pending":
                    skipped_already_done += 1
                    continue

                if self._credit_wallet_once(request, topup):
                    credited_count += 1
                else:
                    skipped_already_done += 1

                topup.status = "approved"
                topup.reviewed_by = request.user
                topup.reviewed_at = timezone.now()
                # keep any existing note; don't overwrite
                topup.admin_note = (topup.admin_note or "").strip()
                topup.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

        msg = f"Approved {credited_count} top-up(s)."
        if skipped_already_done:
            msg += f" Skipped {skipped_already_done} (already reviewed/credited)."
        self.message_user(request, msg, level=messages.SUCCESS)

    @admin.action(description="Reject selected top-ups")
    def reject_topups(self, request, queryset):
        pending = queryset.filter(status="pending")

        if not pending.exists():
            self.message_user(request, "No pending top-ups selected.", level=messages.WARNING)
            return

        rejected_count = 0

        with transaction.atomic():
            for topup in pending.select_for_update().select_related("user"):
                if topup.status != "pending":
                    continue

                topup.status = "rejected"
                topup.reviewed_by = request.user
                topup.reviewed_at = timezone.now()
                if not (topup.admin_note or "").strip():
                    topup.admin_note = "Rejected by admin."
                topup.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note"])

                rejected_count += 1

        self.message_user(request, f"Rejected {rejected_count} top-up(s).", level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        """
        ✅ Makes 'approve from inside the top-up detail page' work:
        If status changes to approved, credit wallet once.
        """
        old_status = None
        if change and obj.pk:
            old_status = WalletTopUp.objects.filter(pk=obj.pk).values_list("status", flat=True).first()

        with transaction.atomic():
            super().save_model(request, obj, form, change)

            # If status moved to approved, credit (once)
            if obj.status == "approved" and old_status != "approved":
                if not obj.reviewed_by:
                    obj.reviewed_by = request.user
                if not obj.reviewed_at:
                    obj.reviewed_at = timezone.now()
                obj.save(update_fields=["reviewed_by", "reviewed_at"])

                self._credit_wallet_once(request, obj)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "tx_type", "source", "amount", "created_at", "order", "topup")
    list_filter = ("tx_type", "source", "created_at")
    search_fields = ("wallet__user__username", "wallet__user__email")
    list_select_related = ("wallet", "wallet__user", "order", "topup")
