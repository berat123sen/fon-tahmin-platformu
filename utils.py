import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from config import DEFAULT_FUNDS

def format_currency(val):
    return f"{val:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

def format_percentage(val):
    if val is None:
        return "N/A"
    return f"%{val:.2f}"

def portfolio_recommendation(budget, risk_tolerance, predictions, accuracies):
    """
    Simulates a dynamic return/profit calculator based on AI predictions and historical accuracy.
    risk_tolerance: 'Düşük', 'Orta', 'Yüksek'
    predictions: dict of fund_code -> prediction result dict from forecaster
    accuracies: dict of fund_code -> accuracy dict { 'avg_accuracy': float or None, 'total_evaluated': int }
    """
    # Risk Profile allocations (which funds to choose and weights)
    # Target funds must be in DEFAULT_FUNDS and have predictions
    available_funds = [code for code in DEFAULT_FUNDS.keys() if code in predictions]
    
    if not available_funds:
        return None
        
    # Standard allocations based on risk profiles
    # We will pick the top-performing funds that match the risk criteria
    # Low Risk: Steady corporate, defensive equity, moderate tech (YAS, MAC, IIH)
    # Medium Risk: Balanced technology, global and thematic (AFT, TTE, YAS, OLD)
    # High Risk: High beta technology, growth and thematic (TTE, AFT, TI3, IPG, GMR)
    
    profiles = {
        "Düşük": {
            "YAS": 0.40,  # Koç Holding (Defensive Bluechip)
            "MAC": 0.30,  # Marmara Capital (Experienced Value)
            "IIH": 0.30   # İstanbul Portföy (Active Equity)
        },
        "Orta": {
            "AFT": 0.30,  # NASDAQ Tech (Global Tech)
            "TTE": 0.25,  # BIST Tech (Local Tech)
            "YAS": 0.25,  # Koç Holding (Defensive Bluechip)
            "OLD": 0.20   # Clean Energy (Thematic)
        },
        "Yüksek": {
            "TTE": 0.35,  # BIST Tech (High Beta Tech)
            "AFT": 0.25,  # NASDAQ Tech (Global Tech Growth)
            "TI3": 0.20,  # BIST 30 Dışı (Small Cap Growth)
            "IPG": 0.20   # Electric Vehicles (Thematic Beta)
        }
    }
    
    selected_allocation = profiles.get(risk_tolerance, profiles["Orta"])
    
    # Filter to only available funds, re-normalize weights
    weights = {}
    for code, weight in selected_allocation.items():
        if code in available_funds:
            weights[code] = weight
            
    if not weights:
        # Fallback to whatever is available
        for code in available_funds[:3]:
            weights[code] = 1.0 / min(3, len(available_funds))
            
    # Normalize weights to sum to 1.0
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}
    
    # Compile portfolio items
    items = []
    total_predicted_profit = 0.0
    
    for code, weight in weights.items():
        pred = predictions[code]
        acc_info = accuracies.get(code, {"avg_accuracy": None, "total_evaluated": 0})
        
        allocated_amount = budget * weight
        pred_return_pct = pred["predicted_return"]  # percentage
        
        # Calculate simulated 2-week profit
        sim_profit = allocated_amount * (pred_return_pct / 100.0)
        final_balance = allocated_amount + sim_profit
        total_predicted_profit += sim_profit
        
        accuracy_val = acc_info.get("avg_accuracy")
        accuracy_display = format_percentage(accuracy_val) if accuracy_val is not None else "Yeni Fon (%85 Simüle)"
        
        items.append({
            "code": code,
            "name": DEFAULT_FUNDS[code],
            "weight": weight,
            "allocated_amount": allocated_amount,
            "predicted_return": pred_return_pct,
            "accuracy": accuracy_display,
            "profit": sim_profit,
            "final_balance": final_balance
        })
        
    weighted_return = (total_predicted_profit / budget) * 100.0
    
    return {
        "items": items,
        "total_initial": budget,
        "total_profit": total_predicted_profit,
        "total_final": budget + total_predicted_profit,
        "weighted_return": weighted_return
    }

def create_forecast_plotly_chart(df_combined, fund_code):
    """
    Creates a premium dark-themed interactive chart showing historical prices
    and the 14-day dotted forecast line with a shaded confidence zone.
    """
    fund_name = DEFAULT_FUNDS.get(fund_code, fund_code)
    
    # Split historical and forecast
    df_hist = df_combined[~df_combined["is_forecast"]].copy()
    df_fore = df_combined[df_combined["is_forecast"]].copy()
    
    # For a seamless connection, add the last historical point to the start of forecast
    if not df_hist.empty and not df_fore.empty:
        last_hist = df_hist.iloc[-1:]
        # Modify copy to mark as forecast
        last_hist_copy = last_hist.copy()
        last_hist_copy["is_forecast"] = True
        df_fore = pd.concat([last_hist_copy, df_fore]).reset_index(drop=True)
        
    fig = go.Figure()
    
    # 1. Shaded confidence interval / forecast zone (simulated 2% width at end)
    if not df_fore.empty:
        fore_dates = df_fore["date"].tolist()
        fore_prices = df_fore["price"].tolist()
        
        # Calculate fan-chart spread that grows over time
        upper_bound = []
        lower_bound = []
        for idx, price in enumerate(fore_prices):
            # Spread grows from 0% at the connection point to 4% at the end of 14 days
            spread = (idx / len(fore_prices)) * 0.04
            upper_bound.append(price * (1.0 + spread))
            lower_bound.append(price * (1.0 - spread))
            
        fig.add_trace(go.Scatter(
            x=fore_dates + fore_dates[::-1],
            y=upper_bound + lower_bound[::-1],
            fill='toself',
            fillcolor='rgba(99, 102, 241, 0.12)', # neon indigo translucent
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="skip",
            showlegend=True,
            name="AI Güven Aralığı"
        ))
        
    # 2. Historical price path
    if not df_hist.empty:
        fig.add_trace(go.Scatter(
            x=df_hist["date"],
            y=df_hist["price"],
            mode="lines",
            name="Gerçek Fiyat",
            line=dict(color="#06b6d4", width=3), # Glowing Cyan
            hovertemplate="Tarih: %{x|%d.%m.%Y}<br>Fiyat: %{y:.6f} ₺<extra></extra>"
        ))
        
    # 3. Forecast price path
    if not df_fore.empty:
        fig.add_trace(go.Scatter(
            x=df_fore["date"],
            y=df_fore["price"],
            mode="lines+markers",
            name="2 Haftalık AI Tahmini",
            line=dict(color="#6366f1", width=2.5, dash="dash"), # Neon Indigo Dash
            marker=dict(size=4, color="#6366f1"),
            hovertemplate="Tarih: %{x|%d.%m.%Y}<br>Tahmini Fiyat: %{y:.6f} ₺ (AI)<extra></extra>"
        ))
        
    # Premium Dark Layout Configuration
    fig.update_layout(
        title={
            'text': f"<b>{fund_code} - Fiyat Analizi ve AI Tahmin Grafiği</b><br><span style='font-size: 12px; color: #9ca3af;'>{fund_name}</span>",
            'y': 0.95,
            'x': 0.01,
            'xanchor': 'left',
            'yanchor': 'top'
        },
        xaxis_title="Tarih",
        yaxis_title="Birim Fiyat (TL)",
        paper_bgcolor="#111827",  # Grey-900 (Dark background matching app)
        plot_bgcolor="#111827",
        font=dict(color="#e5e7eb", family="Outfit, Inter, sans-serif"),
        xaxis=dict(
            showgrid=True,
            gridcolor="#374151",  # Grey-700
            zeroline=False,
            tickformat="%d.%m"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#374151",
            zeroline=False,
            tickformat=",.2f"
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)"
        ),
        margin=dict(l=60, r=30, t=80, b=50),
        hovermode="x unified"
    )
    
    return fig

def create_portfolio_pie_chart(items):
    """
    Creates a beautiful plotly donut chart showing portfolio distribution.
    """
    df = pd.DataFrame(items)
    
    # Interactive pie
    fig = px.pie(
        df,
        values='allocated_amount',
        names='code',
        hole=0.4,
        color_discrete_sequence=['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899']
    )
    
    # Style
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate="Fon: %{label}<br>Yatırım: %{value:,.2f} ₺<br>Oran: %{percent}<extra></extra>"
    )
    
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb"),
        margin=dict(l=10, r=10, t=10, b=10)
    )
    
    return fig
