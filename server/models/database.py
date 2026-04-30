import os
os.environ['SQLALCHEMY_WARN_20'] = '0'
os.environ['SQLALCHEMY_SILENCE_UBER_WARNING'] = '0'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

BASE = declarative_base()

db_url = os.getenv(
    'DATABASE_URL',
    "mysql+pymysql://root:Bb88710307@127.0.0.1:3306/tolerance_db?charset=utf8mb4"
)
engine = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)
