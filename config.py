import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Gemini API Key configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# SQLite Database path
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "fon_data.db")

# Default Turkish mutual funds for the platform
DEFAULT_FUNDS = {
    "AFT": "Ak Portföy Yeni Teknolojiler Yabancı Hisse Senedi Fonu",
    "TTE": "İş Portföy BIST Teknoloji Ağırlıklı Sınırlı Hisse Senedi Fonu",
    "TI3": "İş Portföy BIST 30 Dışı Şirketler Hisse Senedi Fonu",
    "YAS": "Yapı Kredi Portföy Koç Holding İştirakleri Hisse Senedi Fonu",
    "MAC": "Marmara Capital Portföy Hisse Senedi Fonu (Hisse Yoğun)",
    "IIH": "İstanbul Portföy Üçüncü Hisse Senedi Fonu (Hisse Yoğun)",
    "OLD": "QNB Portföy Temiz Enerji ve Su Fon Sepeti Fonu",
    "GMR": "Inveo Portföy Hisse Senedi Fonu (Hisse Yoğun)",
    "IPG": "İş Portföy Elektrikli Araçlar Karma Fonu"
}

# RSS / News scraping urls
NEWS_FEEDS = [
    "https://www.bloomberght.com/rss",
    "https://www.trtworld.com/rss/business",  # fallback in case of need
]
