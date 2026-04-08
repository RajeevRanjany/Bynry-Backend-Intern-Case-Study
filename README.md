# StockFlow — Inventory Management System
Bynry Backend Engineering Intern Case Study | Rajeev Ranjan Yadav

---

## Project Structure

```
├── app/
│   ├── __init__.py          
│   ├── app.py               
│   ├── config.py            
│   ├── models.py            
│   ├── routes/
│   │   ├── products.py     
│   │   └── alerts.py        
│   └── utils/
│       └── validators.py    
├── Part1_Code_Review.md     
├── Part2_Database_Design.md 
├── Part3_API_Implementation.md 
├── docker-compose.yml      
├── .env.example             
└── requirements.txt
```

---

## Prerequisites

- Python 3.10+
- Docker + Docker Compose

---

## Setup & Run

### 1. Clone the repository

```bash
git clone https://github.com/RajeevRanjany/Bynry-Backend-Intern-Case-Study.git
cd Bynry-Backend-Intern-Case-Study
```

### 2. Create `.env` file

```bash
cp .env.example .env
```

No changes needed : default values will work out of the box.

### 3. Start PostgreSQL with Docker

```bash
docker-compose up -d
```

Verify it's running:
```bash
docker ps
```

### 4. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Create database tables

```bash
python3 -c "from app import create_app, db; 
app = create_app(); 
app.app_context().push(); 
db.create_all()"
```

### 6. Seed test data (company + warehouse)

```bash
python3 -c "
from app import create_app, db
from app.models import Company, Warehouse
app = create_app()
with app.app_context():
    c = Company(name='Test Co', email='test@test.com')
    db.session.add(c)
    db.session.flush()
    w = Warehouse(name='Main Warehouse', company_id=c.id)
    db.session.add(w)
    db.session.commit()
    print(f'Company ID: {c.id}, Warehouse ID: {w.id}')
"
```

### 7. Run the Flask server

```bash
python3 -m flask --app app.app run --debug
```

Server runs at `http://localhost:5000`

---

## API Endpoints

### POST /api/products
Creates a new product with initial inventory in a single atomic transaction.

```bash
curl -X POST http://localhost:5000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Widget A",
    "sku": "WID-001",
    "price": 99.99,
    "warehouse_id": 1,
    "initial_quantity": 50
  }'
```

Response `201`:
```json
{"message": "Product created", "product_id": 1}
```

---

### GET /api/companies/{company_id}/alerts/low-stock
Returns low-stock alerts for products with recent sales activity.

```bash
curl http://localhost:5000/api/companies/1/alerts/low-stock
```

Response `200`:
```json
{
  "alerts": [
    {
      "product_id": 1,
      "product_name": "Widget A",
      "sku": "WID-001",
      "warehouse_id": 1,
      "warehouse_name": "Main Warehouse",
      "current_stock": 5,
      "threshold": 10,
      "days_until_stockout": 3,
      "supplier": {
        "id": 1,
        "name": "Supplier Corp",
        "contact_email": "orders@supplier.com"
      }
    }
  ],
  "total_alerts": 1
}
```

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid fields |
| 403 | Unauthorized company access |
| 404 | Warehouse not found |
| 409 | Duplicate SKU |
| 500 | Internal server error |

---

## Case Study Parts

| File | Description |
|------|-------------|
| `Part1_Code_Review.md` | 8 bugs identified in original code with fixes |
| `Part2_Database_Design.md` | Full SQL schema, indexes, design decisions, open questions |
| `Part3_API_Implementation.md` | Low-stock alert endpoint with edge case handling |

## Author
Rajeev Ranjan | MNNIT ALLAHABAD |