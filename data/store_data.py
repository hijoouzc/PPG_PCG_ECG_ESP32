import serial
import csv
import time
import sys

# ===== CẤU HÌNH (BẠN CHỈNH SỬA Ở ĐÂY) =====
PORT = 'COM5'          # Thay bằng cổng COM của bạn
BAUD = 921600          # Tốc độ baud của ESP32
FILENAME = "test5.csv" # Tên file lưu dữ liệu

SAMPLE_RATE = 1000      # Tần số lấy mẫu mong muốn (Hz) - Ví dụ 500Hz
EXPECTED_DT = 1000 / SAMPLE_RATE  # Khoảng thời gian mong muốn giữa 2 mẫu (ms)
# ===========================================

def run_logger():
    # 1. Kết nối Serial
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print(f"✅ Đã kết nối với {PORT}")
        time.sleep(2) # Đợi ESP khởi động
        ser.reset_input_buffer() # Xóa bộ nhớ đệm cũ
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        sys.exit()

    print(f"📝 Đang lưu dữ liệu vào {FILENAME}...")
    print(f"ℹ️  Sample Rate mong muốn: {SAMPLE_RATE} Hz (dt={EXPECTED_DT}ms)")
    print("⚠️  Nhấn Ctrl + C để dừng chương trình.")

    # 2. Mở file CSV để ghi
    with open(FILENAME, mode='w', newline='') as f:
        writer = csv.writer(f)
        
        # Viết header nếu cần (tùy chọn, hiện tại đang để trống theo code gốc)
        # writer.writerow(["Index", "Timestamp", "ECG", "RED", "IR", "PCG"])
        
        # Khởi tạo các biến đếm cho việc check sample rate
        sample_index = 0
        lost_samples = 0
        last_ts = None
        
        try:
            while True:
                # Đọc dữ liệu từ ESP32
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line:
                    parts = line.split(',')
                    
                    # Kiểm tra đủ 4 phần tử (PCG, RED, IR, ECG)
                    if len(parts) == 4:
                        try:
                            # 3. Lấy dữ liệu thô từ chuỗi
                            pcg_val = int(parts[0]) 
                            red_val = int(parts[1]) 
                            ir_val  = int(parts[2]) 
                            ecg_val = int(parts[3]) 
                            
                            # Tạo timestamp hiện tại (ms)
                            ts = int(time.time() * 1000)

                            # ---- SAMPLERATE CHECK (Code của bạn) ----
                            if last_ts is not None:
                                dt = ts - last_ts
                                # Lưu ý: Vì Python chạy trên OS không thời gian thực, 
                                # dt có thể dao động nhẹ dù ESP gửi đúng.
                                # Bạn có thể thêm sai số (tolerance) nếu cần.
                                if dt != EXPECTED_DT:
                                    missed = max(0, dt - EXPECTED_DT)
                                    # Logic đếm số mẫu mất (ước lượng theo thời gian trôi qua)
                                    # Nếu bạn muốn đếm số mẫu bị mất thực sự: num_missed = round(missed / EXPECTED_DT)
                                    lost_samples += missed 
                                    # Chỉ in cảnh báo nếu độ lệch lớn (ví dụ > 5ms) để tránh spam console
                                    if missed > 5: 
                                        print(f"[WARN] Δt={dt} ms, lost_time={missed}ms")

                            last_ts = ts
                            # -----------------------------------------

                            # 4. Ghi vào file (Cập nhật format bao gồm Index và Time)
                            # Format: [Index, Time, ECG, RED, IR, PCG]
                            # Lưu ý: Code mẫu của bạn dùng 'ppg', ở đây tôi giữ cả 'red' và 'ir'
                            row_to_save = [
                                sample_index,
                                ts,
                                ecg_val,
                                red_val,
                                ir_val,
                                pcg_val
                            ]
                            
                            writer.writerow(row_to_save)
                            
                            sample_index += 1
                            
                            # Log tiến độ mỗi 100 mẫu
                            if sample_index % 100 == 0:
                                print(f"Sample {sample_index} | Lost (ms): {lost_samples} | Data: {row_to_save}")
                                
                        except ValueError:
                            continue # Bỏ qua dòng lỗi (không phải số)

        except KeyboardInterrupt:
            print(f"\n🛑 Đã dừng! Tổng cộng lưu được {sample_index} dòng dữ liệu.")
            print(f"Tổng thời gian bị trễ (Lost ms): {lost_samples}")
        finally:
            ser.close()

if __name__ == "__main__":
    run_logger()