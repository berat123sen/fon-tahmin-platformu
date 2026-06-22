import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import database
from config import DEFAULT_FUNDS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Forecaster:
    def __init__(self):
        pass

    def run_backtesting(self):
        """
        Scans all pending forecasts (where target_date <= today) and checks if actual price is available.
        Updates accuracy scores in SQLite database.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Running backtest evaluation for date: {today_str}")
        
        pending = database.get_pending_forecasts(today_str)
        logger.info(f"Found {len(pending)} pending forecasts to evaluate.")
        
        for f in pending:
            forecast_id = f["id"]
            fund_code = f["fund_code"]
            target_date_str = f["target_date"]
            predicted_price = f["predicted_price"]
            
            # Fetch actual price from DB. 
            # Note: Mutual fund prices don't update on weekends, so if target_date is a weekend/holiday,
            # we look for the closest price date available on or after the target_date.
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            SELECT price, price_date FROM prices 
            WHERE fund_code = ? AND price_date >= ?
            ORDER BY price_date ASC LIMIT 1
            """, (fund_code, target_date_str))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                actual_price = float(row["price"])
                actual_date = row["price_date"]
                
                # Calculate accuracy percentage: 100 - absolute percentage error
                percentage_error = abs(predicted_price - actual_price) / actual_price
                accuracy = max(0.0, 100.0 - (percentage_error * 100.0))
                
                # Update DB
                database.update_forecast_evaluation(forecast_id, actual_price, round(accuracy, 2))
                logger.info(f"Evaluated forecast #{forecast_id} for {fund_code}: "
                            f"Pred Price: {predicted_price:.4f}, Actual Price: {actual_price:.4f} (on {actual_date}), "
                            f"Accuracy: {accuracy:.2f}%")
            else:
                logger.info(f"Actual price not yet available for {fund_code} on/after {target_date_str}")

    def generate_2_week_forecast(self, fund_code):
        """
        Generates 14-day forecasts for a fund code using price trends and news sentiment analysis.
        Saves the forecast to DB and returns a dictionary of results.
        """
        fund_code = fund_code.strip().upper()
        
        # Fetch last 30 days of prices from DB
        df_hist = database.get_historical_prices(fund_code)
        if df_hist.empty or len(df_hist) < 3:
            logger.warning(f"Insufficient price history to forecast {fund_code}.")
            return None
            
        # Get latest price and date
        latest_row = df_hist.iloc[-1]
        latest_price = float(latest_row["price"])
        latest_date = latest_row["date"] # pandas Timestamp
        latest_date_str = latest_date.strftime("%Y-%m-%d")
        
        # 1. Quantitative Trend (WMA of recent returns)
        # Calculate daily percentage returns
        df_hist["return"] = df_hist["price"].pct_change()
        df_clean = df_hist.dropna().copy()
        
        # Weight recent returns more heavily (exponential weighting)
        returns = df_clean["return"].values
        n = len(returns)
        if n > 0:
            weights = np.exp(np.linspace(-1, 0, n)) # exponentially increasing weights
            weights /= weights.sum()
            trend_drift = np.sum(returns * weights)
        else:
            trend_drift = 0.0
            
        # Limit extreme drift values to keep predictions realistic
        trend_drift = max(-0.02, min(0.02, trend_drift))
        
        # 2. News Sentiment Impact
        df_news = database.get_news_sentiment(fund_code, limit=5)
        sentiment_score_avg = 0.0
        if not df_news.empty:
            sentiment_score_avg = df_news["sentiment_score"].mean()
            
        # Sentiment adjustment factor: 0.15% return shift per 1.0 sentiment score
        sentiment_adj = sentiment_score_avg * 0.0015
        
        # Combined Daily Expected Return
        expected_daily_return = trend_drift + sentiment_adj
        
        # 3. Project 14 calendar days into the future
        forecast_dates = []
        forecast_prices = []
        
        curr_date = latest_date
        curr_price = latest_price
        
        for day in range(1, 15):
            curr_date = curr_date + timedelta(days=1)
            # Weekend filter or keep calendar days?
            # For drawing continuous predictions we keep all days, but use lower volatility compounding
            # If weekend, we simulate zero drift or small random walk
            if curr_date.weekday() >= 5:
                # Weekend: price stays same as last Friday, or tiny weekend noise
                curr_price = curr_price # stays constant
            else:
                curr_price = curr_price * (1.0 + expected_daily_return)
                
            forecast_dates.append(curr_date)
            forecast_prices.append(round(curr_price, 6))
            
        # Calculate 2-week (14 days) forecasted return percentage
        final_predicted_price = forecast_prices[-1]
        predicted_return = ((final_predicted_price - latest_price) / latest_price) * 100.0
        
        # Target date is 14 days after latest price date
        target_date = latest_date + timedelta(days=14)
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        # Save forecast to database
        database.save_forecast(
            fund_code=fund_code,
            forecast_date=latest_date_str,
            target_date=target_date_str,
            predicted_return=round(predicted_return, 2),
            predicted_price=round(final_predicted_price, 6)
        )
        
        # Create forecast dataframe
        df_forecast = pd.DataFrame({
            "date": forecast_dates,
            "price": forecast_prices,
            "is_forecast": [True] * len(forecast_dates)
        })
        
        df_historical = pd.DataFrame({
            "date": df_hist["date"],
            "price": df_hist["price"],
            "is_forecast": [False] * len(df_hist)
        })
        
        # Combine historical and forecasted
        df_combined = pd.concat([df_historical, df_forecast]).reset_index(drop=True)
        
        return {
            "fund_code": fund_code,
            "forecast_date": latest_date_str,
            "target_date": target_date_str,
            "latest_price": latest_price,
            "predicted_price": final_predicted_price,
            "predicted_return": round(predicted_return, 2),
            "df_forecast": df_forecast,
            "df_combined": df_combined
        }

    def generate_all_forecasts(self):
        """
        Generates 2-week predictions for all DEFAULT_FUNDS and saves them.
        """
        logger.info("Generating forecasts for all funds...")
        results = {}
        for code in DEFAULT_FUNDS.keys():
            res = self.generate_2_week_forecast(code)
            if res:
                results[code] = res
        logger.info("Forecast generation completed.")
        return results
