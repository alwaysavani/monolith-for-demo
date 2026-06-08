from fulfillment_module.shipping_calculator import calculate_shipping

def resolve_checkout(order_id, weight, base_price):
    """Frontend Team endpoint."""
    final_price = calculate_shipping(weight, base_price)
    return {"status": "SUCCESS", "final_price": final_price}
