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
WINDOW_SIZE = 1000 * 10    # Buffer lưu 10 giây dữ liệu
DISPLAY_SECONDS = 5        # Số giây hiển thị trên màn hình

# XỬ LÝ TÍN HIỆU (Signal Processing)
class SignalProcessor:
    def __init__(self, fs=1000):
        self.fs = fs
        
    def butter_bandpass_filter(self, data, lowcut, highcut, order=2):
        """Bộ lọc Bandpass chuẩn"""
        nyquist = 0.5 * self.fs
        low = lowcut / nyquist
        high = highcut / nyquist
        b, a = butter(order, [low, high], btype='band')
        return filtfilt(b, a, data)

    def notch_filter(self, data, freq=50.0, quality=30.0):
        """Bộ lọc Notch cắt nhiễu 50Hz"""
        b, a = iirnotch(freq, quality, self.fs)
        return filtfilt(b, a, data)

    def process_ecg(self, raw_ecg):
        """
        Xử lý ECG: Bandpass 0.5-49Hz + Notch 50Hz
        """
        if len(raw_ecg) < self.fs: return raw_ecg
        try:
            # 1. Band-pass: 0.5 - 49 Hz
            sig = self.butter_bandpass_filter(raw_ecg, 0.5, 49.0)
            # 2. Notch: 50 Hz
            sig = self.notch_filter(sig, 50.0)
            return sig
        except:
            return raw_ecg

    def process_ppg(self, raw_ppg):
        if len(raw_ppg) < self.fs: return raw_ppg
        try:
            # 1. Đảo ngược tín hiệu
            sig_inverted = -1 * np.array(raw_ppg)
            
            # 2. Band-pass: 0.1 - 5 Hz (Làm mượt sóng)
            sig = self.butter_bandpass_filter(sig_inverted, 0.1, 5.0, order=2)
            return sig
        except:
            return raw_ppg

    def calculate_vitals(self, ecg_buffer, red_buffer, ir_buffer):
        """
        Tính BPM và SpO2
        """
        bpm = 0.0
        spo2 = 0.0
        
        # Lấy dữ liệu 3 giây gần nhất để tính toán
        calc_window = self.fs * 3
        
        # --- 1. TÍNH BPM TỪ ECG ---
        if len(ecg_buffer) > calc_window:
            raw_ecg_segment = np.array(list(ecg_buffer)[-calc_window:])
            clean_ecg = self.process_ecg(raw_ecg_segment)
            
            # Tìm đỉnh R
            peaks, _ = find_peaks(clean_ecg, distance=self.fs*0.4, height=np.max(clean_ecg)*0.5)
            
            if len(peaks) > 1:
                rr_intervals = np.diff(peaks) / self.fs
                avg_rr = np.mean(rr_intervals)
                if avg_rr > 0: 
                    bpm = 60 / avg_rr

        # --- 2. TÍNH SpO2 TỪ PPG ---
        # Lưu ý: Tính SpO2 cần dùng tín hiệu thô (hoặc đảo ngược) nhưng KHÔNG dùng bộ lọc High-pass mạnh
        # vì sẽ mất thành phần DC. Ta dùng tín hiệu thô đảo ngược.
        if len(red_buffer) > calc_window:
            # Lấy dữ liệu và đảo ngược để đỉnh hướng lên
            red_arr = -1 * np.array(list(red_buffer)[-calc_window:]) 
            ir_arr  = -1 * np.array(list(ir_buffer)[-calc_window:])
            
            # Tính AC và DC
            # AC: Khoảng cách giữa đỉnh cao nhất và thấp nhất (dùng percentile để lọc nhiễu)
            ac_red = np.percentile(red_arr, 95) - np.percentile(red_arr, 5)
            dc_red = np.mean(red_arr)
            
            ac_ir = np.percentile(ir_arr, 95) - np.percentile(ir_arr, 5)
            dc_ir = np.mean(ir_arr)

            # Tính R và SpO2
            if dc_red != 0 and dc_ir != 0 and ac_red > 10 and ac_ir > 10:
                R_ratio = (ac_red / dc_red) / (ac_ir / dc_ir)
                spo2_calc = 104 - 17 * R_ratio
                spo2 = np.clip(spo2_calc, 60, 100)
            else:
                spo2 = 0.0

        return round(bpm, 2), round(spo2, 2)

# SERIAL READER (THREAD)
class SerialReader:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.running = False
        self.processor = SignalProcessor(fs=SAMPLE_RATE)
        
        # Buffers
        self.ecg_buf = deque(maxlen=WINDOW_SIZE)
        self.red_buf = deque(maxlen=WINDOW_SIZE)
        self.ir_buf = deque(maxlen=WINDOW_SIZE)

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            print(f"Connected to {self.port} (REALTIME PROCESSING)")
        except Exception as e:
            print(f"Serial Error: {e}")

    def update(self):
        while self.running:
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                parts = line.split(',')
                
                # Format: timestamp, pcg, red, ir, ecg
                if len(parts) >= 5:
                    red = int(parts[2])
                    ir  = int(parts[3])
                    ecg = int(parts[4])
                    
                    self.ecg_buf.append(ecg)
                    self.red_buf.append(red)
                    self.ir_buf.append(ir)
            except: pass
    
    def close(self):
        self.running = False
        if self.ser.is_open: self.ser.close()

# VISUALIZATION
reader = SerialReader(SERIAL_PORT, BAUD_RATE)
reader.start()

plt.style.use('default') 
fig, (ax_ecg, ax_red, ax_ir) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
fig.suptitle('REAL-TIME SIGNAL PROCESSING', fontsize=16, fontweight='bold')

# --- 1. ECG ---
line_ecg, = ax_ecg.plot([], [], 'g-', lw=1.2)
ax_ecg.set_title("1. ECG (Filtered: 0.5-49Hz + Notch)", loc='left', color='darkgreen', fontweight='bold')
ax_ecg.set_ylabel("Amplitude")
ax_ecg.grid(True, linestyle='--', alpha=0.5)
text_bpm = ax_ecg.text(0.98, 0.85, 'BPM: --', transform=ax_ecg.transAxes, 
                      color='darkgreen', fontsize=14, fontweight='bold', ha='right')

# --- 2. PPG RED ---
line_red, = ax_red.plot([], [], 'r-', lw=1.5)
ax_red.set_title("2. PPG RED (Filtered: 0.1-5Hz)", loc='left', color='red', fontweight='bold')
ax_red.set_ylabel("Intensity")
ax_red.grid(True, linestyle='--', alpha=0.5)

# --- 3. PPG IR ---
line_ir, = ax_ir.plot([], [], color='darkblue', lw=1.5)
ax_ir.set_title("3. PPG IR (Filtered: 0.1-5Hz)", loc='left', color='darkblue', fontweight='bold')
ax_ir.set_xlabel("Time (samples)")
ax_ir.set_ylabel("Intensity")
ax_ir.grid(True, linestyle='--', alpha=0.5)
text_spo2 = ax_ir.text(0.98, 0.85, 'SpO2: --%', transform=ax_ir.transAxes, 
                        color='darkblue', fontsize=14, fontweight='bold', ha='right')

frame_count = 0 

def animate(i):
    global frame_count
    frame_count += 1
    
    if len(reader.ecg_buf) < SAMPLE_RATE: return tuple()
    
    # Chỉ lấy dữ liệu trong cửa sổ hiển thị để xử lý (tối ưu tốc độ)
    display_len = SAMPLE_RATE * DISPLAY_SECONDS 
    current_len = len(reader.ecg_buf)
    if display_len > current_len: display_len = current_len
    
    # Lấy dữ liệu thô từ buffer
    raw_ecg = np.array(list(reader.ecg_buf)[-display_len:])
    raw_red = np.array(list(reader.red_buf)[-display_len:])
    raw_ir  = np.array(list(reader.ir_buf)[-display_len:])
    
    # --- XỬ LÝ TÍN HIỆU ---
    clean_ecg = reader.processor.process_ecg(raw_ecg)
    vis_red   = reader.processor.process_ppg(raw_red)
    vis_ir    = reader.processor.process_ppg(raw_ir)

    # --- VẼ ĐỒ THỊ ---
    # Down-sample nếu dữ liệu quá nhiều (vẽ mỗi điểm thứ 2)
    step = 2 if len(clean_ecg) > 2000 else 1
    x_axis = np.arange(len(clean_ecg))[::step]
    
    line_ecg.set_data(x_axis, clean_ecg[::step])
    line_red.set_data(x_axis, vis_red[::step])
    line_ir.set_data(x_axis, vis_ir[::step])

    ax_ecg.set_xlim(0, len(clean_ecg))
    
    # --- AUTO SCALE TRỤC Y (Chạy mỗi 10 frame) ---
    if frame_count % 10 == 0:
        # Scale ECG
        if len(clean_ecg) > 0:
            mn, mx = np.min(clean_ecg), np.max(clean_ecg)
            margin = (mx - mn) * 0.1
            ax_ecg.set_ylim(mn - margin, mx + margin)
        
        # Scale PPG (dùng vis_red đã đảo ngược)
        if len(vis_red) > 0:
            mn, mx = np.min(vis_red), np.max(vis_red)
            margin = (mx - mn) * 0.1
            ax_red.set_ylim(mn - margin, mx + margin)
            
        if len(vis_ir) > 0:
            mn, mx = np.min(vis_ir), np.max(vis_ir)
            margin = (mx - mn) * 0.1
            ax_ir.set_ylim(mn - margin, mx + margin)

    # --- TÍNH TOÁN BPM & SpO2 (Chạy mỗi 30 frame ~ 1 giây) ---
    if frame_count % 30 == 0:
        bpm_val, spo2_val = reader.processor.calculate_vitals(
            reader.ecg_buf, reader.red_buf, reader.ir_buf
        )
        text_bpm.set_text(f"BPM: {bpm_val}")
        text_spo2.set_text(f"SpO2: {spo2_val}%")

    return line_ecg, line_red, line_ir, text_bpm, text_spo2

ani = FuncAnimation(fig, animate, interval=30, blit=True)
plt.tight_layout()
plt.show()

reader.close()