from billing_module.payment_gateway import process_payment

def calculate_shipping(weight, base_price):
    """Logistics Team logic."""
    total_with_tax = process_payment(base_price)
    shipping_cost = weight * 2.5
    return total_with_tax + shipping_cost
