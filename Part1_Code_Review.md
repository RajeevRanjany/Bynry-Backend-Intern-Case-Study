# Part 1: Code Review & Debugging

## Original Code

```python
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json

    # Create new product
    product = Product(
        name=data['name'],
        sku=data['sku'],
        price=data['price'],
        warehouse_id=data['warehouse_id']
    )
    db.session.add(product)
    db.session.commit()

    # Update inventory count
    inventory = Inventory(
        product_id=product.id,
        warehouse_id=data['warehouse_id'],
        quantity=data['initial_quantity']
    )
    db.session.add(inventory)
    db.session.commit()

    return {"message": "Product created", "product_id": product.id}
```

---

## Issues Identified

### 1. No Input Validation
**Problem:** `data['name']`, `data['sku']`, etc. are accessed directly without checking if they exist or are valid.  
**Impact:** If any required field is missing, Python raises a `KeyError` and the server returns a 500 Internal Server Error instead of a meaningful 400 Bad Request. A client sending `{}` would crash the endpoint.

---

### 2. No SKU Uniqueness Check
**Problem:** There's no check to ensure the SKU is unique before inserting.  
**Impact:** If the database has a unique constraint on `sku`, the commit will throw an `IntegrityError` and crash without a clean error response. If there's no DB constraint either, duplicate SKUs get silently inserted — breaking product lookups across the platform.

---

### 3. Two Separate `db.session.commit()` Calls (Non-Atomic Transaction)
**Problem:** The product is committed first, then the inventory record is committed separately.  
**Impact:** If the second commit fails (e.g., `initial_quantity` is missing or invalid), the product exists in the DB but has no inventory record — a partial/corrupt state. This is a classic atomicity violation.

---

### 4. `warehouse_id` Stored on the Product Model
**Problem:** `warehouse_id` is set directly on the `Product` object. But the requirements say a product can exist in multiple warehouses.  
**Impact:** This design breaks multi-warehouse support. A product is tied to one warehouse at creation, making it impossible to track the same product across different warehouses without duplicating the product record.

---

### 5. No Handling for Optional Fields
**Problem:** Fields like `initial_quantity` are accessed with `data['initial_quantity']` — no default fallback.  
**Impact:** If a caller doesn't send `initial_quantity`, the code crashes. Some fields should be optional with sensible defaults (e.g., `quantity=0`).

---

### 6. Price Not Validated as Decimal/Positive
**Problem:** `price=data['price']` is passed as-is with no type check or range validation.  
**Impact:** A negative price, zero, or a string like `"free"` could be stored in the database, causing downstream billing or display bugs.

---

### 7. No HTTP Status Codes on Response
**Problem:** The success response returns `200 OK` by default. No explicit status codes are set for error cases.  
**Impact:** Clients can't reliably distinguish success from failure. REST best practice is `201 Created` for resource creation.

---

### 8. No Authentication / Authorization Check
**Problem:** Any caller can create a product with any `warehouse_id`.  
**Impact:** A user from Company A could add products to Company B's warehouse. In a B2B SaaS context this is a serious security issue.

---

## Fixed Version

```python
from flask import request, jsonify
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()

    # 1. Validate request body exists
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # 2. Validate required fields
    required_fields = ['name', 'sku', 'price', 'warehouse_id']
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    # 3. Validate price is a positive decimal
    try:
        price = Decimal(str(data['price']))
        if price <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        return jsonify({"error": "Price must be a positive number"}), 400

    # 4. Optional field with default
    initial_quantity = data.get('initial_quantity', 0)
    if not isinstance(initial_quantity, int) or initial_quantity < 0:
        return jsonify({"error": "initial_quantity must be a non-negative integer"}), 400

    # 5. Check SKU uniqueness before insert
    if Product.query.filter_by(sku=data['sku']).first():
        return jsonify({"error": "SKU already exists"}), 409

    # 6. Check warehouse exists (and optionally belongs to the authenticated company)
    warehouse = Warehouse.query.get(data['warehouse_id'])
    if not warehouse:
        return jsonify({"error": "Warehouse not found"}), 404

    try:
        # 7. Single atomic transaction — both records commit together or not at all
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price
            # warehouse_id removed from Product — product-warehouse relationship
            # is managed through the Inventory table to support multi-warehouse
        )
        db.session.add(product)
        db.session.flush()  # get product.id without committing yet

        inventory = Inventory(
            product_id=product.id,
            warehouse_id=data['warehouse_id'],
            quantity=initial_quantity
        )
        db.session.add(inventory)

        db.session.commit()  # single commit — atomic

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Database integrity error, possibly duplicate SKU"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"message": "Product created", "product_id": product.id}), 201
```

---

## Summary of Fixes

| Issue | Fix Applied |
|---|---|
| No input validation | Added required field checks and type validation |
| No SKU uniqueness check | Query before insert + handle IntegrityError |
| Two separate commits | Used `flush()` + single `commit()` for atomicity |
| `warehouse_id` on Product | Removed — relationship handled via Inventory table |
| Optional fields crash | Used `data.get()` with defaults |
| Price not validated | Validated as positive Decimal |
| No status codes | Returns `201` on success, `400/404/409/500` on errors |
| No auth check | Noted as assumption; warehouse ownership should be verified against authenticated user's company |
