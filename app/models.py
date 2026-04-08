from datetime import datetime
from . import db


class Company(db.Model):
    __tablename__ = 'companies'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(255), nullable=False)
    email      = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Warehouse(db.Model):
    __tablename__ = 'warehouses'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name       = db.Column(db.String(255), nullable=False)
    location   = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    name          = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255))
    contact_phone = db.Column(db.String(50))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


class Product(db.Model):
    __tablename__ = 'products'

    id                  = db.Column(db.Integer, primary_key=True)
    company_id          = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    supplier_id         = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    name                = db.Column(db.String(255), nullable=False)
    sku                 = db.Column(db.String(100), unique=True, nullable=False)
    description         = db.Column(db.Text)
    price               = db.Column(db.Numeric(12, 2), nullable=False)
    product_type        = db.Column(db.String(50), default='standard')  # 'standard' | 'bundle'
    low_stock_threshold = db.Column(db.Integer, default=10)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Inventory(db.Model):
    __tablename__ = 'inventory'
    __table_args__ = (db.UniqueConstraint('product_id', 'warehouse_id'),)

    id           = db.Column(db.Integer, primary_key=True)
    product_id   = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    quantity     = db.Column(db.Integer, nullable=False, default=0)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Sale(db.Model):
    __tablename__ = 'sales'

    id            = db.Column(db.Integer, primary_key=True)
    company_id    = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    warehouse_id  = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    product_id    = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    sold_at       = db.Column(db.DateTime, default=datetime.utcnow)
