import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import scipy.signal as signal

# CẤU HÌNH HỆ THỐNG
FS = 1000  # Sample Rate (Hz)

# CÁC HÀM XỬ LÝ TÍN HIỆU
def process_ecg(data):
    """Lọc nhiễu ECG (Bandpass 0.5-50Hz)"""
    nyquist = 0.5 * FS
    low = 0.5 / nyquist
    high = 50.0 / nyquist
    b, a = signal.butter(1, [low, high], btype='band')
    return signal.filtfilt(b, a, data)

def calculate_vitals(ecg_segment, red_segment, ir_segment):
    """Tính BPM và SpO2 """
    hr = 0.0
    spo2 = 0.0

    # --- 1. TÍNH BPM TỪ ECG ---
    clean_ecg = process_ecg(ecg_segment)
    # Tìm đỉnh R
    peaks, _ = signal.find_peaks(clean_ecg, distance=FS*0.4, height=np.max(clean_ecg)*0.5)
    
    if len(peaks) > 1:
        rr_intervals = np.diff(peaks) / FS
        avg_rr = np.mean(rr_intervals)
        if avg_rr > 0:
            hr = 60 / avg_rr

    # --- 2. TÍNH SpO2 TỪ PPG ---
    red_arr = np.array(red_segment, dtype=float)
    ir_arr = np.array(ir_segment, dtype=float)

    # Tính AC/DC
    ac_red = np.percentile(red_arr, 95) - np.percentile(red_arr, 5)
    dc_red = np.mean(red_arr)
    ac_ir = np.percentile(ir_arr, 95) - np.percentile(ir_arr, 5)
    dc_ir = np.mean(ir_arr)

    if dc_red != 0 and dc_ir != 0 and ac_red > 0 and ac_ir > 0:
        R_ratio = (ac_red / dc_red) / (ac_ir / dc_ir)
        spo2_calc = 104 - 17 * R_ratio
        spo2 = np.clip(spo2_calc, 0, 100)
    
    return round(hr, 2), round(spo2, 2)

# CHƯƠNG TRÌNH CHÍNH
# 1. Đọc dữ liệu
try:
    df = pd.read_csv(r"..\data\test14.csv", header=0)
    # Vẫn cần map đủ cột để đọc đúng dữ liệu, dù không vẽ PCG
    df.columns = ["Timestamp", "PCG", "RED", "IR", "ECG"]
except FileNotFoundError:
    print("Không tìm thấy file CSV.")
    exit()

# 2. Chọn khoảng dữ liệu
start = 80000
end = 90000
if end > len(df): end = len(df)

ecg_data = df["ECG"][start:end].values
red_data = df["RED"][start:end].values
ir_data  = df["IR"][start:end].values
x_axis = range(start, end)

# 3. Tính toán
bpm_val, spo2_val = calculate_vitals(ecg_data, red_data, ir_data)
print(f"Kết quả: BPM={bpm_val}, SpO2={spo2_val}%")

ecg_data = process_ecg(ecg_data)
# 4. Vẽ biểu đồ (Chỉ 3 hàng: ECG, RED, IR)
fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
fig.suptitle(f'Avg BPM: {bpm_val} | Avg SpO2: {spo2_val}%', fontsize=16, color='darkgreen', fontweight='bold')

# --- Đồ thị 1: ECG ---
axs[0].plot(x_axis, ecg_data, color='green')
axs[0].set_title(f"1. ECG Signal", loc='left', fontweight='bold')
axs[0].set_ylabel("Amplitude")
axs[0].grid(True, linestyle='--', alpha=0.6)

# --- Đồ thị 2: PPG RED ---
axs[1].plot(x_axis, red_data, color='red')
axs[1].set_title("2. PPG RED Signal", loc='left', fontweight='bold')
axs[1].set_ylabel("Amplitude")
axs[1].grid(True, linestyle='--', alpha=0.6)

# --- Đồ thị 3: PPG IR ---
axs[2].plot(x_axis, ir_data, color='darkblue')
axs[2].set_title(f"3. PPG IR Signal", loc='left', fontweight='bold')
axs[2].set_xlabel("Sample Index")
axs[2].set_ylabel("Amplitude")
axs[2].grid(True, linestyle='--', alpha=0.6)

plt.tight_layout()
plt.show()