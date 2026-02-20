from decimal import Decimal
from .models import Wallet

def wallet_context(request):
    if not request.user.is_authenticated:
        return {"wallet_balance": Decimal("0.00")}

    wallet = Wallet.objects.filter(user=request.user).first()
    return {"wallet_balance": wallet.balance if wallet else Decimal("0.00")}
