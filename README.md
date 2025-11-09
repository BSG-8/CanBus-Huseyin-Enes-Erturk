# ⚙️ CAN Bus Anomali Tespiti ve Simülasyon Projesi

Bu proje, **CAN (Controller Area Network)** veri yolundaki trafik akışını analiz ederek **anomali tespiti** yapmayı ve çeşitli **saldırı / anomali senaryolarını simüle etmeyi** amaçlar. 🚗💻
Amaç; araç içi veya endüstriyel CAN ağlarında gözlemlenebilecek olağan dışı davranışları otomatik olarak tespit edebilmek, örnek saldırı senaryolarını yeniden üretebilmek ve savunma/analiz için görsel çıktı ve raporlar üretmektir.

---

## 🎯 Kısa Özet

**Projenin temel amacı:**

* 📊 CAN verileri üzerinde anomali tespiti için veri hazırlama, modelleme ve kural-tabanlı tespit yöntemleri geliştirmek.
* 🔄 Gerçekçi simülasyonlarla farklı saldırı/anomali senaryolarını yeniden oluşturmak (ör. sahte mesaj gönderme, tekrar gönderim/flood, ID çakışması vb.).
* 🧠 Simülasyon çıktıları (görseller, videolar, loglar) ile analiz ve dokümantasyon sağlamak.

Kullanılan başlıca teknolojiler: **Python**, veri işleme için **Pandas**, ağ analizi için **Scapy**, görselleştirme için **Matplotlib / Plotly**, sonuç raporları için **HTML / CSS**.

---

## 🗂️ Proje Yapısı

```
.
├── Anomaly Scenarios/                # Anomali senaryolarına ait veri setleri ve belgeler
│   ├── ghost-charge-simulation/     # Ghost charge senaryosuna ait veriler
│   └── <diger-senaryo>/             # Diğer senaryoların dizinleri
├── Simulations/                      # Simülasyon kodları ve çıktıları
│   ├── ghost-charge-simulation/
│   │   ├── main.py
│   │   ├── config.yaml
│   │   ├── photos/
│   │   └── videos/
│   └── <diger-simülasyon>/
├── requirements.txt
└── README.md
```

---

## 🚨 Anomali Senaryoları (Özet)

### 1. ⚡ Ghost Charge Simülasyonu

**Açıklama:** Bu senaryoda ağa sahte **şarj** mesajları (örneğin batarya/şarj yönetim sistemine ait CAN ID'leri taklit eden paketler) gönderilir. Amaç, ilgili alıcıların bu sahte mesajlara nasıl tepki verdiğini (örneğin yanlış durum güncellemesi, alarm üretimi, tüketim anomalileri) gözlemlemektir.
**Hedef:** Sahte mesajların sistem üzerinde yarattığı etkileri ve tespit edilme olasılıklarını incelemek.

📸 **Simülasyon Fotoğrafları:**

![Ghost Charge 1](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/photos/normal_graphic.png)
![Ghost Charge 2](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/photos/normal_logs.png)
![Ghost Charge 3](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/photos/with_attack_graphics.png)
![Ghost Charge 4](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/photos/with_attack_graphics_1.png)
![Ghost Charge 5](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/photos/with_attack_logs.png)

🎥 **Simülasyon Videosu:**

[Ghost Charge Simulation Video (MP4)](https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk/blob/main/Simulations/ghost-charge-simulation/videos/with_ui.mp4)

---

---

## 🧰 Kullanılan Teknolojiler / İstatistikler

* 🐍 **Python** — %54.7: Simülasyonlar, veri analizi, anomali tespiti algoritmaları.
* 🌐 **HTML / CSS** — %45.3: Raporlama ve sonuçların görselleştirilmesi.

---

## 🚀 Başlarken (Getting Started)

### 🔧 Gereksinimler

* Python 3.8+ (veya projede belirtilen sürüm)
* Sanal ortam oluşturulması önerilir (venv / conda)

### ⚙️ Kurulum

```bash
# Repoyu klonlayın
git clone https://github.com/BSG-8/CanBus-Huseyin-Enes-Erturk.git
cd CanBus-Huseyin-Enes-Erturk

# (Opsiyonel) sanal ortam oluşturun
python -m venv venv
source venv/bin/activate    # Linux / macOS
# venv\Scripts\activate     # Windows

# Gerekli paketleri yükleyin
pip install -r requirements.txt
```

### ▶️ Simülasyonu Çalıştırma (Örnek)

Ghost Charge simülasyonunu çalıştırmak için:

```bash
python Simulations/ghost-charge-simulation/main.py
```

Konfigürasyon dosyası (`config.yaml`) üzerinden parametreleri (ör. paket gönderim hızı, hedef CAN ID'ler, log düzeyi) değiştirebilirsiniz.

---

## 📊 Çıktılar ve Analiz

* Simülasyon çalıştırıldığında `Simulations/<senaryo>/outputs/` altında log dosyaları, CSV veriler, görseller ve kısa HTML raporları oluşturulur.
* Anomali tespit sonuçları hem kural tabanlı hem de istatistiksel/model tabanlı yöntemlerle değerlendirilir.

---

## 👨‍💻 Katkıda Bulunanlar

* **Hüseyin Enes Ertürk** — Geliştirici — BSG-8

---

---

## ⚠️ İpuçları / Güvenlik Notları

* CAN ağı üzerinde gerçek cihazlara karşı test yapmadan önce her zaman izniniz olduğundan emin olun. ⚡
* Gerçek araç/cihaz ağlarına zarar verebilecek gönderimler yapmayın. 🚫
* Sadece **simülasyon ortamlarında** (ör. softCAN, sanal ağ) testler gerçekleştirin. 🧪
