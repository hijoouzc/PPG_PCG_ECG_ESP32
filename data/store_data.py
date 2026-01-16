import serial
import csv
import time
import sys

# ===== CẤU HÌNH (BẠN CHỈNH SỬA Ở ĐÂY) =====
PORT = 'COM5'          # Thay bằng cổng COM của bạn
BAUD = 115200          # Tốc độ baud của ESP32
FILENAME = "test1.csv" # Tên file lưu dữ liệu

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
    print("⚠️  Nhấn Ctrl + C để dừng chương trình.")

    # 2. Mở file CSV để ghi
    # test10.csv không có header, nên ta cũng không ghi header để giống định dạng
    with open(FILENAME, mode='w', newline='') as f:
        writer = csv.writer(f)
        
        cnt = 0
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
                            # Thứ tự từ ESP32 (sensor_init.c):
                            pcg_val = int(parts[0]) # global_inmp441_data
                            red_val = int(parts[1]) # global_red
                            ir_val  = int(parts[2]) # global_ir
                            ecg_val = int(parts[3]) # global_adc_value
                            
                            # 4. Sắp xếp lại cho giống test10.csv (ECG, RED, IR, PCG)
                            # Cột 1: ECG
                            # Cột 2: RED
                            # Cột 3: IR
                            # Cột 4: PCG
                            row_to_save = [ecg_val, red_val, ir_val, pcg_val]
                            
                            # Ghi vào file
                            writer.writerow(row_to_save)
                            
                            cnt += 1
                            if cnt % 100 == 0:
                                print(f"Đã lưu {cnt} dòng. Mẫu mới nhất: {row_to_save}")
                                
                        except ValueError:
                            continue # Bỏ qua dòng lỗi (không phải số)

        except KeyboardInterrupt:
            print(f"\n🛑 Đã dừng! Tổng cộng lưu được {cnt} dòng dữ liệu.")
        finally:
            ser.close()

if __name__ == "__main__":
    run_logger()