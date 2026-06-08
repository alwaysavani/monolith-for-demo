from core_infra.feature_flags import is_legacy_billing_enabled

def process_payment(amount):
    """Billing Team logic."""
    if is_legacy_billing_enabled():
        return amount * 1.05  # legacy tax
    return amount * 1.02
