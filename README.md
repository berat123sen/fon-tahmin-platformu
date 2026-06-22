# 📈 Yerel Fon Analiz, Grafik ve 2 Haftalık AI Tahmin Platformu

Bu proje, Türkiye TEFAS (Türkiye Elektronik Fon Dağıtım Platformu) fon verilerini analiz eden, finans haberlerini Gemini yapay zeka modeli ile değerlendirip 2 haftalık trend tahminleri oluşturan ve bunları geçmişe dönük (Backtesting) doğrulayan premium, koyu tema (dark mode) destekli bir finansal dashboard uygulamasıdır.

---

## 🚀 Özellikler

1. **Gelişmiş Arayüz ve UI/UX (Premium Koyu Tema):**
   - Gece mavisi ve antrasit tonlarına sahip, gözü yormayan modern tasarım dili.
   - Plotly tabanlı etkileşimli grafikler: Geçmiş 30/60 günlük fiyatlar (düz çizgi) ve 2 haftalık AI tahmin projeksiyonu (kesikli neon çizgi ile güven aralığı gölgesi).
2. **TEFAS Canlı Veri Entegrasyonu:**
   - Türkiye piyasasındaki fon kodlarını (`AFT`, `TTE`, `TI3`, `YAS`, `MAC`, `IIH`, `OLD`, `GMR`, `IPG`) dinamik olarak çeker.
   - TEFAS API'sinin yavaş veya kapalı olduğu durumlarda çalışmayı sürdürmek için **Geometrik Brownian Hareketi (GBM)** algoritmasını kullanan finansal simülasyon fallback'i içerir.
3. **Yapay Zeka Destekli Sentiment Analizi:**
   - Bloomberg HT gibi kanallardan gelen finans haberlerini ve KAP bildirimlerini tarar.
   - **Gemini API** entegrasyonu ile haberlerin ilgili fon kodları üzerindeki etkisini -1.0 (çok olumsuz) ile 1.0 (çok olumlu) arasında puanlar.
4. **Tahmin Başarı Oranı & SQLite Backtesting:**
   - Yapılan her tahmini ve gerçekleşen fiyatları yerel SQLite veri tabanına kaydeder.
   - Hedef tarihi gelen tahminleri otomatik olarak gerçek TEFAS fiyatlarıyla kıyaslayarak her fon için net bir **"Tahmin Başarı/Doğruluk Yüzdesi"** metriği üretir.
5. **Akıllı Getiri / Kâr Simülatörü:**
   - Kullanıcının bütçe (TL) ve risk toleransına (Düşük, Orta, Yüksek) göre AI tahminleri ve başarı olasılıklarını birleştirerek optimize edilmiş bir fon sepeti önerir.
   - 2 hafta sonundaki "Tahmini Kâr ve Toplam Bakiye" simülasyonunu anlık olarak sunar.

---

## 📁 Proje Klasör Yapısı

```
fon_platform/
├── app.py                  # Streamlit Koyu Tema Dashboard Arayüzü (Ana Uygulama)
├── config.py               # Varsayılan Fon Listesi, DB Yolu ve RSS URL Ayarları
├── database.py             # SQLite Veri Tabanı Katmanı (Fiyat Önbelleği, Tahminler ve Sentiment)
├── tefas_client.py         # TEFAS Veri Çekme Modülü (pytefas/tefas-crawler ve GBM Fallback)
├── news_crawler.py         # Haber Tarayıcı ve Gemini Duygu Analizi Modülü
├── forecaster.py           # 2 Haftalık AI + Trend Tahmin ve Backtesting Motoru
├── utils.py                # Dinamik Portföy Simülatörü ve Plotly Tasarımları
├── test_modules.py         # Otomatik Entegrasyon Test Scripti
├── requirements.txt        # Python Bağımlılıkları Listesi
└── .gitignore              # Git Tarafından İzlenmeyecek Dosyalar (Log, DB, .env vb.)
```

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Depoyu Klonlayın veya İndirin
```bash
git clone <github-depo-linkiniz>
cd <depo-klasoru>
```

### 2. Sanal Ortam Oluşturun ve Aktifleştirin (Önerilen)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Gerekli Kütüphaneleri Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Gemini API Anahtarı Tanımlama (Opsiyonel)
Proje kök dizininde `.env` adında bir dosya oluşturup API anahtarınızı ekleyebilirsiniz:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```
*Not: API anahtarı eklemezseniz, sistem duygu analizi ve tahminler için akıllı dahili kural tabanlı NLP algoritmasını fallback olarak kullanmaya devam edecektir.*

### 5. Uygulamayı Başlatın
```bash
python -m streamlit run app.py
```
Uygulama otomatik olarak açılacaktır. Açılmazsa tarayıcınızdan **`http://localhost:8501`** adresine gidebilirsiniz.

---

## 📊 Entegrasyon Testleri
Sistem modüllerinin (Veri tabanı, TEFAS API bağlantısı, Haber analizi ve Tahmin algoritması) doğru çalıştığını doğrulamak için aşağıdaki scripti çalıştırabilirsiniz:
```bash
python test_modules.py
```
Bu script tüm modülleri test edip `ALL AUTOMATED MODULE CHECKS PASSED SUCCESSFULLY!` mesajını verecektir.

---

## 🛡️ Lisans
Bu proje MIT lisansı altında lisanslanmıştır.
