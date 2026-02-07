import serial
import time
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from scipy.signal import iirnotch, butter, filtfilt, find_peaks

# CẤU HÌNH HỆ THỐNG
SERIAL_PORT = 'COM5'       # Đổi cổng COM của bạn
BAUD_RATE = 921600         # Đảm bảo ESP32 cũng set mức này
SAMPLE_RATE = 1000         # Hz
WINDOW_SIZE = 1000 * 10    # Hiển thị 10 giây dữ liệu

# XỬ LÝ TÍN HIỆU (Signal Processing)
class SignalProcessor:
    def __init__(self, fs=1000):
        self.fs = fs
        
        # 1. ECG Filters (Bandpass 0.5-49 Hz + Notch 50 Hz)
        self.b_ecg, self.a_ecg = butter(2, [0.5, 49], btype='band', fs=fs)
        self.b_notch, self.a_notch = iirnotch(50.0, 30, fs)

        # 2. PCG Filters (Bandpass 20-400 Hz + Notch 50 Hz)
        self.b_pcg, self.a_pcg = butter(2, [20, 400], btype='band', fs=fs)

        # 3. PPG Filters (Bandpass 0.5-5 Hz cho hiển thị đẹp)
        self.b_ppg, self.a_ppg = butter(2, [0.5, 5], btype='band', fs=fs)

    def process_ecg(self, signal):
        if len(signal) < 100: return signal
        sig_notch = filtfilt(self.b_notch, self.a_notch, signal)
        return filtfilt(self.b_ecg, self.a_ecg, sig_notch)

    def process_pcg(self, signal):
        if len(signal) < 100: return signal
        sig_notch = filtfilt(self.b_notch, self.a_notch, signal)
        return filtfilt(self.b_pcg, self.a_pcg, sig_notch)

    def process_ppg(self, signal):
        if len(signal) < 100: return signal
        return filtfilt(self.b_ppg, self.a_ppg, signal)

    def calculate_vitals(self, ecg_buffer, red_buffer, ir_buffer):
        hr = 0
        spo2 = 0
        
        # --- TÍNH NHỊP TIM TỪ ECG ---
        if len(ecg_buffer) > self.fs * 2:
            clean_ecg = self.process_ecg(np.array(ecg_buffer))
            # Tìm đỉnh R
            peaks, _ = find_peaks(clean_ecg, distance=self.fs*0.5, height=np.max(clean_ecg)*0.6)
            if len(peaks) > 1:
                rr_intervals = np.diff(peaks) / self.fs
                avg_rr = np.mean(rr_intervals)
                if avg_rr > 0: hr = 60 / avg_rr

        # --- TÍNH SpO2 TỪ PPG (Dùng tín hiệu thô có thành phần DC) ---
        if len(red_buffer) > self.fs * 2:
            red_arr = np.array(list(red_buffer)[-self.fs*2:]) 
            ir_arr = np.array(list(ir_buffer)[-self.fs*2:])
            
            ac_red = np.max(red_arr) - np.min(red_arr)
            dc_red = np.mean(red_arr)
            ac_ir = np.max(ir_arr) - np.min(ir_arr)
            dc_ir = np.mean(ir_arr)

            if dc_red != 0 and dc_ir != 0:
                R = (ac_red / dc_red) / (ac_ir / dc_ir)
                spo2 = 110 - 25 * R
                spo2 = np.clip(spo2, 80, 100)

        return int(hr), int(spo2)

# SERIAL READER (THREAD)
class SerialReader:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.running = False
        self.processor = SignalProcessor(fs=SAMPLE_RATE)
        
        # Buffers
        self.ecg_buf = deque(maxlen=WINDOW_SIZE)
        self.pcg_buf = deque(maxlen=WINDOW_SIZE)
        self.red_buf = deque(maxlen=WINDOW_SIZE)
        self.ir_buf = deque(maxlen=WINDOW_SIZE)

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            print(f"Connected to {self.port} @ {self.baud}")
        except Exception as e:
            print(f"Serial Error: {e}")

    def update(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                parts = line.split(',')
                if len(parts) == 5:
                    # timestamp = int(parts[0]) 
                    pcg = int(parts[1])
                    red = int(parts[2])
                    ir  = int(parts[3])
                    ecg = int(parts[4])
                    
                    self.ecg_buf.append(ecg)
                    self.pcg_buf.append(pcg)
                    self.red_buf.append(red)
                    self.ir_buf.append(ir)
            except ValueError: pass
            except Exception: pass
    
    def close(self):
        self.running = False
        if self.ser.is_open: self.ser.close()

# VISUALIZATION (MAIN)
reader = SerialReader(SERIAL_PORT, BAUD_RATE)
reader.start()

# 1. CẤU HÌNH NỀN TRẮNG
plt.style.use('default') 

# 2. TẠO 4 HÀNG ĐỒ THỊ (ECG, PPG RED, PPG IR, PCG)
# sharex=True để đồng bộ trục thời gian
fig, (ax_ecg, ax_red, ax_ir, ax_pcg) = plt.subplots(4, 1, figsize=(12, 12), sharex=True)

# --- Đồ thị 1: ECG ---
line_ecg, = ax_ecg.plot([], [], 'g-', lw=1.2) # Màu xanh lá đậm
ax_ecg.set_title("1. Electrocardiogram (ECG)", loc='left', color='darkgreen', fontweight='bold')
ax_ecg.set_ylabel("Amplitude")
ax_ecg.grid(True, linestyle='--', alpha=0.5)
text_hr = ax_ecg.text(0.98, 0.85, 'BPM: --', transform=ax_ecg.transAxes, 
                      color='darkgreen', fontsize=14, fontweight='bold', ha='right')

# --- Đồ thị 2: PPG RED ---
line_red, = ax_red.plot([], [], 'r-', lw=1.5) # Màu đỏ
ax_red.set_title("2. PPG - RED Channel", loc='left', color='red', fontweight='bold')
ax_red.set_ylabel("Intensity")
ax_red.grid(True, linestyle='--', alpha=0.5)
text_spo2 = ax_red.text(0.98, 0.85, 'SpO2: --%', transform=ax_red.transAxes, 
                        color='red', fontsize=14, fontweight='bold', ha='right')

# --- Đồ thị 3: PPG IR (Tách riêng) ---
line_ir, = ax_ir.plot([], [], color='darkblue', lw=1.5) # Màu xanh dương đậm cho IR
ax_ir.set_title("3. PPG - IR Channel", loc='left', color='darkblue', fontweight='bold')
ax_ir.set_ylabel("Intensity")
ax_ir.grid(True, linestyle='--', alpha=0.5)

# --- Đồ thị 4: PCG ---
line_pcg, = ax_pcg.plot([], [], color='purple', lw=0.8) # Màu tím
ax_pcg.set_title("4. Phonocardiogram (PCG)", loc='left', color='purple', fontweight='bold')
ax_pcg.set_ylabel("Amplitude")
ax_pcg.set_xlabel("Time (samples)")
ax_pcg.grid(True, linestyle='--', alpha=0.5)

# Biến đếm frame
frame_count = 0 

def animate(i):
    global frame_count
    frame_count += 1
    
    # Chờ buffer có dữ liệu
    if len(reader.ecg_buf) < SAMPLE_RATE: return tuple()
    
    # Chuyển buffer sang numpy array để xử lý
    raw_ecg = np.array(reader.ecg_buf)
    raw_pcg = np.array(reader.pcg_buf)
    raw_red = np.array(reader.red_buf)
    raw_ir  = np.array(reader.ir_buf)
    
    # --- LỌC TÍN HIỆU ---
    clean_ecg = reader.processor.process_ecg(raw_ecg)
    clean_pcg = reader.processor.process_pcg(raw_pcg)
    # Lọc PPG chỉ để vẽ cho đẹp
    vis_red = reader.processor.process_ppg(raw_red)
    vis_ir  = reader.processor.process_ppg(raw_ir)

    # --- CẬP NHẬT ĐỒ THỊ ---
    x_axis = np.arange(len(clean_ecg))
    window_view = 8000 # Xem 5 giây cuối

    # Update Data
    line_ecg.set_data(x_axis, clean_ecg)
    line_red.set_data(x_axis, vis_red)
    line_ir.set_data(x_axis, vis_ir)
    line_pcg.set_data(x_axis, clean_pcg)

    # Xử lý trôi trục X (Hiệu ứng cuộn)
    current_len = len(x_axis)
    ax_ecg.set_xlim(max(0, current_len - window_view), current_len)
    
    # Auto Scale trục Y mỗi 10 frame 
    if frame_count % 10 == 0:
        # Scale ECG
        view_ecg = clean_ecg[-window_view:]
        if len(view_ecg) > 0:
            mn, mx = np.min(view_ecg), np.max(view_ecg)
            ax_ecg.set_ylim(mn - (mx-mn)*0.1, mx + (mx-mn)*0.1)
        
        # Scale PPG RED
        view_red = vis_red[-window_view:]
        if len(view_red) > 0:
            mn, mx = np.min(view_red), np.max(view_red)
            ax_red.set_ylim(mn - 500, mx + 500)

        # Scale PPG IR
        view_ir = vis_ir[-window_view:]
        if len(view_ir) > 0:
            mn, mx = np.min(view_ir), np.max(view_ir)
            ax_ir.set_ylim(mn - 500, mx + 500)
            
        # Scale PCG (Giữ cố định hoặc auto)
        ax_pcg.set_ylim(-30000, 30000) # PCG thường cố định biên độ

    # --- TÍNH TOÁN BPM / SPO2 (Mỗi 1 giây = 30 frames) ---
    if frame_count % 30 == 0:
        hr, spo2 = reader.processor.calculate_vitals(raw_ecg, raw_red, raw_ir)
        text_hr.set_text(f"BPM: {hr}")
        text_spo2.set_text(f"SpO2: {spo2}%")

    return line_ecg, line_red, line_ir, line_pcg, text_hr, text_spo2

# Chạy animation
ani = FuncAnimation(fig, animate, interval=30, blit=True)

plt.tight_layout()
plt.show()

# Đóng thread khi tắt cửa sổ
reader.close()