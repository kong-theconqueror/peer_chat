# Báo cáo dự án: Ứng dụng Chat Peer-to-Peer (P2P) trên mạng lưới phân tán

## 1. Tổng quan dự án

### 1.1. Mô tả
Đây là một ứng dụng **Chat Peer-to-Peer (P2P)** được xây dựng bằng **Python 3** với giao diện người dùng **PyQt5**. Ứng dụng cho phép các node (peers) độc lập trên mạng lưới phân tán kết nối, khám phá nhau và trao đổi tin nhắn thông qua định tuyến đa chặng.

### 1.2. Đặc điểm chính
- **Phân tán hoàn toàn**: Không có máy chủ trung tâm; mỗi node hoạt động độc lập
- **Định tuyến động**: Tin nhắn được định tuyến qua các node trung gian nếu không thể trực tiếp
- **Khám phá mạng**: Các node có thể tìm kiếm và phát hiện các node khác trong mạng
- **Lưu trữ dữ liệu cục bộ**: Mỗi node duy trì cơ sở dữ liệu SQLite riêng
- **Giao diện đồ họa**: Giao diện PyQt5 thân thiện người dùng

---

## 2. Kiến trúc hệ thống

### 2.1. Sơ đồ kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────┐
│           Giao diện người dùng (UI Layer)           │
│  ┌──────────────────┐        ┌──────────────────┐   │
│  │  MainWindow      │        │  ChatWindow      │   │
│  │  (Chọn node)     │        │  (Trò chuyện)    │   │
│  └──────────────────┘        └──────────────────┘   │
└─────────────────────────────────────────────────────┘
                      ↑
                      │
┌─────────────────────────────────────────────────────┐
│        Lớp quản lý (ChatManager)                    │
│  - Định tuyến tin nhắn                              │
│  - Quản lý các peer (kết nối/ngắt kết nối)          │
│  - Giao tiếp cơ sở dữ liệu                          │
└─────────────────────────────────────────────────────┘
                      ↑
            ┌─────────┼─────────┐
            │         │         │
     ┌──────▼──┐ ┌────▼─────┐ ┌─▼──────────┐
     │ Network │ │ Protocol │ │  Database  │
     │ Layer   │ │ (JSON)   │ │ (SQLite)   │
     └──────┬──┘ └──┬───────┘ └────┬───────┘
            │       │            │
    ┌───────┴───────┼────────────┘
    │       │       │
┌───▼──┐┌───▼───┐┌──▼─────────┐
│Server││Client ││ ChatDB     │
│Worker││Worker ││(messages,  │
│      ││       ││ neighbors) │
└──────┘└───────┘└────────────┘
```

### 2.2. Các thành phần chính

#### **A. Lớp UI (User Interface)**
**Vị trí**: `ui/`

| File | Mục đích |
|------|---------|
| `main_window.py` | Cửa sổ chính - chọn node, đặt tên người dùng, bắt đầu chat |
| `chat_window.py` | Cửa sổ trò chuyện - gửi/nhận tin nhắn, khám phá mạng |

**Luồng:**
1. `MainWindow`: Người dùng chọn node (A-M) từ dropdown
2. Tải cấu hình từ `config/{node}.json`
3. Người dùng nhập username (hoặc dùng mặc định)
4. Click "Start Chat" → mở `ChatWindow`

#### **B. Lớp quản lý (ChatManager)**
**Vị trí**: `core/chat_manager.py`

**Chức năng:**
- **Khởi tạo kết nối**: `init_server()` + `init_client()`
- **Xử lý tin nhắn đến**: `handle_incoming()` - phân loại loại tin nhắn (MESSAGE, FIND_NODES, FIND_ACK)
- **Định tuyến tin nhắn**: `handle_forward_msg()` - chọn neighbor tiếp theo nếu không tìm được receiver
- **Quản lý peer kích hoạt**: Danh sách những peer đang kết nối

**Key Attributes:**
```python
self.clients          # dict: peer_id → ClientWorker (kết nối đi)
self.server_clients   # list: ServerClientWorker (kết nối đến)
self.seen_messages    # set: message_id đã xử lý (chống vòng lặp)
self.active_peer      # list: peer_id đang online
self.db               # ChatDatabase instance
self.neigbors         # list: neighbor từ cấu hình
```

#### **C. Lớp mạng (Network Layer)**
**Vị trị**: `network/`

| Thành phần | Chức năng |
|------------|----------|
| **ServerWorker** | Lắng nghe cổng, chấp nhận kết nối đến từ peer khác |
| **ClientWorker** | Kết nối chủ động đến peer khác, xử lý gửi/nhận dữ liệu |
| **ServerClientWorker** | Xử lý mỗi socket kết nối đến (chạy trên thread riêng) |
| **protocol.py** | `encode_message()` / `decode_message()` - chuyển đổi JSON ↔ bytes UTF-8 |

**Mô hình Threading:**
- Mỗi worker chạy trên `QThread` riêng biệt
- Giao tiếp qua Qt signals (không dùng locks)
- Cleanup an toàn khi tắt: `worker.finished` → `thread.quit()`

#### **D. Lớp cơ sở dữ liệu (Database Layer)**
**Vị trí**: `core/db.py`

**Schema SQLite** (mỗi node có db riêng tại `db/{node}.db`):

```sql
-- Lưu trữ tin nhắn
CREATE TABLE messages (
    id VARCHAR(36),
    sender TEXT,
    receiver TEXT,
    content TEXT,
    timestamp DATETIME,
    is_sent INTEGER  -- 1=gửi, 0=nhận
)

-- Lưu thông tin neighbor
CREATE TABLE neighbor (
    peer_id TEXT,       -- UUID
    username TEXT,
    ip TEXT,
    port INTEGER,
    last_seen DATETIME,
    status INTEGER      -- 1=online, 0=offline
)
```

**API chính:**
- `save_message(sender, receiver, content, is_sent)`
- `get_conversation(user1, user2)` → danh sách tin nhắn
- `get_neighbors()` → danh sách neighbor
- `add_neighbor(peer_id, username, ip, port)`

#### **E. Giao thức tin nhắn (Protocol)**
**Vị trí**: `network/protocol.py`

**Định dạng tin nhắn JSON:**
```json
{
  "type": "MESSAGE|FIND_NODES|FIND_ACK",
  "from": "<sender_peer_id>",
  "from_n": "<sender_username>",
  "to": "<receiver_peer_id>",
  "to_n": "<receiver_username>",
  "message_id": "<uuid>",
  "content": "<payload>",
  "ttl": 5,
  "forward": "<forwarder_peer_id>",
  "timestamp": <unix_timestamp>
}
```

**Các loại tin nhắn:**
- **MESSAGE**: Tin nhắn chat thông thường
- **FIND_NODES**: Yêu cầu khám phá các node khác (flood với TTL)
- **FIND_ACK**: Phản hồi khám phá, chứa danh sách neighbor

---

## 3. Quy tắc định tuyến

### 3.1. Chống vòng lặp
- **Cơ chế**: Duy trì `ChatManager.seen_messages` (tập hợp message_id)
- Mỗi khi nhận tin nhắn:
  - Nếu `message_id` đã tồn tại → **bỏ qua**
  - Nếu mới → **thêm vào** và **xử lý**
- **TTL (Time-To-Live)**: Giảm 1 mỗi lần forward; nếu TTL = 0 → **bỏ qua**

### 3.2. Định tuyến tin nhắn
```
Nhận MESSAGE:
  ├─ Kiểm tra destination (receiver_peer_id)
  ├─ Nếu receiver là node hiện tại → Hiển thị + lưu DB
  ├─ Nếu receiver không phải → Gọi handle_forward_msg()
  │  └─ Chọn một neighbor + forward với TTL-1
  └─ Nếu TTL = 0 → DROP
```

### 3.3. Khám phá mạng (FIND_NODES)
- FIND_NODES được **flood** (gửi đến tất cả neighbor) với TTL
- Mỗi node nhận được:
  - Ghi lại nguồn (sender) trong local neighbor list
  - Gửi lại FIND_ACK chứa danh sách neighbor của nó
  - Forward FIND_NODES với TTL-1

---

## 4. Cấu hình (Configuration)

**Vị trí**: `config/{node}.json` (A-M)

**Ví dụ cấu hình (A.json):**
```json
{
  "peer_id": "<uuid>",
  "username": "UserA",
  "port": 5001,
  "neighbors": [
    {
      "peer_id": "<uuid_B>",
      "username": "UserB",
      "ip": "127.0.0.1",
      "port": 5002
    },
    ...
  ]
}
```

**Tạo dữ liệu mẫu**: Chạy `python gen_data.py`
- Sinh 13 node (A-M) với UUID ngẫu nhiên
- Tạo ma trận kết nối neighbor định sẵn
- Khởi tạo SQLite DB cho mỗi node

---

## 5. Hướng dẫn sử dụng

### 5.1. Cài đặt môi trường
```bash
# Tạo virtual environment (Windows)
python -m virtualenv .env
.env\Scripts\activate

# Cài đặt dependencies
pip install -r requirements.txt
```

### 5.2. Tạo dữ liệu mẫu
```bash
python gen_data.py
# Tạo: config/A.json - M.json + db/A.db - M.db
```

### 5.3. Chạy ứng dụng
```bash
python main.py
# Mở MainWindow
# 1. Chọn node từ dropdown (A-M)
# 2. Nhập username (hoặc giữ mặc định)
# 3. Click "Start Chat"
# 4. ChatWindow mở ra
```

### 5.4. Sử dụng ứng dụng
**Trong ChatWindow:**
- **Gửi tin nhắn**: Chọn receiver từ dropdown → Nhập nội dung → Click "Send"
- **Khám phá mạng**: Menu "Discover" → "Find Nodes" → Hiển thị danh sách peer
- **Xem lịch sử**: Tab "History" → Xem conversation với peer

---

## 6. Các tính năng đã triển khai

✅ **Hoàn thành:**
- Chọn node từ giao diện
- Cấu hình người dùng (username, cổng, neighbor)
- Bắt đầu server + client kết nối
- Gửi tin nhắn đơn giản (direct + forwarding)
- Lưu tin nhắn vào SQLite
- Khám phá mạng (FIND_NODES / FIND_ACK)
- Logging (console + panel "Logs" trong UI)
- Quản lý threading an toàn (cleanup signals)

⚠️ **Chưa triển khai đầy đủ:**
- **Mã hóa**: `crypto/encrypt.py` chỉ là stub (đảo chuỗi)
- **Key exchange**: `crypto/key_exchange.py` trống
- **Helper utils**: `utils/helper.py` chưa implement
- **Tests tự động**: `tests/` có cơ sở nhưng chưa hoàn chỉnh
- **CI/CD**: Không có pipeline tự động

---

## 8. Cấu trúc thư mục chi tiết

```
peer_chat/
├── config/              # Cấu hình node (A.json - M.json)
├── db/                  # Database SQLite (A.db - M.db)
├── core/
│   ├── chat_manager.py  # Quản lý peer + định tuyến
│   ├── db.py            # Lớp database
│   └── __init__.py
├── network/
│   ├── protocol.py      # Encode/decode JSON
│   ├── client_worker.py # ClientWorker (kết nối đi)
│   ├── server_worker.py # ServerWorker (server socket)
│   ├── server_client_worker.py # Xử lý socket đến
│   └── __init__.py
├── crypto/
│   ├── encrypt.py       # (Stub) Mã hóa
│   ├── key_exchange.py  # (Trống) Trao đổi khóa
│   └── __init__.py
├── ui/
│   ├── main_window.py   # Cửa sổ chính
│   ├── chat_window.py   # Cửa sổ trò chuyện
│   └── __init__.py
├── utils/
│   ├── config.py        # Đọc/ghi JSON config
│   ├── logger.py        # Logging
│   ├── helper.py        # (Trống) Helper functions
│   └── __init__.py
├── tests/
│   ├── test_db.py
│   ├── conftest.py
│   └── __pycache__/
├── gen_data.py          # Tạo dữ liệu mẫu
├── main.py              # Điểm vào ứng dụng
├── requirements.txt     # Dependencies
└── README.md
```

---

## 9. Hướng phát triển trong tương lai

### 9.1. Tính năng bảo mật
- [ ] Implement mã hóa end-to-end (AES-256)
- [ ] Implement key exchange (ECDH)
- [ ] Xác thực peer (digital signature)
- [ ] Quản lý certificate

### 9.2. Tính năng nâng cao
- [ ] Nhóm chat (multi-user conversation)
- [ ] Chia sẻ file qua P2P
- [ ] Voice/video call
- [ ] Message persistence + sync

### 9.3. Cải thiện hiệu năng
- [ ] Caching neighbor list
- [ ] Optimize routing (DHT - Distributed Hash Table)
- [ ] Compression tin nhắn
- [ ] Connection pooling

### 9.4. Kiểm thử & CI
- [ ] Unit tests cho `ChatManager` + protocol
- [ ] Integration tests (2+ node)
- [ ] Load testing
- [ ] GitHub Actions pipeline

---
