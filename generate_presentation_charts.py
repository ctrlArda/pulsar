import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# Apple-Vari Premium Karanlık Tema Ayarları
COLOR_BG = "#1C1C1E"
COLOR_FG = "#F2F2F7"
COLOR_ACCENT = "#0A84FF"
COLOR_WARNING = "#FF453A"
COLOR_SUCCESS = "#30D158"
COLOR_MUTED = "#8E8E93"

plt.rcParams['figure.facecolor'] = COLOR_BG
plt.rcParams['axes.facecolor'] = COLOR_BG
plt.rcParams['axes.edgecolor'] = '#3A3A3C'
plt.rcParams['text.color'] = COLOR_FG
plt.rcParams['axes.labelcolor'] = COLOR_MUTED
plt.rcParams['xtick.color'] = COLOR_MUTED
plt.rcParams['ytick.color'] = COLOR_MUTED
plt.rcParams['grid.color'] = '#3A3A3C'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.5
plt.rcParams['font.family'] = 'sans-serif'

# 1. Sentetik Fırtına Verisi (Zaman serisi: T-0 CME Çarpma anı)
t = np.linspace(-12, 12, 100) # -12 saatten +12 saate

# Güneş Rüzgarı Hızı (Vsw) ve Yoğunluğu (N)
v_sw = np.where(t < 0, 400 + np.random.normal(0, 10, 100), 750 + 150*np.exp(-t/4) + np.random.normal(0, 20, 100))
n_ions = np.where(t < 0, 5 + np.random.normal(0, 1, 100), 25 + 10*np.exp(-t/2) + np.random.normal(0, 2, 100))

# Dinamik Basınç (Pd) = 1.6726e-6 * N * Vsw^2
p_d = 1.6726e-6 * n_ions * (v_sw**2)

# Dst Index (Jeomanyetik Fırtına Şiddeti) - Burton Modeli Yaklaşımı
dst = np.where(t < 0, -10 + np.random.normal(0, 2, 100), -120 - 150*np.sin(t*np.pi/12) * np.exp(-t/6) + np.random.normal(0, 3, 100))

# XGBoost GIC Risk Tahminleri (kV/km)
gic_p50 = np.where(t < 0, 0.5, 4.5 * np.exp(-t/3) * np.sin(t))
gic_p50 = np.abs(gic_p50) + np.random.normal(0, 0.2, 100)
gic_p90 = gic_p50 * 1.4 + 0.5
gic_p10 = gic_p50 * 0.7 - 0.2
gic_p10 = np.maximum(gic_p10, 0)

# Grafik 1: Kinetik Şok ve Dst Çöküşü
fig, ax1 = plt.subplots(figsize=(10, 5), dpi=300)
ax2 = ax1.twinx()

line1 = ax1.plot(t, p_d, color=COLOR_WARNING, linewidth=2.5, label='Dinamik Basınç (nPa) - $P_d$')
ax1.fill_between(t, p_d, alpha=0.1, color=COLOR_WARNING)
line2 = ax2.plot(t, dst, color=COLOR_ACCENT, linewidth=2.5, linestyle='-', label='Dst İndeksi (nT)')

ax1.set_xlabel("Zaman (T-0: CME Çarpışma Anı) [Saat]")
ax1.set_ylabel("Dinamik Basınç (nPa)", color=COLOR_WARNING, fontweight='bold')
ax2.set_ylabel("Dst İndeksi (nT)", color=COLOR_ACCENT, fontweight='bold')
ax1.grid(True)
plt.title("Helioguard: CME Etki Öncesi ve Sonrası Kinetik/Manyetik Dalgalanma", pad=20, color=COLOR_FG, fontweight='bold')

# Legend
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper left', frameon=True, facecolor='#2C2C2E', edgecolor='#3A3A3C')

plt.tight_layout()
plt.savefig('sunum_grafik_1_kinetik_dst.png', transparent=False)
plt.close()

# Grafik 2: XGBoost GIC Risk Kantilleri (p10, p50, p90)
fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

ax.plot(t, gic_p50, color=COLOR_SUCCESS, linewidth=2, label='XGBoost GIC Medyan Beklenti (p50)')
ax.plot(t, gic_p90, color=COLOR_WARNING, linewidth=1, linestyle='--', label='Kötü Senaryo (p90)')
ax.plot(t, gic_p10, color=COLOR_ACCENT, linewidth=1, linestyle=':', label='İyimser Senaryo (p10)')

ax.fill_between(t, gic_p10, gic_p90, color=COLOR_SUCCESS, alpha=0.15, label='Risk Güven Aralığı')

ax.set_xlabel("Zaman (T-0: CME Çarpışma Anı) [Saat]")
ax.set_ylabel("Şebeke İndüklenen Akım Voltajı (V/km)")
ax.set_title("Makine Öğrenimi: Trafo Merkezi GIC (Geomagnetically Induced Current) Risk Bandı", pad=20, fontweight='bold')
ax.grid(True)
ax.legend(loc='upper right', frameon=True, facecolor='#2C2C2E', edgecolor='#3A3A3C')

plt.tight_layout()
plt.savefig('sunum_grafik_2_xgboost_gic.png', transparent=False)
plt.close()

print("Grafikler başarıyla oluşturuldu: 'sunum_grafik_1_kinetik_dst.png' ve 'sunum_grafik_2_xgboost_gic.png'")
