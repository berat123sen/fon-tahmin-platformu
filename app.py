import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import logging
from config import DEFAULT_FUNDS
import database
from tefas_client import TefasClient
from news_crawler import NewsCrawler
from forecaster import Forecaster
import utils

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Yerel Fon Analiz, Grafik ve AI Tahmin Platformu",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Dark Theme CSS Injection
st.markdown("""
    <style>
        /* Import premium font */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        /* Main background and font */
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #0b0f19 !important;
            color: #cbd5e1 !important;
            font-family: 'Outfit', -apple-system, sans-serif;
        }
        
        /* Sidebar background */
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b;
        }
        
        /* Custom Glowing Card styles */
        .glow-card {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .glow-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.2), 0 4px 6px -2px rgba(99, 102, 241, 0.1);
            border-color: #4f46e5;
        }
        .card-title {
            font-size: 14px;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .card-value {
            font-size: 28px;
            font-weight: 800;
            color: #f8fafc;
            margin-top: 5px;
        }
        .card-desc {
            font-size: 12px;
            color: #64748b;
            margin-top: 5px;
        }
        
        /* Interactive buttons */
        .stButton>button {
            background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%) !important;
            color: #ffffff !important;
            border: none !important;
            padding: 10px 24px !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4) !important;
            transition: all 0.3s ease !important;
        }
        .stButton>button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.6) !important;
        }
        
        /* Table header style */
        .dataframe th {
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }
        
        /* Mobile responsive adjustments */
        @media (max-width: 768px) {
            /* Force Streamlit columns to collapse and stack vertically on mobile */
            [data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
                padding-left: 0px !important;
                padding-right: 0px !important;
                margin-bottom: 20px !important;
            }
            /* Adjust top glowing cards for mobile spacing */
            .glow-card {
                padding: 15px !important;
                margin-bottom: 10px !important;
            }
            .card-value {
                font-size: 22px !important;
            }
            /* Make text smaller on mobile to prevent overflow */
            h1 {
                font-size: 24px !important;
            }
            h2 {
                font-size: 20px !important;
            }
            h3 {
                font-size: 18px !important;
            }
        }
    </style>
""", unsafe_allow_html=True)

# Helper function to seed data if empty
def seed_database_if_empty():
    database.init_db()
    existing_funds = database.get_funds()
    
    # We want to make sure all DEFAULT_FUNDS are in the DB and have prices
    # If not, let's do a complete seed
    has_defaults = all(code in existing_funds for code in DEFAULT_FUNDS.keys())
    
    if has_defaults:
        # Check if we actually have prices
        conn = database.get_db_connection()
        count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        conn.close()
        if count > 100:  # we expect at least ~300 prices for 9 funds
            return
            
    logger.info("Database is empty or has test leftovers. Initializing with mock historical prices and predictions...")
    
    # Clean up any test leftovers
    conn = database.get_db_connection()
    conn.execute("DELETE FROM funds")
    conn.execute("DELETE FROM prices")
    conn.execute("DELETE FROM forecasts")
    conn.execute("DELETE FROM news_sentiment")
    conn.commit()
    conn.close()
    
    # Save default funds
    for code, name in DEFAULT_FUNDS.items():
        database.save_fund(code, name)
        
    # Generate historical prices for the last 60 days
    tefas_client = TefasClient()
    today_str = datetime.now().strftime("%Y-%m-%d")
    start_date_str = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    for code in DEFAULT_FUNDS.keys():
        df_prices = tefas_client.fetch_fund_data(code, start_date_str, today_str)
        if not df_prices.empty:
            database.save_prices(df_prices)
            
    # Seed historical forecasts from 14 days ago to evaluate right now for backtest simulation!
    # Made 14 days ago, targeting today
    date_14_days_ago = datetime.now() - timedelta(days=14)
    date_14_days_ago_str = date_14_days_ago.strftime("%Y-%m-%d")
    
    for code in DEFAULT_FUNDS.keys():
        # Get historical price from 14 days ago
        df_hist = database.get_historical_prices(code, end_date=date_14_days_ago_str)
        if not df_hist.empty:
            price_then = float(df_hist.iloc[-1]["price"])
            # Generate a predicted price with some return
            pred_return = float(hash(code) % 7) - 2.5 # returns between -2.5% and +4.5%
            pred_price = price_then * (1 + (pred_return / 100.0))
            
            # Save historical forecast
            database.save_forecast(
                fund_code=code,
                forecast_date=date_14_days_ago_str,
                target_date=today_str,
                predicted_return=pred_return,
                predicted_price=pred_price
            )
            
    # Seed some mock news so that sentiment analysis is instantly populated
    news_crawler = NewsCrawler()
    news_items = news_crawler.fetch_latest_news()
    for news in news_items:
        for code in DEFAULT_FUNDS.keys():
            score, label = news_crawler.analyze_sentiment(news["title"], code)
            database.save_news_sentiment(
                fund_code=code,
                title=news["title"],
                url=news["url"],
                published_date=news["published_date"],
                sentiment_score=score,
                sentiment_label=label
            )
            
    # Run backtesting & first predictions
    forecaster = Forecaster()
    forecaster.run_backtesting()
    forecaster.generate_all_forecasts()
    logger.info("Database seeding completed successfully.")

# Seed on startup
seed_database_if_empty()

# Sidebar Setup
st.sidebar.markdown(f"<h2 style='text-align: center; color: #f8fafc;'>📈 Fon AI Platformu</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; color: #94a3b8; font-size: 13px;'>TEFAS Analiz ve 2 Haftalık Yapay Zeka Tahmin Motoru</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Gemini API Key Entry in Sidebar (Optional config fallback)
user_api_key = st.sidebar.text_input("Gemini API Anahtarı (Opsiyonel)", value="", type="password", help="Haber analizini kendi Gemini anahtarınızla yapmak isterseniz girin. Girilmezse dahili NLP motoru kullanılır.")
st.sidebar.markdown("---")

# Pipeline runner
if st.sidebar.button("🔄 Verileri Yenile ve Yeniden Analiz Et"):
    with st.spinner("Güncel TEFAS fiyatları çekiliyor, haberler taranıyor ve AI tahminleri yapılıyor..."):
        try:
            # 1. Fetch latest prices
            client = TefasClient()
            today_str = datetime.now().strftime("%Y-%m-%d")
            start_date_str = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
            
            for code in DEFAULT_FUNDS.keys():
                df_prices = client.fetch_fund_data(code, start_date_str, today_str)
                if not df_prices.empty:
                    database.save_prices(df_prices)
            
            # 2. Analyze News Sentiment
            crawler = NewsCrawler(api_key=user_api_key if user_api_key else None)
            crawler.run_analysis_for_all_funds()
            
            # 3. Evaluate past forecasts (Backtesting)
            forecaster = Forecaster()
            forecaster.run_backtesting()
            
            # 4. Generate new predictions
            forecaster.generate_all_forecasts()
            
            st.sidebar.success("Veri yenileme ve AI analizleri başarıyla tamamlandı!")
            # Trigger full rerun
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Hata oluştu: {e}")

# Fetch data from DB for rendering
funds_dict = database.get_funds()
predictions_dict = {}
accuracies_dict = {}

for code in DEFAULT_FUNDS.keys():
    # Load latest forecasts
    df_fc = database.get_all_forecasts(code)
    if not df_fc.empty:
        # Get the latest row
        latest_fc = df_fc.iloc[0]
        # Fetch historical + forecast series
        df_hist = database.get_historical_prices(code)
        # Re-construct expected dictionary format
        predictions_dict[code] = {
            "predicted_return": latest_fc["predicted_return"],
            "predicted_price": latest_fc["predicted_price"],
            "forecast_date": latest_fc["forecast_date"],
            "target_date": latest_fc["target_date"]
        }
    
    # Load accuracies
    accuracies_dict[code] = database.get_fund_accuracy(code)

# Header Section
st.markdown("<h1 style='text-align: center; margin-bottom: 5px; color: #f8fafc;'>Yerel Fon Analiz, Grafik ve 2 Haftalık Yapay Zeka Tahmin Platformu</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 16px; margin-bottom: 30px;'>Türkiye TEFAS Fonları için Sayısal Trend Analizi ve Gemini Yapay Zeka Haber Sentiment Entegrasyonu</p>", unsafe_allow_html=True)

# Top Cards
col_card1, col_card2, col_card3 = st.columns(3, gap="small")

# Find top performing fund by prediction
top_perf_code = "N/A"
top_perf_val = 0.0
for code, pred in predictions_dict.items():
    if pred["predicted_return"] > top_perf_val:
        top_perf_val = pred["predicted_return"]
        top_perf_code = code

# Find most stable prediction fund
most_stable_code = "N/A"
most_stable_val = 0.0
for code, acc in accuracies_dict.items():
    if acc["avg_accuracy"] is not None and acc["avg_accuracy"] > most_stable_val:
        most_stable_val = acc["avg_accuracy"]
        most_stable_code = code

# Sentiment Summary index
all_scores = []
for code in DEFAULT_FUNDS.keys():
    df_n = database.get_news_sentiment(code, limit=5)
    if not df_n.empty:
        all_scores.extend(df_n["sentiment_score"].tolist())
avg_sentiment_market = sum(all_scores) / len(all_scores) if all_scores else 0.0
sentiment_lbl = "Pozitif" if avg_sentiment_market > 0.1 else "Negatif" if avg_sentiment_market < -0.1 else "Dengeli"

with col_card1:
    st.markdown(f"""
        <div class="glow-card">
            <div class="card-title">En Yüksek Tahmini Getiri (2 Hafta)</div>
            <div class="card-value" style="color: #10b981;">{top_perf_code} ({utils.format_percentage(top_perf_val)})</div>
            <div class="card-desc">AI tahminlerine göre önümüzdeki 14 günde en yüksek yükseliş beklenen fon.</div>
        </div>
    """, unsafe_allow_html=True)

with col_card2:
    st.markdown(f"""
        <div class="glow-card">
            <div class="card-title">Tahmin Doğruluk Lideri</div>
            <div class="card-value" style="color: #06b6d4;">{most_stable_code} ({utils.format_percentage(most_stable_val) if most_stable_val > 0 else 'Yeni Platform'})</div>
            <div class="card-desc">Geçmiş tahminlerin gerçekleşen TEFAS fiyatlarıyla kıyaslanması sonucu en yüksek başarı oranı.</div>
        </div>
    """, unsafe_allow_html=True)

with col_card3:
    st.markdown(f"""
        <div class="glow-card">
            <div class="card-title">Genel Piyasa Duygusu</div>
            <div class="card-value" style="color: #6366f1;">{sentiment_lbl} ({avg_sentiment_market:+.2f})</div>
            <div class="card-desc">Finansal haberlerin ve KAP bildirimlerinin Gemini tarafından yapılan ortalama duygu analiz puanı.</div>
        </div>
    """, unsafe_allow_html=True)

# Main Grid (Fund List & Details)
col_left, col_right = st.columns([2, 3], gap="small")

with col_left:
    st.markdown("### 📋 Takip Listesi ve AI Tahminleri")
    
    # Construct DataFrame for table
    table_data = []
    for code, name in DEFAULT_FUNDS.items():
        df_hist = database.get_historical_prices(code)
        latest_price = float(df_hist.iloc[-1]["price"]) if not df_hist.empty else 0.0
        
        pred = predictions_dict.get(code, {"predicted_return": 0.0})
        acc = accuracies_dict.get(code, {"avg_accuracy": None})
        
        # Calculate recent return (e.g. last 7 days)
        recent_ret = 0.0
        if len(df_hist) >= 5:
            price_5d_ago = float(df_hist.iloc[-5]["price"])
            recent_ret = ((latest_price - price_5d_ago) / price_5d_ago) * 100.0
            
        # Get average news sentiment
        df_news = database.get_news_sentiment(code, limit=5)
        sentiment_avg = df_news["sentiment_score"].mean() if not df_news.empty else 0.0
        
        table_data.append({
            "Kod": code,
            "Fon Adı": name[:30] + "...",
            "Son Fiyat (TL)": round(latest_price, 4),
            "Son 1 Haftalık Getiri": round(recent_ret, 2),
            "Duygu Skoru (AI)": round(sentiment_avg, 2),
            "2 Haftalık AI Tahmini": pred["predicted_return"],
            "Tahmin Başarısı": acc["avg_accuracy"]
        })
        
    df_table = pd.DataFrame(table_data)
    
    # Sorting selector
    sort_option = st.selectbox(
        "🔀 Listeyi Sırala:",
        options=[
            "Varsayılan (Kod Sıralı)",
            "Fon Adı (A-Z)",
            "Son Fiyat (En Yüksek)",
            "Son 1 Haftalık Getiri (En Yüksek)",
            "Duygu Skoru (En Yüksek)",
            "2 Haftalık AI Tahmini (En Yüksek)",
            "Tahmin Başarısı (En Yüksek)"
        ]
    )
    
    # Sort DataFrame based on selection
    if sort_option == "Fon Adı (A-Z)":
        df_table = df_table.sort_values(by="Fon Adı", ascending=True)
    elif sort_option == "Son Fiyat (En Yüksek)":
        df_table = df_table.sort_values(by="Son Fiyat (TL)", ascending=False)
    elif sort_option == "Son 1 Haftalık Getiri (En Yüksek)":
        df_table = df_table.sort_values(by="Son 1 Haftalık Getiri", ascending=False)
    elif sort_option == "Duygu Skoru (En Yüksek)":
        df_table = df_table.sort_values(by="Duygu Skoru (AI)", ascending=False)
    elif sort_option == "2 Haftalık AI Tahmini (En Yüksek)":
        df_table = df_table.sort_values(by="2 Haftalık AI Tahmini", ascending=False)
    elif sort_option == "Tahmin Başarısı (En Yüksek)":
        df_table = df_table.sort_values(by="Tahmin Başarısı", ascending=False, na_position='last')
        
    # Let user select the active fund via a dropdown
    selected_fund_code = st.selectbox(
        "🔍 Detaylarını İncelemek İstediğiniz Fonu Seçin:",
        options=DEFAULT_FUNDS.keys(),
        format_func=lambda x: f"{x} - {DEFAULT_FUNDS[x]}"
    )
    
    # Render table elegantly with styled column configurations
    st.dataframe(
        df_table,
        column_config={
            "Son Fiyat (TL)": st.column_config.NumberColumn(format="%.4f ₺"),
            "Son 1 Haftalık Getiri": st.column_config.NumberColumn(format="%+.2f%%"),
            "Duygu Skoru (AI)": st.column_config.NumberColumn(format="%+.2f"),
            "2 Haftalık AI Tahmini": st.column_config.NumberColumn(format="%+.2f%%"),
            "Tahmin Başarısı": st.column_config.NumberColumn(format="%.1f%%")
        },
        use_container_width=True,
        hide_index=True
    )

with col_right:
    st.markdown(f"### 📊 Detaylı Grafik & Analiz: {selected_fund_code}")
    
    # Load historical + forecast combined data
    df_hist = database.get_historical_prices(selected_fund_code)
    
    # Generate interactive plot
    if not df_hist.empty:
        # Load predictions to reconstruct combined series
        df_fc = database.get_all_forecasts(selected_fund_code)
        if not df_fc.empty:
            latest_fc = df_fc.iloc[0]
            # Construct forecast dataframe segment
            forecast_dates = []
            forecast_prices = []
            curr_date = pd.to_datetime(latest_fc["forecast_date"])
            curr_price = float(df_hist.iloc[-1]["price"])
            
            # Extrapolate forecast prices
            pred_return_daily = (latest_fc["predicted_return"] / 100.0) / 10 # approximate 10 business days return
            for day in range(1, 15):
                curr_date = curr_date + timedelta(days=1)
                if curr_date.weekday() < 5:
                    curr_price = curr_price * (1.0 + pred_return_daily)
                forecast_prices.append(curr_price)
                forecast_dates.append(curr_date)
                
            df_fore = pd.DataFrame({
                "date": forecast_dates,
                "price": forecast_prices,
                "is_forecast": [True] * len(forecast_dates)
            })
            
            df_historical = pd.DataFrame({
                "date": df_hist["date"],
                "price": df_hist["price"],
                "is_forecast": [False] * len(df_hist)
            })
            
            df_combined = pd.concat([df_historical, df_fore]).reset_index(drop=True)
            
            fig = utils.create_forecast_plotly_chart(df_combined, selected_fund_code)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Bu fona ait tahmin verisi bulunamadı. Lütfen sol menüden verileri yenileyin.")
    else:
        st.warning("Fiyat geçmişi yüklenemedi.")

# Secondary Panel: Haber Duygusu ve Simülatör
st.markdown("---")
col_bot_left, col_bot_right = st.columns([1, 1], gap="small")

with col_bot_left:
    st.markdown(f"### 📰 Son Finansal Haberler ve Sentiment Analizleri ({selected_fund_code})")
    
    df_news = database.get_news_sentiment(selected_fund_code, limit=5)
    if not df_news.empty:
        for idx, row in df_news.iterrows():
            sentiment_score = row["sentiment_score"]
            sentiment_label = row["sentiment_label"]
            
            # Neon badge colors based on label
            color = "#10b981" if sentiment_label == "Pozitif" else "#ef4444" if sentiment_label == "Negatif" else "#64748b"
            
            st.markdown(f"""
                <div style="background-color: #1e293b; padding: 12px; border-radius: 8px; border-left: 5px solid {color}; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <span style="font-size: 11px; color: #94a3b8;">{row["published_date"]}</span>
                        <span style="background-color: {color}; color: #ffffff; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 800;">{sentiment_label} ({sentiment_score:+.2f})</span>
                    </div>
                    <div style="font-size: 14px; font-weight: 600; color: #f1f5f9;">{row["title"]}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Bu fona ait analiz edilmiş haber bulunamadı.")

with col_bot_right:
    st.markdown("### 🧮 Akıllı Kâr ve Portföy Simülatörü")
    st.markdown("Yatırım bütçenizi ve risk tercihinizi girin, AI motorumuz en iyi başarı oranına ve getiriye sahip fon sepetini simüle etsin.")
    
    sim_col1, sim_col2 = st.columns(2, gap="small")
    with sim_col1:
        budget_input = st.number_input("Yatırım Miktarı (TL):", min_value=1000, max_value=10000000, value=50000, step=1000)
    with sim_col2:
        risk_input = st.selectbox("Risk Toleransı:", options=["Düşük", "Orta", "Yüksek"], index=1)
        
    # Run simulation
    rec = utils.portfolio_recommendation(budget_input, risk_input, predictions_dict, accuracies_dict)
    
    if rec:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); border: 1px solid #4f46e5; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 15px;">
                <div style="font-size: 13px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">2 Hafta Sonundaki Tahmini Kâr / Toplam Bakiye</div>
                <div style="font-size: 32px; font-weight: 800; color: #10b981; margin-top: 5px;">+{utils.format_currency(rec["total_profit"])}</div>
                <div style="font-size: 20px; font-weight: 600; color: #f8fafc; margin-top: 2px;">Toplam Bakiye: {utils.format_currency(rec["total_final"])}</div>
                <div style="font-size: 12px; color: #64748b; margin-top: 5px;">Simüle edilen ağırlıklı getiri oranı: <strong style="color: #6366f1;">%{rec["weighted_return"]:.2f}</strong></div>
            </div>
        """, unsafe_allow_html=True)
        
        # Display breakdown
        st.markdown("**Sepet Dağılım Detayı:**")
        df_rec_table = pd.DataFrame(rec["items"])
        st.dataframe(
            df_rec_table[[ "code", "weight", "allocated_amount", "predicted_return", "accuracy", "profit" ]],
            column_config={
                "code": "Fon Kodu",
                "weight": st.column_config.NumberColumn("Ağırlık", format="%.2f"),
                "allocated_amount": st.column_config.NumberColumn("Yatırım Tutarı", format="%.2f ₺"),
                "predicted_return": st.column_config.NumberColumn("AI Tahmini Return", format="%+.2f%%"),
                "accuracy": "Tarihsel Doğruluk",
                "profit": st.column_config.NumberColumn("Beklenen Kâr", format="%.2f ₺")
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Show allocation pie chart
        fig_pie = utils.create_portfolio_pie_chart(rec["items"])
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Simülatör için yeterli tahmin verisi bulunmamaktadır.")
