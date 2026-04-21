# db.py

import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        mq135 INTEGER,
        mq2 INTEGER,
        mq4 INTEGER,
        temp FLOAT,
        hum FLOAT
    );
    """)

    conn.commit()
    conn.close()