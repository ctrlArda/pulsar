**🚀 HELIOGUARD: MASTER SİSTEM MİMARİSİ VE TEKNİK ŞARTNAME**

## **1\. SİSTEMİN ÇALIŞMA PRENSİBİ VE ALGORİTMİK AKIŞ (ZORUNLU 5 MADDE)**

Arka planda çalışan Python otonom motoru (Worker), 7/24 API'leri dinler ve tehlike anında aşağıdaki 5 aşamalı protokolü saniyeler içinde çalıştırıp sonucu Supabase veritabanına, oradan da React arayüzüne gönderir.

### **AŞAMA 1: Fırtınayı Önceden Anlama (Erken Tespit \- Early Detection)**

Sistem tehlikeyi Dünya'ya vurmadan uzayda yakalamak zorundadır.

* **Kullanılan Gerçek Veri Kaynakları:**  
  1. NASA DONKI API (Koronal Kütle Atımı \- CME bildirimleri için)  
  2. NOAA SWPC plasma-1-day.json ve mag-1-day.json (DSCOVR/ACE L1 uydularından gelen anlık Güneş rüzgarı telemetrisi).  
* **Mühendislik Detayı (Tetikleyici Algoritma):**  
  Python scripti her 60 saniyede bir NOAA API'sini sorgular. Sistemde iki kritik eşik vardır:  
  1. **Gezegenlerarası Manyetik Alan ($B\_z$):** $B\_z$ değeri Dünya'nın manyetik alanına zıt yönde (Güneye doğru) \-10 nT (nanotesla) altına düşerse, Dünya'nın kalkanı yarılmış demektir.  
  2. **Güneş Rüzgarı Hızı:** Hız 500 km/s üzerine çıkarsa.  
     *Eğer her iki şart aynı anda gerçekleşirse, sistem "KIRMIZI ALARM: Erken Tespit Başarılı" statüsüne geçer.*

### **AŞAMA 2: Fırtına Ne Zaman Gelecek? (ETA Hesaplama \- Time of Arrival)**

Jüriye fırtınanın saati ve dakikası verilecektir.

* **Fiziksel Hesaplama Mantığı:** DSCOVR uydusu Dünya'dan tam L1 Lagrange noktasında, yani yaklaşık **1.500.000 kilometre** Güneş'e doğru uzakta park halindedir. Güneş fırtınası önce bu uyduya çarpar.  
* **Matematiksel Algoritma:**  
  $$ETA \\text{ (Saniye)} \= \\frac{1.500.000 \\text{ km}}{Anlık\\ Güneş\\ Rüzgarı\\ Hızı\\ (km/s)}$$  
* *Örnek Çalışma:* Sistem API'den canlı hızı 800 km/s olarak okudu.  
  $1.500.000 / 800 \= 1875$ saniye. Yani fırtınanın Dünya atmosferine çarpmasına tam **31 dakika 15 saniye** var.  
* **Arayüz Çıktısı:** Ekranda geriye sayan, kırmızı renkli dev bir canlı sayaç başlar. (Örn: *Çarpışmaya Son: 31:15*).

### **AŞAMA 3: Nerelere Etki Edecek? (Mikro-Bölgesel Isı Haritası)**

Hedef bölge doğrudan Türkiye, özellikle sistemin çalıştığı nokta olan **Osmaniye / Kadirli** ve Çukurova havzası baz alınarak daraltılacaktır.

* **Kullanılan Veri:** Küresel $K\_p$ indeksi (0-9 arası şiddet) ve WMM (World Magnetic Model) verileri.  
* **Mühendislik Detayı:** Türkiye orta enlem (mid-latitude) ülkesidir (Kadirli koordinatları: \~37.3° Kuzey, \~36.0° Doğu). $K\_p$ indeksi 7 ve üzerine çıktığında, "Auroral Oval" (Kutup Işıkları halkası) güneye doğru genişler.  
* Sistem, Kadirli'nin manyetik enlemini formüle sokarak yerel bir risk yüzdesi çıkarır.  
* **Arayüz Çıktısı:** Mapbox API ile ekrana Çukurova haritası gelir. Kadirli ve çevresindeki ana enerji iletim hatları (OpenStreetMap Overpass API'den çekilmiş gerçek koordinatlar) üzerinde kırmızıdan sarıya dönen canlı bir ısı haritası belirir.

### **AŞAMA 4: Hangi Cihazlar ve Sistemler Hasar Alacak? (Hardware Vulnerability)**

Sistem tehlikeyi cihaz tipine göre ayrıştırıp etiketler. Bu işlem şu 3 parametreye göre otonom yapılır:

1. **X-Ray Akısı Yüksekse (Radyo Kesintisi):**  
   * *Hasar Görecek Sistemler:* Havacılık telsizleri (VHF/HF), amatör telsizciler (Kısa dalga), gemi haberleşme sistemleri. İyonosferdeki D-katmanı yutulması nedeniyle sinyaller kaybolur.  
2. **Radyo Akısı (F10.7) ve Sürtünme Yüksekse:**  
   * *Hasar Görecek Sistemler:* Alçak Dünya Yörüngesi (LEO) uyduları (Starlink, İMECE, Göktürk). Atmosfer genleştiği için uydular yavaşlar ve irtifa kaybeder (Kessler Sendromu riski).  
3. **Jeomanyetik Sapma ($K\_p$ ve $B\_z$) Yüksekse:**  
   * *Hasar Görecek Sistemler:* Çukurova'daki akıllı tarım sistemlerinde (Traktör otonom sürüşleri) GPS/GNSS sinyallerinde 10-50 metre sapma (L-Band sintilasyonu). Ayrıca uzun yüksek gerilim hatlarına bağlı büyük trafolarda (Geomanyetik İndüklenmiş Akım \- GIC) aşırı ısınma.

### **AŞAMA 5: Alınması Gereken Önlemler (Otonom Aksiyon Protokolleri)**

Sistem hasar alacak cihazları belirledikten sonra, ilgili sektörlere **"Acil Durum Protokolü (SOP)"** önerilerini listeler.

* **Enerji Sektörü (Kadirli TEİAŞ Merkezi vb.):**  
  * "Acil Eylem: Yüksek gerilim hatlarındaki kapasitörleri devreden çıkarın."  
  * "Trafo soğutma sistemlerini tam güce alın, yük atma (load shedding) senaryolarını hazırlayın."  
* **Havacılık ve Ulaşım (Adana Şakirpaşa / Çukurova Havalimanı rotaları):**  
  * "Acil Eylem: Uçaklarda HF radyo güvenilmez durumda. Uydu haberleşmesine (SATCOM) geçin."  
  * "GPS sinyallerinde sapma (scintillation) bekleniyor. Ataletsel Seyrüsefer Sistemlerini (INS) çapraz kontrole alın."  
* **Uydu Operatörleri:**  
  * "Acil Eylem: Sürtünmeyi azaltmak için güneş panellerini atmosferik akışa paralel (edge-on) konuma getirin."  
  * "Çarpışma uyarı (Collision Avoidance) manevraları için yakıt bütçesini hazırlayın."

---

## **2\. TEKNİK VERİ BORU HATTI (DATA PIPELINE) MİMARİSİ**

Projenin teknik olarak kusursuz çalışması için kullanılacak araçlar ve katmanlar şunlardır:

### **Katman 1: Python Engine (Arka Plan Beyni)**

* **Görev:** Host edildiği sunucuda (Render veya sürekli çalışan bir yerel terminal) saniyede bir asenkron (asyncio) olarak çalışır.  
* **Bağlandığı Endpoints:**  
  * https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json  
  * https://services.swpc.noaa.gov/products/solar-wind/mag-1-day.json  
  * https://celestrak.org/NORAD/elements/gp.php?GROUP=active\&FORMAT=tle  
* **İşlem:** Gelen JSON verilerini *Pandas* ve *NumPy* ile matrix hesaplamalarına (yukarıdaki 5 aşama) sokar. Çıkan sonucu bir JSON paketi (Payload) haline getirip Supabase'e gönderir.

### **Katman 2: Supabase (Veritabanı ve Gerçek Zamanlı Dağıtım)**

PostgreSQL tabanlı veritabanında sadece iki ana tablo olacaktır:

1. **Live\_Telemetry Tablosu:** NOAA'dan gelen ham Güneş rüzgarı hızı, $B\_z$ değeri, $K\_p$ indeksi her 1 dakikada bir buraya güncellenir.  
2. **Crisis\_Alerts Tablosu:** Python motoru bir tehlike hesapladığında buraya bir satır (Tehlike Tipi, ETA, Etkilenen Cihazlar, Çözüm Önerileri) ekler (INSERT).

### **Katman 3: React Frontend (Kullanıcı ve Jüri Ekranı)**

* Supabase'in Realtime kütüphanesi ile Crisis\_Alerts tablosuna abone (subscribe) olunur.  
* Kullanıcı ekranındayken, veritabanına yeni bir tehlike satırı düştüğü milisaniye içerisinde, sayfa hiç yenilenmeden ekranda **Alarm Zilleri, Kadirli Isı Haritası ve Sayaç (ETA)** patlar.  
* **Canlı Terminal:** Ekranın sağ alt köşesinde siyah bir konsol penceresi bulunur. Arka planda saniyede bir çekilen ham NASA verileri burada matris gibi akar. Bu, jüriye "Sistemin şu an canlı verilerle yaşadığının" kanıtıdır.

---

## **3\. KESİNLİKLE UYULACAK GİZLİ HACKATHON KURALLARI**

1. **"Fake Data" Yasaktır:** Sistemdeki her değer gerçek API uçlarından gelmelidir. Arayüzde rastgele sayı üreten tek bir JavaScript fonksiyonu dahi olmayacaktır.  
2. **Sessizlik Durumu Planı (Backtesting):** 26 Mart 2026 itibarıyla Güneş aktivitesi yüksek olsa da, jüri sunumu yapılan o 5 dakika içinde Güneş tamamen sakin kalabilir (Örn: Rüzgar hızı 350 km/s, $K\_p$=1). Bu durumda sistem boş gözükmemelidir. React arayüzünde ufak bir **"Arşiv Verisiyle Besle"** butonu olacaktır. Bu buton basıldığında, Python scripti NOAA'nın canlı API'si yerine, tarihteki en büyük fırtınalardan birinin (Örn: Ekim 2003 veya Ocak 2026 S4 Fırtınası) arşivlenmiş JSON dosyasını okumaya başlayacaktır. Jüriye, *"Şu an Güneş sakin, bu yüzden sisteme tarihin en büyük fırtınasının gerçek telemetri verilerini bir video kaset gibi yüklüyoruz, bakın algoritmalarımız Kadirli'yi nasıl savunuyor"* denilecektir.  
3. **Hız ve Görsellik:** Sistem bilimsel makale gibi sıkıcı tablolar içermeyecektir. Her şey görselleştirilecektir. Kp indeksi bar grafiklerle, tehlike bölgeleri ısı haritasıyla, cihaz hasarları ikonlarla, önlemler kısa ve net "CHECKLIST" tarzında gösterilecektir.

### **Çözdüğümüz Asıl Kriz: "NOAA'nın 3 Saatlik Kör Noktası"**

Fiziksel bir gerçek var: NOAA'nın yayınladığı resmi küresel $K\_p$ indeksi (fırtına şiddeti) **her 3 saatte bir** güncellenir. Ancak saatte 1000 km hızla Dünya'ya çarpan bir Güneş fırtınasında 3 saat beklemek, uyduların düşmesi ve trafoların yanması demektir.

İşte bizim ML modelimiz tam bu kör noktayı aydınlatacak. Sistemi beklemekten kurtarıp "Gelecek Tahmincisi" (Predictive Engine) yapacağız.

---

### **HELIOGUARD ML MİMARİSİ: XGBoost Zaman Serisi Tahmincisi**

Hackathon süresi kısıtlı olduğu için, eğitilmesi günler süren hantal derin öğrenme modelleri yerine, tabular (tablo) verilerde inanılmaz hızlı ve keskin çalışan, Kaggle şampiyonlarının tercihi **XGBoost (Extreme Gradient Boosting)** regresyon modelini kullanacağız.

#### **1\. Modelin Amacı (Ne Tahmin Edecek?)**

ML modelimiz, DSCOVR uydusundan anlık olarak saniye saniye akan Güneş rüzgarı verilerini yutacak ve **"1 saat sonra Kadirli/Çukurova bölgesindeki yerel manyetik sapma şiddeti ne olacak?"** sorusunun cevabını tahmin edecek.

#### **2\. Eğitim Aşaması (Offline Training \- Kesinlikle Gerçek Veri)**

Modeli eğitmek için sahte veri (dummy data) kullanmıyoruz.

* **Veri Seti:** NASA'nın **OMNIWeb** arşivinden, özellikle 2003 (Halloween Storms), Mayıs 2024 ve Ocak 2026'daki devasa fırtınaların saniye saniye telemetri kayıtlarını CSV olarak indireceğiz (yaklaşık 10-20 yıllık gerçek tarihsel uzay verisi).  
* **Özellikler (Features \- Modelin Girdileri):**  
  * $B\_z$ (Manyetik alanın Z ekseni yönelimi \- En kritik tetikleyici)  
  * $v$ (Güneş rüzgarı hızı)  
  * $\\rho$ (Proton yoğunluğu)  
  * $T$ (Plazma sıcaklığı)  
* **Hedef Değişken (Target \- Modelin Çıktısı):** Gelecekteki $t+60$ (60 dakika sonraki) yerel jeomanyetik bozulma endeksi.

#### **3\. Canlı Çalışma Aşaması (Live Inference \- Hackathon Anı)**

Modelimizi eğitip .pkl (pickle) veya .json formatında kaydedeceğiz. Arka planda çalışan Python (FastAPI) motorumuz şu döngüye girecek:

1. Python scripti NOAA canlı API'sine bağlanır.  
2. Son 10 dakikanın $B\_z$, hız ve yoğunluk verilerini alır.  
3. Bu canlı veriyi önceden eğittiğimiz xgboost\_model.predict() fonksiyonuna sokar.  
4. Model anında çıktıyı verir: *"Şu an Güneş rüzgarı normal görünüyor ama verideki mikro dalgalanmalardan (paternlerden) dolayı Kadirli üzerindeki manyetik yük 45 dakika içinde %60 artacak\!"*  
5. Sistem bu tahmini Supabase'e yazar, React arayüzünde **"Yapay Zeka Tahmini: 45 Dakika İçinde Bölgesel Risk"** alarmı patlar.

---

### **Sistemdeki ML \+ Fizik İşbirliği**

Makine öğrenimi her şeyi tek başına yapmayacak. Algoritmik iş bölümü şöyle olacak:

* **ML Modeli:** Fırtınanın 1-2 saat sonra yeryüzünde yaratacağı *manyetik şiddeti* tahmin edecek.  
* **Fizik Formülleri (Önceki mesajda kurduğumuz sistem):** ML modelinin tahmin ettiği bu şiddeti alıp, "Bu şiddet uyduları tam olarak kaç metre düşürür?" veya "Aralığından dolayı hangi HF radyo frekanslarını keser?" hesaplamalarını yapacak.  
* *Sonuç:* Yapay Zeka öngörür, Fizik net hasarı hesaplar.

### **Yaratıcılıkta Son Nokta: "Görünmez Tehlikeyi Tespiti"**

Bazen fırtına (hız) çok düşüktür ama Güneş'in manyetik alanı ($B\_z$) aniden güneye döner. İnsan gözü veya basit if-else kodları "Hız düşük, tehlike yok" der. Ancak ML modeli, on binlerce satırlık geçmiş fırtına tecrübesine dayanarak "Bu sessizlik fırtına öncesi sessizliktir, Dünya'nın manyetik kalkanı deliniyor" diyebilir. Jüriye bu detayla gidildiğinde teknik puan tam verilir.

