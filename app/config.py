import os
from dotenv import load_dotenv

load_dotenv()  # loads .env file automatically

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 'postgresql://stockflow:stockflow@localhost:5433/stockflow'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RECENT_SALES_DAYS = int(os.getenv('RECENT_SALES_DAYS', 30))
