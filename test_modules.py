import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def test_pipeline():
    logger.info("Initializing automated verification checks...")
    
    # 1. Test config loading
    try:
        import config
        logger.info(f"Loaded config. Default funds: {list(config.DEFAULT_FUNDS.keys())}")
    except Exception as e:
        logger.error(f"Config module test failed: {e}")
        return False

    # 2. Test database initialization
    try:
        import database
        database.init_db()
        logger.info(f"Database initialized. Path: {config.DB_PATH}")
        # Insert/replace test fund
        database.save_fund("TEST_FUND", "Test Fund Name")
        funds = database.get_funds()
        assert "TEST_FUND" in funds, "Fund saving/retrieval failed"
        logger.info("Database tests passed.")
    except Exception as e:
        logger.error(f"Database module test failed: {e}")
        return False

    # 3. Test TEFAS client
    try:
        from tefas_client import TefasClient
        client = TefasClient()
        df = client.fetch_fund_data("TTE", "2026-05-01", "2026-05-15")
        assert not df.empty, "TefasClient returned empty dataframe"
        assert "price" in df.columns, "Price column not found in df"
        # Save to DB
        database.save_prices(df)
        logger.info(f"TEFAS client test passed. Fetched {len(df)} price points.")
    except Exception as e:
        logger.error(f"TEFAS client test failed: {e}")
        return False

    # 4. Test News crawler and sentiment
    try:
        from news_crawler import NewsCrawler
        crawler = NewsCrawler()
        news = crawler.fetch_latest_news()
        assert len(news) > 0, "No news fetched"
        # Test sentiment analysis
        score, label = crawler.analyze_sentiment(news[0]["title"], "TTE")
        logger.info(f"Sentiment analysis test: Title='{news[0]['title']}' -> Score={score}, Label={label}")
        # Save sentiment to DB
        database.save_news_sentiment("TTE", news[0]["title"], news[0]["url"], news[0]["published_date"], score, label)
        logger.info("News crawler tests passed.")
    except Exception as e:
        logger.error(f"News crawler test failed: {e}")
        return False

    # 5. Test Forecaster and 2-week predictions
    try:
        from forecaster import Forecaster
        forecaster = Forecaster()
        
        # Save mock price history to evaluate forecast backtesting
        import pandas as pd
        from datetime import datetime, timedelta
        
        # Insert some historical prices for TTE to ensure we can forecast
        today = datetime.now()
        price_list = []
        for x in range(30):
            d = (today - timedelta(days=30-x)).strftime("%Y-%m-%d")
            price_list.append({"code": "TTE", "date": d, "price": 10.0 + x * 0.1})
        df_dummy = pd.DataFrame(price_list)
        database.save_prices(df_dummy)
        
        # Run 2-week forecast
        res = forecaster.generate_2_week_forecast("TTE")
        assert res is not None, "Forecasting returned None"
        logger.info(f"Forecast test passed. Generated predicted 2-week return: {res['predicted_return']}%")
        
        # Run backtest evaluator
        forecaster.run_backtesting()
        logger.info("Forecaster and Backtesting tests passed.")
    except Exception as e:
        logger.error(f"Forecaster module test failed: {e}")
        return False

    # 6. Test utils calculations
    try:
        import utils
        predictions = {
            "TTE": {"predicted_return": 3.5, "predicted_price": 10.35, "forecast_date": "2026-06-01", "target_date": "2026-06-15"}
        }
        accuracies = {
            "TTE": {"avg_accuracy": 92.5, "total_evaluated": 1}
        }
        rec = utils.portfolio_recommendation(10000, "Orta", predictions, accuracies)
        assert rec is not None, "Portfolio recommendation returned None"
        assert rec["total_profit"] > 0, "Portfolio profit calculation incorrect"
        logger.info("Utils tests passed.")
    except Exception as e:
        logger.error(f"Utils module test failed: {e}")
        return False

    logger.info("ALL AUTOMATED MODULE CHECKS PASSED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)
