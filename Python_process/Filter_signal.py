import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import scipy.signal as signal

# CẤU HÌNH HỆ THỐNG
FS = 1000  # Tần số lấy mẫu (Hz)

# CÁC HÀM XỬ LÝ TÍN HIỆU

def butter_bandpass_filter(data, lowcut, highcut, fs, order=2):
    """Bộ lọc Bandpass kỹ thuật số"""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = signal.butter(order, [low, high], btype='band')
    return signal.filtfilt(b, a, data)

def notch_filter(data, cutoff, fs, Q=30):
    """Bộ lọc Notch để loại bỏ nhiễu nguồn điện (50Hz)"""
    nyq = 0.5 * fs
    freq = cutoff / nyq
    b, a = signal.iirnotch(freq, Q)
    return signal.filtfilt(b, a, data)

def process_ecg(ecg_raw):
    """Xử lý ECG: Bandpass + Notch + Find Peaks"""
    # 1. Bandpass Filter (0.5 - 49 Hz)
    filtered = butter_bandpass_filter(ecg_raw, 0.5, 49, FS)
    
    # 2. Notch Filter (50 Hz)
    filtered = notch_filter(filtered, 50, FS)
    
    # 3. Peak Detection (R peaks)
    r_peaks, _ = signal.find_peaks(filtered, distance=FS*0.4, height=np.max(filtered)*0.6)
    
    q_points = []
    s_points = []
    window = int(0.05 * FS) 
    
    for r in r_peaks:
        # Tìm Q
        start_q = max(0, r - window)
        segment_q = filtered[start_q:r]
        if len(segment_q) > 0:
            q_points.append(start_q + np.argmin(segment_q))
        else:
            q_points.append(np.nan)
            
        # Tìm S
        end_s = min(len(filtered), r + window)
        segment_s = filtered[r:end_s]
        if len(segment_s) > 0:
            s_points.append(r + np.argmin(segment_s))
        else:
            s_points.append(np.nan)
            
    return filtered, r_peaks, np.array(q_points), np.array(s_points)

def process_ppg(ppg_raw):
    """Xử lý PPG: Bandpass + Find Systolic Peaks + Footpoints"""
    # 1. Narrow Bandpass Filter (0.1 - 5 Hz)
    filtered = butter_bandpass_filter(ppg_raw, 0.1, 5, FS)
    
    # 2. Detect Systolic Peaks
    peaks, _ = signal.find_peaks(filtered, distance=FS*0.4, height=np.mean(filtered))
    
    feet = []
    for p in peaks:
        search_window = int(0.3 * FS) 
        start_search = max(0, p - search_window)        
        segment = filtered[start_search:p]
        
        if len(segment) > 0:
            foot_idx = start_search + np.argmin(segment)
            feet.append(foot_idx)
        else:
            feet.append(np.nan)
            
    return filtered, peaks, np.array(feet)

def calculate_advanced_metrics(ecg_r, ecg_q, ppg_peaks, ppg_feet, red_raw, ir_raw):
    """
    Tính toán BPM, HRV, Crest Time và SpO2.
    """
    metrics = {}
    
    # --- 1. ECG METRICS ---
    if len(ecg_r) > 1:
        rr_intervals = np.diff(ecg_r) / FS
        metrics['BPM'] = 60 / np.mean(rr_intervals)
        metrics['HRV_SDNN'] = np.std(rr_intervals) * 1000 
        
        valid_mask = ~np.isnan(ecg_q)
        valid_r = ecg_r[valid_mask]
        valid_q = ecg_q[valid_mask]
        
        min_len = min(len(valid_r), len(valid_q))
        if min_len > 0:
            qr_vals = (valid_r[:min_len] - valid_q[:min_len]) / FS
            metrics['Avg_QR_Interval'] = np.mean(qr_vals) * 1000 
        else:
             metrics['Avg_QR_Interval'] = 0
    else:
        metrics['BPM'] = 0; metrics['HRV_SDNN'] = 0; metrics['Avg_QR_Interval'] = 0

    # --- 2. PPG METRICS (MORPHOLOGY) ---
    if len(ppg_peaks) > 0 and len(ppg_feet) > 0:
        crest_times = []
        for p, f in zip(ppg_peaks, ppg_feet):
            if not np.isnan(f):
                t = (p - f) / FS
                if t > 0: crest_times.append(t)
        
        if len(crest_times) > 0:
            metrics['Avg_Crest_Time'] = np.mean(crest_times) * 1000 
        else:
            metrics['Avg_Crest_Time'] = 0
    else:
        metrics['Avg_Crest_Time'] = 0

    # --- 3. SPO2 CALCULATION (NEW) ---
    # Tính AC và DC từ tín hiệu thô (Raw Data)
    # AC: Dùng hiệu giữa phân vị 95 và 5 để loại bỏ nhiễu gai (robust amplitude)
    ac_red = np.percentile(red_raw, 95) - np.percentile(red_raw, 5)
    dc_red = np.mean(np.abs(red_raw)) # Lấy trị tuyệt đối vì tín hiệu đầu vào đã bị đảo ngược (-df)

    ac_ir = np.percentile(ir_raw, 95) - np.percentile(ir_raw, 5)
    dc_ir = np.mean(np.abs(ir_raw))

    if dc_red > 0 and dc_ir > 0 and ac_red > 0 and ac_ir > 0:
        # Tỷ số Ratio of Ratios
        R = (ac_red / dc_red) / (ac_ir / dc_ir)
        
        # Công thức hiệu chuẩn tuyến tính: 110 - 25*R 
        spo2_val = 110 - 25 * R
        metrics['SpO2'] = np.clip(spo2_val, 0, 100) # Giới hạn 0-100%
    else:
        metrics['SpO2'] = 0

    return metrics

# CHƯƠNG TRÌNH CHÍNH
# 1. Đọc dữ liệu
try:
    df = pd.read_csv(r"..\data\test15.csv", header=0)
    df.columns = ["Timestamp", "PCG", "RED", "IR", "ECG"]
except FileNotFoundError:
    print("Không tìm thấy file CSV.")
    exit()

# 2. Chọn khoảng dữ liệu
start = 40000
end = len(df)-50000 
if end > len(df): end = len(df)

raw_ecg = df["ECG"][start:end].values
# Đảo ngược tín hiệu để đỉnh hướng lên (cho Peak Detection)
raw_red = -df["RED"][start:end].values
raw_ir  = -df["IR"][start:end].values 
x_axis = np.arange(start, end)

print("Đang xử lý tín hiệu...")

# 3. Xử lý tín hiệu
ecg_clean, r_peaks, q_points, s_points = process_ecg(raw_ecg)
ppg_clean, ppg_peaks, ppg_feet = process_ppg(raw_ir)

# 4. Tính toán chỉ số 
metrics = calculate_advanced_metrics(r_peaks, q_points, ppg_peaks, ppg_feet, raw_red, raw_ir)

print(f"=== KẾT QUẢ PHÂN TÍCH ===")
print(f"1. ECG Analysis:")
print(f"   - Heart Rate: {metrics['BPM']:.2f} BPM")
print(f"   - HRV (SDNN): {metrics['HRV_SDNN']:.2f} ms")
print(f"   - Avg Q-R Interval: {metrics['Avg_QR_Interval']:.2f} ms")
print(f"2. PPG Analysis:")
print(f"   - Avg Crest Time: {metrics['Avg_Crest_Time']:.2f} ms")
print(f"   - SpO2: {metrics['SpO2']:.2f} %")


# 5. Vẽ biểu đồ minh họa
fig, axs = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
# Cập nhật tiêu đề biểu đồ
fig.suptitle(f'BPM: {metrics["BPM"]:.1f} | SpO2: {metrics["SpO2"]:.1f}% | Crest Time: {metrics["Avg_Crest_Time"]:.1f}ms', fontsize=14, fontweight='bold')

# --- Plot 1: ECG ---
axs[0].plot(x_axis, ecg_clean, 'g-', label='Filtered ECG')
axs[0].plot(x_axis[r_peaks], ecg_clean[r_peaks], 'ro', label='R')
valid_q = ~np.isnan(q_points)
if np.any(valid_q):
    axs[0].plot(x_axis[q_points[valid_q].astype(int)], ecg_clean[q_points[valid_q].astype(int)], 'b^', label='Q')
valid_s = ~np.isnan(s_points)
if np.any(valid_s):
    axs[0].plot(x_axis[s_points[valid_s].astype(int)], ecg_clean[s_points[valid_s].astype(int)], 'kv', label='S')
axs[0].set_title("1. ECG Signal (Bandpass 0.5-49Hz + Notch 50Hz)")
axs[0].legend(loc='upper right')
axs[0].grid(True, alpha=0.5)

# --- Plot 2: PPG ---
axs[1].plot(x_axis, ppg_clean, color='purple', label='Filtered PPG (IR)')
axs[1].plot(x_axis[ppg_peaks], ppg_clean[ppg_peaks], 'ro', label='Systolic Peak')
valid_feet = ~np.isnan(ppg_feet)
if np.any(valid_feet):
    feet_idx = ppg_feet[valid_feet].astype(int)
    axs[1].plot(x_axis[feet_idx], ppg_clean[feet_idx], 'yo', markeredgecolor='k', label='Footpoint')
axs[1].set_title("2. PPG Signal (Bandpass 0.1-5Hz)")
axs[1].legend(loc='upper right')
axs[1].grid(True, alpha=0.5)

plt.tight_layout()
plt.show()