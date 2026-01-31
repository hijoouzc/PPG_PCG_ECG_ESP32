import serial
import time
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from scipy.signal import iirnotch, butter, filtfilt, find_peaks

# SYSTEM CONFIGURATION
SERIAL_PORT = 'COM5'       # Set your COM 
BAUD_RATE = 921600         # Đảm bảo ESP32 cũng set mức này
SAMPLE_RATE = 1000         # Hz
WINDOW_SIZE = 1000 * 5     # 5 giây dữ liệu
FFT_WINDOW = 1024          

# Signal Processing
class SignalProcessor:
    def __init__(self, fs=1000):
        self.fs = fs
        
        # 1. ECG Filters
        # Bandpass 0.5-49 Hz + Notch 50 Hz
        self.b_ecg, self.a_ecg = butter(2, [0.5, 49], btype='band', fs=fs)
        self.b_notch, self.a_notch = iirnotch(50.0, 30, fs)

        # 2. PCG Filters
        # Bandpass 20-500 Hz + Notch 50 Hz
        self.b_pcg, self.a_pcg = butter(2, [20, 400], btype='band', fs=fs) # 500Hz là Nyquist của 1000Hz, nên giảm xuống 400 để an toàn

        # 3. PPG Filters
        # Bandpass 0.1-5 Hz (Cho việc vẽ hình dáng sóng mượt)
        self.b_ppg, self.a_ppg = butter(2, [0.5, 5], btype='band', fs=fs) # Tăng lowcut lên 0.5 để đỡ trôi

    def process_ecg(self, signal):
        if len(signal) < 100: return signal
        # Notch 50Hz -> Bandpass 0.5-49Hz
        sig_notch = filtfilt(self.b_notch, self.a_notch, signal)
        return filtfilt(self.b_ecg, self.a_ecg, sig_notch)

    def process_pcg(self, signal):
        if len(signal) < 100: return signal
        # Notch 50Hz -> Bandpass 20-500Hz
        sig_notch = filtfilt(self.b_notch, self.a_notch, signal)
        return filtfilt(self.b_pcg, self.a_pcg, sig_notch)

    def process_ppg_visualization(self, signal):
        if len(signal) < 100: return signal
        # Chỉ dùng để vẽ sóng mượt, không dùng tính SpO2 (vì mất thành phần DC)
        return filtfilt(self.b_ppg, self.a_ppg, signal)

    def calculate_vitals(self, ecg_buffer, red_buffer, ir_buffer):
        hr = 0
        spo2 = 0
        
        # TÍNH NHỊP TIM TỪ ECG (R-Peak Detection)
        if len(ecg_buffer) > self.fs * 2:
            clean_ecg = self.process_ecg(np.array(ecg_buffer))
            # Tìm đỉnh R (chiều cao tối thiểu = 60% max)
            peaks, _ = find_peaks(clean_ecg, distance=self.fs*0.5, height=np.max(clean_ecg)*0.6)
            if len(peaks) > 1:
                rr_intervals = np.diff(peaks) / self.fs # Đổi sang giây
                avg_rr = np.mean(rr_intervals)
                if avg_rr > 0:
                    hr = 60 / avg_rr

        # TÍNH SpO2 TỪ PPG
        # SpO2 cần thành phần DC, nên dùng buffer thô (chưa lọc bandpass 0.1-5Hz)
        if len(red_buffer) > self.fs * 2:
            red_arr = np.array(list(red_buffer)[-self.fs*2:]) # Lấy 2s cuối
            ir_arr = np.array(list(ir_buffer)[-self.fs*2:])
            
            # AC = Max - Min, DC = Mean
            ac_red = np.max(red_arr) - np.min(red_arr)
            dc_red = np.mean(red_arr)
            ac_ir = np.max(ir_arr) - np.min(ir_arr)
            dc_ir = np.mean(ir_arr)

            if dc_red != 0 and dc_ir != 0:
                R = (ac_red / dc_red) / (ac_ir / dc_ir)
                # Công thức thực nghiệm chuẩn: SpO2 = 110 - 25 * R
                spo2_calc = 110 - 25 * R
                spo2 = np.clip(spo2_calc, 80, 100) # Giới hạn hiển thị 80-100%

        return int(hr), int(spo2)

# SERIAL READER
class SerialReader:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.running = False
        self.processor = SignalProcessor(fs=SAMPLE_RATE)
        
        self.ecg_buf = deque(maxlen=WINDOW_SIZE)
        self.pcg_buf = deque(maxlen=WINDOW_SIZE)
        self.red_buf = deque(maxlen=WINDOW_SIZE)
        self.ir_buf = deque(maxlen=WINDOW_SIZE)
        
        self.current_hr = 0
        self.current_spo2 = 0

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            print(f"Connected to {self.port}")
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
            except Exception as e: print(e)
    
    def close(self):
        self.running = False
        if self.ser.is_open: self.ser.close()

# VISUALIZATION
reader = SerialReader(SERIAL_PORT, BAUD_RATE)
reader.start()

plt.style.use('dark_background')
fig = plt.figure(figsize=(14, 10))
gs = fig.add_gridspec(3, 2)

# 1. ECG Plot
ax_ecg = fig.add_subplot(gs[0, 0])
line_ecg, = ax_ecg.plot([], [], 'g-', lw=1.2)
ax_ecg.set_title("ECG (Filtered 0.5-49Hz)")
text_hr = ax_ecg.text(0.02, 0.9, '', transform=ax_ecg.transAxes, color='lime', fontsize=12, fontweight='bold')

# 2. PCG Plot
ax_pcg = fig.add_subplot(gs[1, 0])
line_pcg, = ax_pcg.plot([], [], 'c-', lw=0.8)
ax_pcg.set_title("PCG (Filtered 20-500Hz)")

# 3. FFT Plot
ax_fft = fig.add_subplot(gs[2, 0])
line_fft, = ax_fft.plot([], [], 'm-', lw=1)
ax_fft.set_title("PCG Spectrum")
ax_fft.set_xlabel("Frequency (Hz)")
ax_fft.set_xlim(0, 200)

# 4. PPG Plot
ax_ppg = fig.add_subplot(gs[0:2, 1])
line_red, = ax_ppg.plot([], [], 'r-', label='Red', lw=1.5)
line_ir, = ax_ppg.plot([], [], 'b-', label='IR (Filtered 0.1-5Hz)', lw=1.5, alpha=0.7)
ax_ppg.set_title("PPG Signal")
ax_ppg.legend()
text_spo2 = ax_ppg.text(0.02, 0.9, '', transform=ax_ppg.transAxes, color='white', fontsize=12, fontweight='bold')

# Biến đếm frame để không tính toán vital signs quá nhanh
frame_count = 0 

def animate(i):
    global frame_count
    frame_count += 1
    
    if len(reader.ecg_buf) < SAMPLE_RATE: return
    
    # Lấy dữ liệu từ buffer
    raw_ecg = np.array(reader.ecg_buf)
    raw_pcg = np.array(reader.pcg_buf)
    raw_red = np.array(reader.red_buf)
    raw_ir  = np.array(reader.ir_buf)
    
    # XỬ LÝ TÍN HIỆU THEO TÀI LIỆU
    # ECG: 0.5-49Hz
    clean_ecg = reader.processor.process_ecg(raw_ecg)
    
    # PCG: 20-500Hz
    clean_pcg = reader.processor.process_pcg(raw_pcg)
    
    # PPG Visualization: 0.1-5Hz
    clean_ir = reader.processor.process_ppg_visualization(raw_ir)
    clean_red = reader.processor.process_ppg_visualization(raw_red)

    # CẬP NHẬT ĐỒ THỊ
    x_axis = np.arange(len(clean_ecg))
    
    # ECG
    line_ecg.set_data(x_axis, clean_ecg)
    ax_ecg.set_xlim(max(0, len(clean_ecg)-3000), len(clean_ecg))
    ax_ecg.set_ylim(np.min(clean_ecg[-3000:]), np.max(clean_ecg[-3000:]))
    
    # PCG
    line_pcg.set_data(x_axis, clean_pcg)
    ax_pcg.set_xlim(max(0, len(clean_pcg)-3000), len(clean_pcg))
    ax_pcg.set_ylim(-30000, 30000)

    # PPG
    line_red.set_data(x_axis, clean_red)
    line_ir.set_data(x_axis, clean_ir)
    ax_ppg.set_xlim(max(0, len(clean_red)-2000), len(clean_red))
    if frame_count % 10 == 0:
        ax_ppg.set_ylim(np.min(clean_ir[-2000:]), np.max(clean_ir[-2000:]))

    # FFT (Tính trên PCG đã lọc)
    if len(clean_pcg) > 1024:
        last_seg = clean_pcg[-1024:] * np.hanning(1024)
        fft_vals = np.abs(np.fft.fft(last_seg))
        freqs = np.fft.fftfreq(1024, d=1/SAMPLE_RATE)
        line_fft.set_data(freqs[:512], fft_vals[:512])
        if frame_count % 20 == 0:
            ax_fft.set_ylim(0, np.max(fft_vals[:512]) * 1.2)

    # TÍNH TOÁN CHỈ SỐ (Mỗi 30 frames ~ 1 giây)
    if frame_count % 30 == 0:
        hr, spo2 = reader.processor.calculate_vitals(raw_ecg, raw_red, raw_ir)
        text_hr.set_text(f"Heart Rate: {hr} BPM")
        text_spo2.set_text(f"SpO2: {spo2}%")

    return line_ecg, line_pcg, line_red, line_ir, line_fft, text_hr, text_spo2

ani = FuncAnimation(fig, animate, interval=30, blit=False)
plt.tight_layout()
plt.show()
reader.close()