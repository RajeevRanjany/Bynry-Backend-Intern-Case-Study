# Part 2: Database Design

## Schema (SQL DDL)

```sql
-- Companies using the StockFlow platform
CREATE TABLE companies (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Warehouses belong to a company
CREATE TABLE warehouses (
    id          SERIAL PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    location    TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Suppliers are linked to a company
CREATE TABLE suppliers (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    contact_email   VARCHAR(255),
    contact_phone   VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Products (no warehouse_id here — that's in inventory)
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    supplier_id     INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    name            VARCHAR(255) NOT NULL,
    sku             VARCHAR(100) UNIQUE NOT NULL,
    description     TEXT,
    price           NUMERIC(12, 2) NOT NULL CHECK (price >= 0),
    product_type    VARCHAR(50) DEFAULT 'standard', -- 'standard' | 'bundle'
    low_stock_threshold INTEGER DEFAULT 10,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Inventory: tracks stock of a product in a specific warehouse
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (product_id, warehouse_id)  -- one record per product-warehouse pair
);

-- Inventory change log (audit trail)
CREATE TABLE inventory_logs (
    id              SERIAL PRIMARY KEY,
    inventory_id    INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    change_amount   INTEGER NOT NULL,         -- positive = stock in, negative = stock out
    reason          VARCHAR(100),             -- 'sale', 'restock', 'adjustment', etc.
    changed_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    changed_at      TIMESTAMP DEFAULT NOW()
);

-- Users belong to a company
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    role        VARCHAR(50) DEFAULT 'staff',  -- 'admin' | 'staff'
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Bundle products: a product can contain other products
CREATE TABLE bundle_items (
    id              SERIAL PRIMARY KEY,
    bundle_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    component_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity        INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    UNIQUE (bundle_id, component_id),
    CHECK (bundle_id != component_id)  -- a product can't bundle itself
);

-- Sales activity (used to determine "recent sales" for low-stock alerts)
CREATE TABLE sales (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    warehouse_id    INTEGER NOT NULL REFERENCES warehouses(id),
    product_id      INTEGER NOT NULL REFERENCES products(id),
    quantity_sold   INTEGER NOT NULL CHECK (quantity_sold > 0),
    sold_at         TIMESTAMP DEFAULT NOW()
);
```

---

## Indexes

```sql
-- Frequent lookups by company
CREATE INDEX idx_warehouses_company ON warehouses(company_id);
CREATE INDEX idx_products_company ON products(company_id);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_inventory_product ON inventory(product_id);
CREATE INDEX idx_sales_product_date ON sales(product_id, sold_at);
CREATE INDEX idx_sales_company ON sales(company_id);
CREATE INDEX idx_inventory_logs_inventory ON inventory_logs(inventory_id);
```

---

## Entity Relationships (Text ERD)

```
companies
  ├── warehouses (1:N)
  ├── products   (1:N)
  ├── suppliers  (1:N)
  └── users      (1:N)

products
  ├── inventory  (1:N) → links to warehouses (M:N via inventory)
  ├── bundle_items as bundle_id   (1:N)
  ├── bundle_items as component_id (1:N)
  └── sales      (1:N)

inventory
  └── inventory_logs (1:N)
```

---

## Design Decisions & Justifications

| Decision | Reason |
|---|---|
| `inventory` table as join between `products` and `warehouses` | Supports a product existing in multiple warehouses with different quantities |
| `sku` is UNIQUE globally | Business requirement — SKUs identify products platform-wide |
| `price` uses `NUMERIC(12,2)` | Avoids floating-point precision issues with money |
| `low_stock_threshold` on `products` | Threshold varies by product type as per business rules |
| `inventory_logs` as separate audit table | Tracks every change with reason and actor — needed for compliance and debugging |
| `bundle_items` self-referencing `products` | Clean way to model bundles without a separate products table |
| `sales` table | Required to determine "recent sales activity" for low-stock alerts |
| `CHECK (quantity >= 0)` on inventory | Prevents negative stock at DB level |

---

## Gaps & Questions for the Product Team

1. **Multi-tenancy / SKU scope:** Is SKU unique globally across all companies, or just within a company? (Currently modeled as global)

2. **Threshold definition:** What defines "low stock"? Is it a fixed number, a percentage of reorder quantity, or days-until-stockout?

3. **Recent sales window:** What counts as "recent" for sales activity? Last 7 days? 30 days? Configurable?

4. **Bundle stock calculation:** When a bundle is sold, does it deduct from component inventory? Who manages that logic?

5. **Supplier-product relationship:** Can a product have multiple suppliers? (Currently 1 supplier per product)

6. **Soft deletes:** Should products/warehouses be hard-deleted or archived? Deleting a product with sales history would lose data.

7. **User roles & permissions:** What can a `staff` user do vs an `admin`? Can staff create products?

8. **Currency:** Is price always in one currency, or do companies operate in multiple currencies?

9. **Reorder quantity:** Should the schema track a reorder quantity (how much to order when low)? Useful for the alert response.

10. **Warehouse capacity:** Do warehouses have a max capacity that inventory shouldn't exceed?
