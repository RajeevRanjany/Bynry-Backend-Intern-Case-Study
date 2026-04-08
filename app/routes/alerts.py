from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, g, current_app
from sqlalchemy import text

from .. import db

alerts_bp = Blueprint('alerts', __name__)


def require_company_access(f):
    """
    Authorization decorator — ensures the logged-in user belongs to the
    requested company. Assumes g.current_user is set by upstream auth middleware.
    In a real app this would verify a JWT token.
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
    GET /api/companies/<company_id>/alerts/low-stock

    Returns products that are below their low_stock_threshold AND have had
    at least one sale in the last RECENT_SALES_DAYS days.

    Assumptions:
    - "Recent sales" window = 30 days (configurable via RECENT_SALES_DAYS env var)
    - Threshold is stored per product in products.low_stock_threshold
    - days_until_stockout = current_stock / avg_daily_sales (linear projection)
    - Products with no supplier return supplier: null (not an error)
    - Results ordered by current_stock ASC (most critical first)

    Design note: single CTE query instead of multiple ORM calls to avoid N+1.
    """
    days = current_app.config.get('RECENT_SALES_DAYS', 30)
    since_date = datetime.utcnow() - timedelta(days=days)

    query = text("""
        WITH recent_sales AS (
            -- Aggregate sales per product/warehouse within the time window.
            -- Products with zero sales in this window are excluded (inner join below).
            SELECT
                product_id,
                warehouse_id,
                SUM(quantity_sold)                              AS total_sold,
                ROUND(SUM(quantity_sold)::NUMERIC / :days, 4)  AS avg_daily_sales
            FROM sales
            WHERE company_id = :company_id
              AND sold_at    >= :since_date
            GROUP BY product_id, warehouse_id
        )
        SELECT
            p.id                  AS product_id,
            p.name                AS product_name,
            p.sku                 AS sku,
            w.id                  AS warehouse_id,
            w.name                AS warehouse_name,
            i.quantity            AS current_stock,
            p.low_stock_threshold AS threshold,
            rs.avg_daily_sales    AS avg_daily_sales,
            s.id                  AS supplier_id,
            s.name                AS supplier_name,
            s.contact_email       AS supplier_email
        FROM inventory i
        JOIN products     p  ON p.id  = i.product_id
        JOIN warehouses   w  ON w.id  = i.warehouse_id
        JOIN recent_sales rs ON rs.product_id   = i.product_id
                             AND rs.warehouse_id = i.warehouse_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE w.company_id        = :company_id
          AND i.quantity         <= p.low_stock_threshold
        ORDER BY i.quantity ASC
    """)

    try:
        rows = db.session.execute(query, {
            "company_id": company_id,
            "since_date": since_date,
            "days":       days,
        }).mappings().all()
    except Exception as e:
        current_app.logger.error(f"low_stock_alerts query failed (company={company_id}): {e}")
        return jsonify({"error": "Internal server error"}), 500

    alerts = [_build_alert(row) for row in rows]
    return jsonify({"alerts": alerts, "total_alerts": len(alerts)}), 200


def _build_alert(row) -> dict:
    """Converts a DB row into the alert response shape."""
    avg = float(row['avg_daily_sales']) if row['avg_daily_sales'] else 0

    # Avoid division by zero; return null if we can't project stockout date
    days_until_stockout = round(row['current_stock'] / avg) if avg > 0 else None

    return {
        "product_id":          row['product_id'],
        "product_name":        row['product_name'],
        "sku":                 row['sku'],
        "warehouse_id":        row['warehouse_id'],
        "warehouse_name":      row['warehouse_name'],
        "current_stock":       row['current_stock'],
        "threshold":           row['threshold'],
        "days_until_stockout": days_until_stockout,
        "supplier": {
            "id":            row['supplier_id'],
            "name":          row['supplier_name'],
            "contact_email": row['supplier_email'],
        } if row['supplier_id'] else None,
    }
