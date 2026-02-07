import serial
import time
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# CẤU HÌNH HỆ THỐNG
SERIAL_PORT = 'COM5'       # Đổi cổng COM của bạn
BAUD_RATE = 921600         # Đảm bảo ESP32 cũng set mức này
SAMPLE_RATE = 1000         # Hz
WINDOW_SIZE = 1000 * 5    # 5 giây dữ liệu

# ĐỌC SERIAL 
class SerialReader:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.running = False
        
        # Buffer lưu dữ liệu thô (Đã bỏ PCG)
        self.ecg_buf = deque(maxlen=WINDOW_SIZE)
        self.red_buf = deque(maxlen=WINDOW_SIZE)
        self.ir_buf = deque(maxlen=WINDOW_SIZE)

    def start(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self.update, daemon=True)
            self.thread.start()
            print(f"Connected to {self.port} (RAW MODE - NO PCG)")
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

            except ValueError: pass
            except Exception as e: print(e)
    
    def close(self):
        self.running = False
        if self.ser.is_open: self.ser.close()

# HIỂN THỊ RAW DATA
reader = SerialReader(SERIAL_PORT, BAUD_RATE)
reader.start()

# 1. CẤU HÌNH NỀN TRẮNG
plt.style.use('default') 

# 2. TẠO 3 HÀNG ĐỒ THỊ (Đã bỏ hàng PCG)
fig, (ax_ecg, ax_red, ax_ir) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
fig.suptitle('Raw Sensor Data Monitoring', fontsize=14)

# --- Đồ thị 1: ECG (RAW) ---
line_ecg, = ax_ecg.plot([], [], 'g-', lw=1.0) 
ax_ecg.set_title("1. Raw ECG Signal", loc='left', color='darkgreen', fontweight='bold')
ax_ecg.set_ylabel("ADC Value")
ax_ecg.grid(True, linestyle='--', alpha=0.5)

# --- Đồ thị 2: PPG RED (RAW) ---
line_red, = ax_red.plot([], [], 'r-', lw=1.0) 
ax_red.set_title("2. Raw RED Channel", loc='left', color='red', fontweight='bold')
ax_red.set_ylabel("Intensity")
ax_red.grid(True, linestyle='--', alpha=0.5)

# --- Đồ thị 3: PPG IR (RAW) ---
line_ir, = ax_ir.plot([], [], color='darkblue', lw=1.0) 
ax_ir.set_title("3. Raw IR Channel", loc='left', color='darkblue', fontweight='bold')
ax_ir.set_ylabel("Intensity")
ax_ir.set_xlabel("Time (samples)")
ax_ir.grid(True, linestyle='--', alpha=0.5)

frame_count = 0 

def animate(i):
    global frame_count
    frame_count += 1
    
    # Chờ buffer có dữ liệu
    if len(reader.ecg_buf) < 100: return tuple()
    
    # Chuyển buffer sang numpy array
    raw_ecg = np.array(reader.ecg_buf)
    raw_red = np.array(reader.red_buf)
    raw_ir  = np.array(reader.ir_buf)
    
    # --- CẬP NHẬT DỮ LIỆU ---
    x_axis = np.arange(len(raw_ecg))
    window_view = 5000 # Xem 5 giây cuối

    # Vẽ trực tiếp dữ liệu thô
    line_ecg.set_data(x_axis, raw_ecg)
    line_red.set_data(x_axis, raw_red)
    line_ir.set_data(x_axis, raw_ir)

    # Xử lý cuộn trục X
    current_len = len(x_axis)
    ax_ecg.set_xlim(max(0, current_len - window_view), current_len)
    
    # Auto Scale trục Y mỗi 5 frame
    if frame_count % 5 == 0:
        # Scale ECG
        view_ecg = raw_ecg[-window_view:]
        if len(view_ecg) > 0:
            mn, mx = np.min(view_ecg), np.max(view_ecg)
            margin = (mx - mn) * 0.1 if mx != mn else 100
            ax_ecg.set_ylim(mn - margin, mx + margin)
        
        # Scale PPG RED
        view_red = raw_red[-window_view:]
        if len(view_red) > 0:
            mn, mx = np.min(view_red), np.max(view_red)
            margin = (mx - mn) * 0.1 if mx != mn else 500
            ax_red.set_ylim(mn - margin, mx + margin)

        # Scale PPG IR
        view_ir = raw_ir[-window_view:]
        if len(view_ir) > 0:
            mn, mx = np.min(view_ir), np.max(view_ir)
            margin = (mx - mn) * 0.1 if mx != mn else 500
            ax_ir.set_ylim(mn - margin, mx + margin)
            
    return line_ecg, line_red, line_ir

ani = FuncAnimation(fig, animate, interval=30, blit=False)
plt.tight_layout()
plt.show()
reader.close()