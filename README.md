# Helioguard 
**Milli Uzay Havası Erken Uyarı ve Risk Yönetim Sistemi**

**Helioguard**, Türkiye'nin kritik ulusal altyapılarını siber ve fiziksel etkilere açık hale getiren aşırı jeomanyetik fırtınalara, güneş patlamalarına (Solar Flares) ve koronal kütle atımlarına (CME) karşı korumak için tasarlanmış, sıfır maliyet (zero-cost) hedefli, ileri seviye otonom bir Uzay Havası Karar Destek Sistemidir (DSS).

Sistem, gökyüzündeki görünmez tehlikelere karşı yeryüzündeki dijital ve fiziksel varlıklarımızı savunan bir erken uyarı ve eylem mekanizmasıdır. `mimari.md` ve `PROJE_DETAYI.md` referanslarına tamamen sadık kalınarak üç temel katmanda dizayn edilmiştir. Üstelik sıfır maliyet (zero-cost) kurulum ile bağımsız donanım ve hizmetlere olan ihtiyacı sıfırlayarak, offline çalışma ve yerel cache mimarisine öncelik verir.

---

## 📖 İçindekiler
1. [Proje Vizyonu ve Çözülen Sorun](#1-proje-vizyonu-ve-cözulen-sorun)
2. [Sistemin Çalışma Prensibi: 5 Aşamalı Protokol](#2-sistemin-calisma-prensibi-5-asamali-protokol)
3. [Mekanizma Katmanları ve Veri Mimarisi](#3-mekanizma-katmanlari-ve-veri-mimarisi)
4. [Makine Öğrenmesi (ML) ve Açıklanabilir Yapay Zeka (XAI)](#4-makine-ögrenmesi-ml-ve-aciklanabilir-yapay-zeka-xai)
5. [Dizin Yapısı](#5-dizin-yapisi)
6. [Kurulum ve Çalıştırma (Hızlı Başlangıç)](#6-kurulum-ve-calistirma-hizli-baslangic)
7. [XGBoost Model Eğitimi (Tarihsel Modelleme)](#7-xgboost-model-egitimi-tarihsel-modelleme)
8. [Testler ve Jüri "Smoke Test" Kontrolü](#8-testler-ve-juri-smoke-test-kontrolu)
9. [Hackathon Özel: Arşiv (Backtesting) Modu](#9-hackathon-ozel-arsiv-backtesting-modu)

---

## 1. Proje Vizyonu ve Çözülen Sorun

Modern yaşantımız enerji, haberleşme ve uydulara bağlıdır. Şiddetli uzay olayları (Güneş Fırtınaları) kritik altyapımızda doğrudan fiziksel çöküntüler yaratır:
- **Geomagnetic Induced Currents (GIC):** Manyetik alandaki ani dalgalanmalar uzun enerji nakil hatlarında doğru akımlar (DC) oluşturur ve trafo merkezlerini kullanılamaz hale getirir.
- **Atmosferik Sürüklenme Çoğalması (Drag):** Radyasyon nedeniyle atmosferin genleşmesi, alçak dünya yörüngesindeki uyduların ciddi anlamda yavaşlamasına ve yörünge ömrünü yitirmesine neden olur.
- **İyonosferik Sapmalar ve GNSS Blackout:** Havacılık, denizcilik ve askeri operasyonlar için elzem olan GPS koordinatlarında 50 metrenin üzerinde sapmalara ve telsiz frekansı emilimine yol açar.

Mevcut NOAA uyarı sistemleri 3 saatte bir güncellenen "küresel" uyarılar verir. Helioguard ise tam **L1 Lagrange noktasındaki (1.5 milyon km ötede)** telemetri verisini gerçek zamanlı işleyerek tehdidi saniyeler içerisinde **Türkiye coğrafyasına ve altyapılarına (TEİAŞ şebekelerine, uçuşlara, uydulara)** özel risk faktörlerine dönüştürür. 

---

## 2. Sistemin Çalışma Prensibi: 5 Aşamalı Protokol

### 🚨 Aşama 1: Fırtınayı Önceden Anlama (Early Detection)
NOAA, NASA DONKI, CelesTrak ve küresel telemetri ağları her dakika dinlenir. 
`Bz <= -10 nT` (Manyetik alanın güneye kilitlenmesi) ve güneş rüzgarı hızının **500 km/s**'yi aşması, doğrudan *KIRMIZI ALARM* evresini tetikler.

### ⏱️ Aşama 2: Kinetik Geliş Penceresi ve ETA 
Sistem basit bir varış süresi (1.5 Milyon KM / Rüzgar Hızı) çıkarmanın ötesinde ETA'yı, **Varış Penceresi + Güven Puanı + Risk Bandı** ile matematiksel olarak detaylandırıp ön yüzde otonom, canlı bir sayaç başlatır. NOAA alert ve forecast ürünleri anlık entegre edilir.

### 🗺️ Aşama 3: Turkiye Geo-Uzamsal Isı Haritası
Türkiye'nin Ulusal Elektrik İletim şebekeleri (Overpass API'den gerçek geometri alınarak) WebGL/SVG topolojisi ile `d3-geo` ve `d3-delaunay` üzerinden işlenir. Kp endeksi yüksek olduğunda risk altında olan şebeke nodlarında saniye saniye değişen yüksek çözünürlüklü ısı haritaları oluşturulur.

### 🔌 Aşama 4: Donanım ve Sektörel Analizler (Vulnerability)
Pek çok veriyi entegre yorumlar:
- **X-Ray & F10.7 Rad:** Radyo iletişimi (HF kesintisi) ve LEO uydu irtifası analizi.
- **Yogunluk & Dst (Kyoto):** Doğrudan GIC potansiyeli ve transformatör hasar ölçümü. 

### 🛡️ Aşama 5: Otonom Operasyon (SOP Üretimi)
Elektrik şebekesi, havacılık sektörü ve uydu operatörleri için durum eylem planları üretilir. (Örneğin: *"Kapasitörleri devreden çıkar", "GNSS güvensiz, SATCOM'a geç"* vb.)

---

## 3. Mekanizma Katmanları ve Veri Mimarisi

Çözüm 3 temel klasöre ve zero-cost, yüksek bulunabilirlik (high availability) mimarisine odaklanmıştır:

- `engine/`: NOAA SWPC, NASA DONKI, CelesTrak ve Overpass (OpenStreetMap) verisini çeken Python (FastAPI tabanlı) asenkron uç.
- `data/cache/live/`: Canlı bağlantıların son başarılı isteklerini cache'leyen disk katmanı. API hizmetinin çökmesi durumunda geriye dönük arabellekle yaşama tutunma yeteneği.
- `data/helioguard.db`: Postgres ihtiyacını sıfırlayan, yerleşik zero-cost Local SQLite mimarisi (Orijinal mimari gereği istendiğinde `supabase/` altındaki SQL şemaları kullanılabilir).
- `src/`: React 18 & Vite tabanlı web aplikasyonu. Apple-like (iOS 26) dizayn stili, veri bantları, canlı risk izleme arayüzü ve milisaniyelik reaktif animasyonlarla donanmıştır.

### Arayüz Katmanları:
- **Genel Durum:** Tek ulusal operasyon resmi, risk bandı ve varış ETA zamanı.
- **Uydu Filosu:** TLE verisi üzerinden Türk uydularının sürtünme ve yörünge bozulum analizi.
- **Havacılık ve İHA:** X-Ray düzeyinden doğrudan uçuş güvenliği ve sinyal bütünlüğü.
- **Enerji Şebekesi:** Geometrik vektörlerle çizilen GIC riski ve bölgesel hat analizleri.
- **Kurumsal API:** REST endpointleri ve webhook preview yüzeyi.

---

## 4. Makine Öğrenmesi (ML) ve Açıklanabilir Yapay Zeka (XAI)

Dünya üzerindeki en yenilikçi taraflardan biri sistemin tahminsel yetenekleridir:
- **XGBoost Regression İş Hattı:** Son `10 dk + 1 saat + 6 saat` ölçeklerinde `Bz`, rüzgar hızı, yoğunluk, `Kp` ve `Dst` paternlerini çıkarıp XGBoost modeliyle **60 dakika sonraki Dst** hedefini tahmin eder.
- **Belirsizlik Bandı (Quantile):** Merkez tahmine ek olarak `P10` ve `P90` model bantları (quantile) işletilerek hata toleransı gösterge paneline yansıtılır.
- **Açıklanabilir YZ (XAI):** Ağaç katkılarından türetilen SHAP-benzeri açıklama ile hangi sinyallerin tahmini fırtınalı yöne ittiği jüri ekranında imzalanmış bar grafikleriyle gösterilir.
- **Doğrulama:** Gelişmiş veri ile modelin geçmiş `Dst MAE`, quantile bant kapsama oranı aktif olarak panelde gösterilir.

---

## 5. Dizin Yapısı

```text
helioguard/
├── engine/                      
│   ├── helioguard/
│   │   ├── app.py               # FastAPI Controller
│   │   ├── worker.py            # Uzay telemetri coroutine motoru
│   │   ├── physics_engine.py    # Uzay dinamiği matematik motoru
│   │   ├── predictor.py         # ML XGBoost modellerinin ayaklandırılması
│   │   └── training/            # OMNI telemetrilerini hazırlayan scriptler
│   ├── pyproject.toml           
│   └── tests/                   # Kapsamlı backend dogrulama sistemi
├── src/                         
│   ├── components/              # TurkeyMap, SatellitePanel vb. React bileşenleri
│   ├── hooks/                   # useHelioguardFeed, vb. API iletişim katmanı
│   ├── lib/                     # D3.js veri çevirileri ve formatlamalar
│   ├── App.tsx                  # Merkezi gösterge tablosu
│   └── styles.css               # Modern iOS-style UI (Apple product logic)
├── data/                        
│   ├── archive/                 # Geçmiş fırtınalar (Halloween 2003, Kis 2026. vb)
│   ├── cache/                   # API sınırlarına karşı Zero-Cost yerel disk önbelleği
│   ├── models/                  # Eğitilmiş .json ML modelleri
│   └── training/                # CSV formatı OMNI çalışma kağıtları
├── supabase/                    # Opsiyonel Postgres veritabanı konfigürasyonu
├── mimari.md                    # Sistem temel mimari ve akış yönergesi
└── PROJE_DETAYI.md              # Teknik dokümantasyon ve hedef kitle defteri
```

---

## 6. Kurulum ve Çalıştırma (Hızlı Başlangıç)

Proje hem modern bağımlılıklara hem de lokal zero-cost sistem mantığına dayalı olarak tasarlanmıştır. Yalnızca Python motoruna ve Node platformuna ihtiyaç duyar.

### Frontend (React Geliştirme Ekranı)
```bash
npm install
npm run dev
# localhost:5173 portunda veya Vite'in belirlediği yerel IP üzerinden React ayağa kalkar.
# .env dosyası olarak "VITE_API_BASE_URL=http://localhost:8000" ayarı ile backendi hedefler.
```

### Backend (Python 3.11+ Motoru)
```bash
cd engine
python -m venv .venv
# Windows için: .venv\Scripts\activate | MacOS/Linux için: source .venv/bin/activate
pip install -e .
uvicorn helioguard.app:app --reload --port 8000
```

### Ortam Değişkenleri
Gerekli backend değişkenleri (motor çalışırken konsolda `export` edilerek veya `.env` üzerinden girilebilir):
```env
OPERATING_MODE=live
NASA_API_KEY=DEMO_KEY     # Canlı DONKI sorguları için kendi NASA anahtarınız da girilebilir.
```
*Zero-Cost Notu: NASA, OpenSky, CelesTrak, NOAA veri kaynaklarına giden çağrılar sınırlandırma (rate limit) yaşamaması adına düzenli bir lokal arabellekten (`data/cache/live`) dağıtılır. CelesTrak 2 saat, Overpass 6 saat, DONKI (demo key var ise) 24 saat önbelleklenir. Ayrıca kalıcılık `data/helioguard.db` sqlite olarak lokal tutulur.*

---

## 7. XGBoost Model Eğitimi (Tarihsel Modelleme)

Raporun istediği gibi yalnızca gerçek tarihsel telemetri (OMNI verisi vs.) kullanılmalıdır. Workspace artık NOAA SPDF OMNI aylık ascii dosyalarını indirip eğitim CSV'sine çeviren bir araç içerir.

**Veri Seti Hazırlama:**
```bash
cd engine
python -m helioguard.training.prepare_omni
```
*Bu komutla varsayılan olarak `storm-halloween-2003.csv`, `storm-may-2024.csv`, `storm-jan-2026.csv`, `storm-feb-2026.csv` eğitim setleri arşive eklenir.*

**Model Eğitimi Başlatma:**
```bash
cd engine
helioguard-train data\training\storm-halloween-2003.csv data\training\storm-may-2024.csv data\training\storm-jan-2026.csv data\training\storm-feb-2026.csv
```
Bu komuttan sonra quantile bantlarıyla birlikte modeller `data/models/xgboost-model.json`, `xgboost-model.p10.json` ve `xgboost-model.p90.json` olarak yazılır. Tahmin motoru bu dosyaları bulunca otomatik devreye girer.

---

## 8. Testler ve Jüri "Smoke Test" Kontrolü

Jüri sunumunda veya deployment öncesinde API'yi tek komutla test etmek için özel CLI scriptleri hazırdır.

```bash
# Arşiv verisi üstünden (Backtest) alarm, ML, heatgrid, ETA senaryoları simülasyon testi
cd engine
python -m helioguard.jury_smoke_test --mode archive

# Doğrudan canlı otonom uçların ve cache fallback sistemlerinin testi
cd engine
python -m helioguard.jury_smoke_test --mode live
```
Backend'in tamamını test etmek isterseniz (compile syntax check + unit tests + archive smoke test):
```bash
cd engine
python -m helioguard.backend_test
# Canlı strict testi için: python -m helioguard.backend_test --live-only --strict-live
```

---

## 9. Hackathon Özel: Arşiv (Backtesting) Modu

Jüri değerlendirme anında Güneş **sessiz ve tehlikesiz** olabilir. Sistemin tepkiselliğini kaybetmemek ve fake veri yasaklarını delmemek adına projeye bir **"Arşiv Verisiyle Besle"** butonu eklenmiştir. 
Bu arka plan modu tetiklendiğinde motor, canlı NOAA okumayı bırakıp yerel sunucudaki `data/archive/march-2026-geomagnetic-storm/` geçmiş kasetini saniye saniye simüle etmeye başlar. Fırtına o an vuruyormuş gibi XAI katmanı, ETA sayaçları ve ısı haritaları jürinin testine kusursuz şekilde sunulur.
```

## Kurumsal API yuzeyi

Kurum entegrasyonlari icin sifir-maliyet REST yuzeyi:

- `GET /health`
- `GET /api/state`
- `POST /api/mode/{mode}`
- `GET /api/stream/terminal`
- `GET /api/webhooks/preview`

`/api/webhooks/preview`, ASELSAN, TUSAS veya TEIAS benzeri adaptorlerin kapali sistemlere aktarabilecegi ornek alarm payload'ini verir.

## Dosya yapisi

- `engine/helioguard/data_sources.py`: NOAA, DONKI, CelesTrak, Overpass ve arsiv baglantilari
- `engine/helioguard/analysis.py`: fiziksel kurallar, risk skoru, cihaz ayrisma ve SOP uretimi
- `engine/helioguard/predictor.py`: canli XGBoost ozellik cikarma ve inference
- `engine/helioguard/storage.py`: zero-cost yerel SQLite kaliciligi
- `engine/helioguard/app.py`: FastAPI API + SSE terminal akisi
- `src/`: React paneli

## Not

Canli sistem, varsayilan olarak ucretsiz NOAA, NASA, CelesTrak ve Overpass kaynaklarina baglanir; zorunlu ucretli servis yoktur. Supabase ve Mapbox ancak rapordaki orijinal topolojiyi sonradan birebir canlandirmak istenirse opsiyonel olarak eklenir.

Bilimsel ve operasyonel sinir:

- Sistem gercek resmi/veri-kokenli kaynaklari kullansa da, uretilen yerel risk skoru ve ML tahmini operasyonel resmi uyari yerine gecmez.
- Panel, tek bir kesin sayi yerine `belirsizlik araligi`, `varis penceresi` ve `guven puani` gosterecek sekilde tasarlanmistir.
- Hayat, ucus emniyeti, enerji sebekesi koruma veya hukuki yukumluluk doguran kararlar icin nihai referans olarak resmi NOAA/SWPC yayinlari ve yetkili operasyon merkezleri kullanilmalidir.
#   p u l s a r 
 
 
