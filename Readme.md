# NT106 - Delta Chat với Load Balancer Tự Code

## 🎯 Giới Thiệu

Ứng dụng chat với **Load Balancer tự code 100%** (KHÔNG dùng Nginx/HAProxy) để đạt điểm cao theo yêu cầu giáo viên.

**Đặc điểm:**
- ✅ Custom Load Balancer (414 lines Python)
- ✅ Weighted Round-Robin Algorithm (3:2:1)
- ✅ Health Check System (mỗi 5 giây)
- ✅ Sticky Sessions (IP-based)
- ✅ TCP + HTTP Load Balancing
- ✅ E2EE Encryption (ECDH + AES-GCM-256)
- ✅ Real-time messaging (SocketIO)

---

## 📋 Yêu Cầu Hệ Thống

- Python 3.12+
- Linux/WSL
- Các thư viện trong `requirements.txt`

---

## 🚀 Cách Chạy Ứng Dụng

### **Bước 1: Cài đặt dependencies**

```bash
pip install -r requirements.txt
```

### **Bước 2: Khởi động cluster (Load Balancer + 3 Backend)**

```bash
python3 run_cluster.py
```

**Kết quả:**
- ✅ Load Balancer HTTP: http://localhost:8000
- ✅ Load Balancer TCP: localhost:9000
- ✅ Backend 1: http://localhost:5001
- ✅ Backend 2: http://localhost:5002
- ✅ Backend 3: http://localhost:5003

### **Bước 3: Truy cập ứng dụng**

Mở trình duyệt:
```
http://localhost:8000
```

---

## 📁 Cấu Trúc Project

```
NT106/
├── app.py                      # Flask application backend
├── run_cluster.py              # Cluster orchestrator
├── core/
│   ├── load_balancer.py        # ⭐ Custom LB (414 lines TỰ CODE)
│   ├── tcp_messenger.py        # TCP messaging
│   ├── database.py             # SQLite database
│   ├── crypto_manager.py       # E2EE encryption
│   ├── e2ee_manager.py         # E2EE key management
│   ├── s3_manager.py           # S3 file storage
│   └── admin_key_manager.py    # Admin master key
├── templates/                  # HTML templates
├── static/                     # CSS/JS files
├── requirements.txt            # Dependencies
└── REPORT.md                   # Báo cáo đồ án chi tiết
```

---

## 🎓 Cơ Chế Load Balancing

### **1. Weighted Round-Robin Algorithm**

```
weights = [3, 2, 1]  # Backend 1: 50%, Backend 2: 33%, Backend 3: 17%
```

**Cách hoạt động:**
- Request 1-3 → Backend 1
- Request 4-5 → Backend 2
- Request 6 → Backend 3
- (Lặp lại cycle)

### **2. Health Check System**

- Mỗi 5 giây: `GET /health`
- 3 lần fail → mark unhealthy
- Tự động loại backend lỗi khỏi pool

### **3. Sticky Sessions**

- Client IP → Backend mapping
- Giải quyết vấn đề session consistency

---

## 🔧 Cấu Hình Ports

| Service | Port |
|---------|------|
| Load Balancer HTTP | 8000 |
| Load Balancer TCP | 9000 |
| Backend 1 | 5001 (HTTP), 9991 (TCP) |
| Backend 2 | 5002 (HTTP), 9992 (TCP) |
| Backend 3 | 5003 (HTTP), 9993 (TCP) |

---

## 🛑 Dừng Cluster

```bash
./stop_cluster.sh
```

Hoặc thủ công:
```bash
pkill -f "run_cluster.py"
pkill -f "app.py"
```

---

## ⚠️ Troubleshooting

### **Lỗi: "Address already in use"**

```bash
# Check ports
sudo lsof -i :8000 -i :9000

# Kill processes
pkill -9 -f "python.*app.py"
pkill -9 -f "run_cluster"
```

---


## 📖 Tài Liệu Chi Tiết

Xem [REPORT.md](REPORT.md) để biết thêm chi tiết về:
- Kiến trúc hệ thống đầy đủ
- Data Flow Workflow (OSI/TCP-IP layers)
- E2EE implementation
- Load Balancer design
https://drive.google.com/drive/folders/1lK72gi-jH3zmg84ELWL_z20z34rmChaB
---


