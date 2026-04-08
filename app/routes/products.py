from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import Product, Inventory, Warehouse
from ..utils.validators import validate_create_product

products_bp = Blueprint('products', __name__)


@products_bp.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json()
    cleaned, error = validate_create_product(data)

    if error:
        return jsonify({"error": error}), 400

    warehouse = Warehouse.query.get(cleaned['warehouse_id'])
    if not warehouse:
        return jsonify({"error": "Warehouse not found"}), 404

    if Product.query.filter_by(sku=cleaned['sku']).first():
        return jsonify({"error": "A product with this SKU already exists"}), 409

    try:
        product = Product(
            name=cleaned['name'],
            sku=cleaned['sku'],
            price=cleaned['price'],
            description=cleaned['description'],
            supplier_id=cleaned['supplier_id'],
            company_id=warehouse.company_id,
        )
        db.session.add(product)
        db.session.flush()

        inventory = Inventory(
            product_id=product.id,
            warehouse_id=cleaned['warehouse_id'],
            quantity=cleaned['initial_quantity'],
        )
        db.session.add(inventory)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Database integrity error"}), 409
    except Exception as e:
        db.session.rollback()
        from flask import current_app
        current_app.logger.error(f"create_product error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"message": "Product created", "product_id": product.id}), 201
