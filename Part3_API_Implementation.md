# Part 3: API Implementation — Low Stock Alerts

## Endpoint
`GET /api/companies/{company_id}/alerts/low-stock`

---

## Assumptions Made (due to incomplete requirements)

1. "Recent sales activity" = at least 1 sale in the last 30 days (configurable via `RECENT_SALES_DAYS`)
2. Low stock threshold is stored per product in `products.low_stock_threshold`
3. `days_until_stockout` is calculated as: `current_stock / avg_daily_sales` (based on last 30 days)
4. A product is only alerted once per warehouse (not aggregated across warehouses)
5. Authentication is handled by middleware — `company_id` in the URL is validated against the logged-in user's company
6. A product with zero sales in the window is excluded (no recent activity = no alert)
7. If `avg_daily_sales` is 0 (but product has recent sales), `days_until_stockout` returns `null`

---

## Implementation

```python
from flask import Blueprint, jsonify, request, g
from sqlalchemy import text
from datetime import datetime, timedelta
from functools import wraps

alerts_bp = Blueprint('alerts', __name__)

RECENT_SALES_DAYS = 30  # configurable window for "recent sales activity"


def require_company_access(f):
    """
    Middleware: ensures the authenticated user belongs to the requested company.
    Assumes g.current_user is set by an auth middleware upstream.
    """
    @wraps(f)
    def decorated(company_id, *args, **kwargs):
        if not hasattr(g, 'current_user') or g.current_user.company_id != company_id:
            return jsonify({"error": "Unauthorized"}), 403
        return f(company_id, *args, **kwargs)
    return decorated


@alerts_bp.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
@require_company_access
def get_low_stock_alerts(company_id):
    """
    Returns low-stock alerts for all warehouses belonging to a company.

    A product triggers an alert when:
    - current stock <= product's low_stock_threshold
    - the product has had at least 1 sale in the last RECENT_SALES_DAYS days
    """

    since_date = datetime.utcnow() - timedelta(days=RECENT_SALES_DAYS)

    # Single optimized query using a CTE:
    # 1. recent_sales: aggregates sales per product/warehouse in the time window
    # 2. Joins inventory, products, warehouses, suppliers
    # 3. Filters to only low-stock items with recent activity
    query = text("""
        WITH recent_sales AS (
            SELECT
                product_id,
                warehouse_id,
                SUM(quantity_sold)                          AS total_sold,
                COUNT(*)                                    AS sale_count,
                -- avg daily sales over the window (used for days_until_stockout)
                ROUND(SUM(quantity_sold)::NUMERIC / :days, 4) AS avg_daily_sales
            FROM sales
            WHERE company_id = :company_id
              AND sold_at >= :since_date
            GROUP BY product_id, warehouse_id
        )
        SELECT
            p.id                AS product_id,
            p.name              AS product_name,
            p.sku               AS sku,
            w.id                AS warehouse_id,
            w.name              AS warehouse_name,
            i.quantity          AS current_stock,
            p.low_stock_threshold AS threshold,
            rs.avg_daily_sales  AS avg_daily_sales,
            s.id                AS supplier_id,
            s.name              AS supplier_name,
            s.contact_email     AS supplier_email
        FROM inventory i
        JOIN products    p  ON p.id = i.product_id
        JOIN warehouses  w  ON w.id = i.warehouse_id
        JOIN recent_sales rs ON rs.product_id = i.product_id
                             AND rs.warehouse_id = i.warehouse_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE w.company_id = :company_id
          AND i.quantity <= p.low_stock_threshold
        ORDER BY i.quantity ASC
    """)

    try:
        result = db.session.execute(query, {
            "company_id": company_id,
            "since_date": since_date,
            "days": RECENT_SALES_DAYS
        })
        rows = result.mappings().all()
    except Exception as e:
        # Log the error internally; don't expose DB details to client
        app.logger.error(f"Low stock query failed for company {company_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # Edge case: company exists but has no warehouses / no products
    if not rows:
        return jsonify({"alerts": [], "total_alerts": 0}), 200

    alerts = []
    for row in rows:
        # Calculate days_until_stockout safely (avoid division by zero)
        avg = float(row['avg_daily_sales']) if row['avg_daily_sales'] else 0
        if avg > 0:
            days_until_stockout = round(row['current_stock'] / avg)
        else:
            # Has recent sales but avg rounds to 0 — not enough data to predict
            days_until_stockout = None

        alert = {
            "product_id":         row['product_id'],
            "product_name":       row['product_name'],
            "sku":                row['sku'],
            "warehouse_id":       row['warehouse_id'],
            "warehouse_name":     row['warehouse_name'],
            "current_stock":      row['current_stock'],
            "threshold":          row['threshold'],
            "days_until_stockout": days_until_stockout,
            "supplier": {
                "id":            row['supplier_id'],
                "name":          row['supplier_name'],
                "contact_email": row['supplier_email']
            } if row['supplier_id'] else None
        }
        alerts.append(alert)

    return jsonify({
        "alerts":       alerts,
        "total_alerts": len(alerts)
    }), 200
```

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| Company has no warehouses | Returns `{"alerts": [], "total_alerts": 0}` |
| Product has no supplier | `supplier` field returns `null` instead of crashing |
| `avg_daily_sales` is 0 | `days_until_stockout` returns `null` safely |
| Unauthorized company access | 403 returned by `require_company_access` decorator |
| DB query failure | Caught, logged server-side, returns 500 without leaking DB info |
| Product above threshold | Excluded by `WHERE i.quantity <= p.low_stock_threshold` |
| No recent sales activity | Excluded by the `JOIN` with `recent_sales` CTE (inner join) |

---

## Approach & Design Notes

- Used a single SQL query with a CTE instead of multiple ORM calls — avoids N+1 queries and is more efficient at scale.
- `recent_sales` CTE pre-aggregates sales data so the main query stays clean.
- `days_until_stockout` is a simple linear projection — in production this could be improved with a moving average or ML model.
- The `require_company_access` decorator enforces that users can only see their own company's alerts — critical for B2B multi-tenancy.
- Supplier info is a `LEFT JOIN` so products without suppliers still appear in alerts.
- Results are ordered by `current_stock ASC` so the most critical items appear first.
