import sqlite3
import pandas as pd
from datetime import datetime
import os
from config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create funds table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS funds (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL
    )
    """)
    
    # Create prices table (caching historical prices)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        fund_code TEXT,
        price_date TEXT,
        price REAL,
        PRIMARY KEY (fund_code, price_date)
    )
    """)
    
    # Create forecasts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund_code TEXT,
        forecast_date TEXT,
        target_date TEXT,
        predicted_return REAL,
        predicted_price REAL,
        actual_price REAL,
        accuracy_score REAL,
        is_evaluated INTEGER DEFAULT 0,
        FOREIGN KEY (fund_code) REFERENCES funds(code)
    )
    """)
    
    # Create news & sentiment table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund_code TEXT,
        title TEXT,
        url TEXT,
        published_date TEXT,
        sentiment_score REAL,
        sentiment_label TEXT,
        FOREIGN KEY (fund_code) REFERENCES funds(code)
    )
    """)
    
    conn.commit()
    conn.close()

def save_fund(code, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO funds (code, name)
    VALUES (?, ?)
    """, (code, name))
    conn.commit()
    conn.close()

def get_funds():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM funds")
    rows = cursor.fetchall()
    conn.close()
    return {row["code"]: row["name"] for row in rows}

def save_prices(df):
    """
    Saves price DataFrame. Needs columns: 'code', 'date', 'price'
    """
    if df.empty:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        # Ensure correct types and formatting
        try:
            date_str = str(row["date"])
            # Format datetime or timestamp to YYYY-MM-DD
            if " " in date_str:
                date_str = date_str.split(" ")[0]
            price_val = float(row["price"])
            fund_code = str(row["code"]).strip().upper()
            
            cursor.execute("""
            INSERT OR REPLACE INTO prices (fund_code, price_date, price)
            VALUES (?, ?, ?)
            """, (fund_code, date_str, price_val))
        except Exception as e:
            # Skip invalid rows silently or log
            continue
            
    conn.commit()
    conn.close()

def get_historical_prices(fund_code, start_date=None, end_date=None):
    """
    Returns historical prices as a pandas DataFrame sorted by date.
    """
    conn = get_db_connection()
    query = "SELECT price_date as date, price FROM prices WHERE fund_code = ?"
    params = [fund_code]
    
    if start_date:
        query += " AND price_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND price_date <= ?"
        params.append(end_date)
        
    query += " ORDER BY price_date ASC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # Format date column
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df

def get_latest_price_date(fund_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(price_date) as max_date FROM prices WHERE fund_code = ?", (fund_code,))
    row = cursor.fetchone()
    conn.close()
    return row["max_date"] if row and row["max_date"] else None

def save_forecast(fund_code, forecast_date, target_date, predicted_return, predicted_price):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if a forecast already exists for this fund on this forecast_date
    cursor.execute("""
    SELECT id FROM forecasts WHERE fund_code = ? AND forecast_date = ?
    """, (fund_code, forecast_date))
    row = cursor.fetchone()
    
    if row:
        # Update existing
        cursor.execute("""
        UPDATE forecasts 
        SET target_date = ?, predicted_return = ?, predicted_price = ?
        WHERE id = ?
        """, (target_date, predicted_return, predicted_price, row["id"]))
    else:
        # Insert new
        cursor.execute("""
        INSERT INTO forecasts (fund_code, forecast_date, target_date, predicted_return, predicted_price)
        VALUES (?, ?, ?, ?, ?)
        """, (fund_code, forecast_date, target_date, predicted_return, predicted_price))
        
    conn.commit()
    conn.close()

def get_pending_forecasts(today_str):
    """
    Returns forecasts where target_date <= today_str and is_evaluated = 0.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, fund_code, forecast_date, target_date, predicted_return, predicted_price
    FROM forecasts
    WHERE target_date <= ? AND is_evaluated = 0
    """, (today_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_forecast_evaluation(forecast_id, actual_price, accuracy_score):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE forecasts
    SET actual_price = ?, accuracy_score = ?, is_evaluated = 1
    WHERE id = ?
    """, (actual_price, accuracy_score, forecast_id))
    conn.commit()
    conn.close()

def get_fund_accuracy(fund_code):
    """
    Calculates overall success metric and returns average accuracy.
    Formula: average of accuracy_scores (100 - absolute percentage error).
    Also counts how many forecasts were evaluated.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COUNT(*) as total, AVG(accuracy_score) as avg_accuracy
    FROM forecasts
    WHERE fund_code = ? AND is_evaluated = 1
    """, (fund_code,))
    row = cursor.fetchone()
    conn.close()
    
    total = row["total"] if row else 0
    avg_accuracy = row["avg_accuracy"] if row and row["avg_accuracy"] is not None else None
    return {
        "total_evaluated": total,
        "avg_accuracy": avg_accuracy
    }

def get_all_forecasts(fund_code=None):
    conn = get_db_connection()
    if fund_code:
        query = "SELECT * FROM forecasts WHERE fund_code = ? ORDER BY forecast_date DESC"
        df = pd.read_sql_query(query, conn, params=[fund_code])
    else:
        query = "SELECT * FROM forecasts ORDER BY forecast_date DESC"
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def save_news_sentiment(fund_code, title, url, published_date, sentiment_score, sentiment_label):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check duplicate
    cursor.execute("""
    SELECT id FROM news_sentiment WHERE fund_code = ? AND title = ?
    """, (fund_code, title))
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("""
        INSERT INTO news_sentiment (fund_code, title, url, published_date, sentiment_score, sentiment_label)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (fund_code, title, url, published_date, sentiment_score, sentiment_label))
        conn.commit()
    conn.close()

def get_news_sentiment(fund_code, limit=10):
    conn = get_db_connection()
    query = """
    SELECT title, url, published_date, sentiment_score, sentiment_label
    FROM news_sentiment
    WHERE fund_code = ?
    ORDER BY published_date DESC, id DESC
    LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=[fund_code, limit])
    conn.close()
    return df
