from decimal import Decimal, InvalidOperation


def validate_create_product(data: dict) -> tuple[dict | None, str | None]:
    """
    Validates the request body for POST /api/products.
    Returns (cleaned_data, error_message).
    If error_message is not None, the request should be rejected.
    """
    if not data:
        return None, "Request body is required"

    # Check required fields
    required = ['name', 'sku', 'price', 'warehouse_id']
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return None, f"Missing required fields: {missing}"

    # Validate price
    try:
        price = Decimal(str(data['price']))
        if price <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        return None, "Price must be a positive number"

    # Validate optional initial_quantity
    initial_quantity = data.get('initial_quantity', 0)
    if not isinstance(initial_quantity, int) or initial_quantity < 0:
        return None, "initial_quantity must be a non-negative integer"

    return {
        "name":             data['name'],
        "sku":              data['sku'],
        "price":            price,
        "warehouse_id":     data['warehouse_id'],
        "initial_quantity": initial_quantity,
        "description":      data.get('description'),
        "supplier_id":      data.get('supplier_id'),
    }, None
