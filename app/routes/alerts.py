from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, g, current_app
from sqlalchemy import text

from .. import db

alerts_bp = Blueprint('alerts', __name__)


def require_company_access(f):
    @wraps(f)
    def decorated(company_id, *args, **kwargs):
        # TODO: verify JWT token in production
        return f(company_id, *args, **kwargs)
    return decorated


@alerts_bp.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
@require_company_access
def get_low_stock_alerts(company_id):
    days = current_app.config.get('RECENT_SALES_DAYS', 30)
    since_date = datetime.utcnow() - timedelta(days=days)

    query = text("""
        WITH recent_sales AS (
            SELECT
                product_id,
                warehouse_id,
                SUM(quantity_sold) AS total_sold,
                ROUND(SUM(quantity_sold)::NUMERIC / :days, 4) AS avg_daily_sales
            FROM sales
            WHERE company_id = :company_id
              AND sold_at >= :since_date
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
        JOIN recent_sales rs ON rs.product_id = i.product_id
                             AND rs.warehouse_id = i.warehouse_id
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        WHERE w.company_id = :company_id
          AND i.quantity  <= p.low_stock_threshold
        ORDER BY i.quantity ASC
    """)

    try:
        rows = db.session.execute(query, {
            "company_id": company_id,
            "since_date": since_date,
            "days": days,
        }).mappings().all()
    except Exception as e:
        current_app.logger.error(f"low_stock_alerts error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    alerts = [_build_alert(row) for row in rows]
    return jsonify({"alerts": alerts, "total_alerts": len(alerts)}), 200


def _build_alert(row) -> dict:
    avg = float(row['avg_daily_sales']) if row['avg_daily_sales'] else 0
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
