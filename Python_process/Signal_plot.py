import pandas as pd
import matplotlib.pyplot as plt

# Đọc dữ liệu từ file CSV không có tiêu đề
df = pd.read_csv(r"..\data\test15.csv", header=0)
df.columns = ["Timestamp","PCG","RED","IR","ECG"]  # Đặt tên cột tương ứng

# Định nghĩa khoảng cần vẽ (bạn có thể điều chỉnh)
start = 40000
end = 45000

# Tạo trục x
x = range(start, end)

# Tạo biểu đồ
fig, axs = plt.subplots(4, 1, figsize=(12, 8), sharex=True)

# ECG
axs[0].plot(x, df["ECG"][start:end], color='orange')
axs[0].set_title("ECG Signal")
axs[0].set_ylabel("Amplitude")
axs[0].grid(True)

# PPG RED
red = -df["RED"][start:end]  # Đảo ngược tín hiệu RED
axs[1].plot(x, red, color='red')
axs[1].set_title("PPG RED Signal")
axs[1].set_ylabel("Amplitude")
axs[1].grid(True)

# PPG IR
ir = -df["IR"][start:end]  # Đảo ngược tín hiệu IR
axs[2].plot(x, ir, color='green')
axs[2].set_title("PPG IR Signal")
axs[2].set_xlabel("Sample Index")
axs[2].set_ylabel("Amplitude")
axs[2].grid(True)

# PCG
axs[3].plot(x, df["PCG"][start:end], color='blue')
axs[3].set_title("PCG Signal")
axs[3].set_xlabel("Sample Index")
axs[3].set_ylabel("Amplitude")
axs[3].grid(True)

plt.tight_layout()
plt.show()