import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import iirnotch, filtfilt, firwin, lfilter

# --- CẤU HÌNH ---
FILE_PATH = r"..\data\test5.csv"  # Đường dẫn file của bạn
SAMPLE_RATE = 1000  # QUAN TRỌNG: Thay đổi số này đúng với thiết bị thu của bạn (ví dụ 4000, 8000...)
NOTCH_FREQ = 50.0  # Tần số điện lưới cần lọc

# --- CÁC HÀM XỬ LÝ (Lấy từ các file mẫu của bạn) ---

def apply_notch_filter(data, fs=SAMPLE_RATE, freq=NOTCH_FREQ, quality=30):
    """
    Logic từ file Notch_bef_aft.py: Loại bỏ nhiễu 50Hz
    """
    b, a = iirnotch(freq, quality, fs)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def apply_fir_lowpass(data, cutoff, fs=SAMPLE_RATE, num_taps=65):
    """
    Logic từ file FIR_coeffs.py kết hợp xử lý: Lọc bỏ tần số cao
    """
    # Tạo hệ số (như file FIR_coeffs.py)
    # num_taps nên là số lẻ để tránh dịch pha nếu dùng lfilter thường, 
    # nhưng filtfilt sẽ xử lý vấn đề pha.
    fir_coeff = firwin(num_taps, cutoff=cutoff, fs=fs)
    
    # Áp dụng bộ lọc vào dữ liệu (dùng filtfilt để không bị trễ pha)
    filtered_data = filtfilt(fir_coeff, 1.0, data)
    return filtered_data

# --- CHƯƠNG TRÌNH CHÍNH ---

# 1. Đọc dữ liệu (Logic từ Signal_plot.py)
try:
    df = pd.read_csv(FILE_PATH, header=None)
    df.columns = ["ECG", "RED", "IR", "PCG"]
    print("Đọc file thành công.")
except Exception as e:
    print(f"Lỗi đọc file: {e}")
    # Tạo dữ liệu giả lập để test nếu không có file thực
    df = pd.DataFrame(np.random.randn(2000, 4), columns=["ECG", "RED", "IR", "PCG"])

# 2. Xử lý tín hiệu
# Tạo DataFrame mới để chứa dữ liệu đã lọc
df_filtered = df.copy()

# --- Xử lý ECG ---
# Bước A: Lọc Notch 50Hz (Quan trọng cho ECG)
df_filtered["ECG"] = apply_notch_filter(df_filtered["ECG"])
# Bước B: Lọc Low-pass khoảng 100Hz (loại nhiễu cơ)
df_filtered["ECG"] = apply_fir_lowpass(df_filtered["ECG"], cutoff=100)

# --- Xử lý PPG (RED & IR) ---
# PPG cần lọc mạnh hơn, chỉ lấy tần số thấp (< 10Hz)
df_filtered["RED"] = apply_fir_lowpass(df_filtered["RED"], cutoff=5, num_taps=101)
df_filtered["IR"] = apply_fir_lowpass(df_filtered["IR"], cutoff=5, num_taps=101)

# --- Xử lý PCG (Tim phổi) ---
# PCG cần giữ lại tần số âm thanh (20-400Hz). 
# Logic FIR của bạn cutoff=450 là hợp lý.
df_filtered["PCG"] = apply_fir_lowpass(df_filtered["PCG"], cutoff=450)
# Có thể thêm Notch cho PCG nếu thấy tiếng "ù" 50Hz
df_filtered["PCG"] = apply_notch_filter(df_filtered["PCG"])


# 3. Vẽ đồ thị so sánh (Logic nâng cấp từ Signal_plot.py)
start = 100
end = 1100
x = range(start, end)

fig, axs = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

# Hàm vẽ tiện ích
def plot_compare(ax, raw, filtered, title, color_raw='lightgray', color_filt='blue'):
    ax.plot(x, raw[start:end], color=color_raw, label='Raw', alpha=0.6)
    ax.plot(x, filtered[start:end], color=color_filt, label='Filtered', linewidth=1.5)
    ax.set_title(title)
    ax.set_ylabel("Amplitude")
    ax.legend(loc='upper right')
    ax.grid(True)

# Vẽ từng kênh
plot_compare(axs[0], df["ECG"], df_filtered["ECG"], "ECG Signal (Notch 50Hz + LP 100Hz)", color_filt='orange')
plot_compare(axs[1], df["RED"], df_filtered["RED"], "PPG RED (LP 5Hz)", color_filt='red')
plot_compare(axs[2], df["IR"], df_filtered["IR"], "PPG IR (LP 5Hz)", color_filt='green')
plot_compare(axs[3], df["PCG"], df_filtered["PCG"], "PCG Signal (LP 450Hz + Notch)", color_filt='blue')

axs[3].set_xlabel("Sample Index")
plt.tight_layout()
plt.show()

# 4. Phân tích phổ sau khi lọc (Optional - Logic từ fastFourier_Trans.py)
# Bạn có thể uncomment dòng dưới để xem phổ của một kênh bất kỳ
# plt.figure()
# plt.psd(df_filtered["ECG"], Fs=SAMPLE_RATE)
# plt.title("Power Spectral Density of Filtered ECG")
# plt.show()