import serial
import csv
import time
import sys

# ===== CẤU HÌNH =====
PORT = 'COM5'
BAUD = 921600 
FILENAME = "test15.csv"

# Target: 1000Hz => 1000 micro-seconds (us) giữa các mẫu
TARGET_INTERVAL_US = 1000 

def run_logger():
    ser = None
    try:
        # Tăng timeout để tránh treo nếu mất kết nối
        ser = serial.Serial(PORT, BAUD, timeout=2)
        print(f" Connected: {PORT} @ {BAUD} ")
        time.sleep(1) # Chờ ổn định
        ser.reset_input_buffer() # Xóa dữ liệu rác ban đầu
    except Exception as e:
        print(f"!!! CONNECTION ERROR: {e}")
        sys.exit(1)

    print(f"Writing data to file: {FILENAME}")
    print("Press Ctrl+C to stop the program...")
    with open(FILENAME, mode='w', newline='') as f:
        writer = csv.writer(f)
        
        # Ghi Header cho file CSV (Khớp với printf trong C)
        # C Code: printf("%lld,%d,%lu,%lu,%d\n", timestamp, pcg, red, ir, ecg);
        writer.writerow(["Timestamp", "PCG", "RED", "IR", "ECG"])

        sample_count = 0
        total_lost_samples = 0
        last_esp_ts = None
        start_time = time.time()

        try:
            while True:
                # Đọc 1 dòng từ Serial
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                except serial.SerialException:
                    print("Serial Disconnected!")
                    break

                if not line:
                    continue

                parts = line.split(',')

                # Kiểm tra đủ 5 cột dữ liệu (Timestamp, PCG, Red, IR, ECG)
                if len(parts) != 5:
                    # In ra dòng lỗi để debug nếu cần (hoặc bỏ qua)
                    print(f"Format error: {line}")
                    continue

                try:
                    # Parse dữ liệu
                    esp_ts  = int(parts[0]) # Timestamp từ ESP32 (micro-seconds)
                    pcg_val = int(parts[1])
                    red_val = int(parts[2])
                    ir_val  = int(parts[3])
                    ecg_val = int(parts[4])
                except ValueError:
                    continue

                #  KIỂM TRA MẤT MẪU (Dựa trên Timestamp ESP32) 
                if last_esp_ts is not None:
                    # Tính khoảng cách thời gian giữa 2 mẫu liên tiếp
                    delta_us = esp_ts - last_esp_ts
                    
                    # Nếu khoảng cách lớn hơn 1050us (cho phép sai số 50us), coi như mất mẫu
                    # Lý thuyết: 1000us. Thực tế có thể dao động 999-1001us.
                    if delta_us > (TARGET_INTERVAL_US + 50):
                        # Tính số mẫu bị mất (làm tròn)
                        lost = int((delta_us - TARGET_INTERVAL_US) / TARGET_INTERVAL_US)
                        total_lost_samples += lost
                        # print(f"!!! WARNING: Lost {lost} samples (Delta: {delta_us}us)")

                last_esp_ts = esp_ts

                # GHI DỮ LIỆU
                writer.writerow([esp_ts, pcg_val, red_val, ir_val, ecg_val])
                sample_count += 1

                # Hiển thị trạng thái mỗi 1000 mẫu (1 giây)
                if sample_count % 1000 == 0:
                    elapsed = time.time() - start_time
                    fps = sample_count / elapsed
                    print(f"Time: {elapsed:.1f}s | Mau: {sample_count} | Lost: {total_lost_samples} | Speed: {fps:.1f} Hz")

        except KeyboardInterrupt:
            print(f"\n Stopping data logger...")
            print(f"Total samples collected: {sample_count}")
            print(f"Total samples lost: {total_lost_samples}")
            if sample_count > 0:
                percent_loss = (total_lost_samples / (sample_count + total_lost_samples)) * 100
                print(f"Packet loss rate: {percent_loss:.2f}%")
            
        finally:
            if ser and ser.is_open:
                ser.close()
                print("Serial port closed.")

if __name__ == "__main__":
    run_logger()