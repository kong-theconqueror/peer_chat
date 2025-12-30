# BÁO CÁO DEMO

## 1. TỔNG QUAN ĐỀ TÀI

Hệ thống chat ngang hàng (Peer-to-Peer Chat System - P2P Chat) là mô hình ứng dụng giao tiếp thời gian thực nơi các thiết bị người dùng kết nối trực tiếp với nhau mà không phụ thuộc vào máy chủ trung tâm, giải quyết hạn chế của mô hình Client-Server như điểm nghẽn đơn lẻ, chi phí vận hành cao và rủi ro downtime. Nhu cầu phát triển xuất phát từ sự bùng nổ ứng dụng chat (như WhatsApp, Telegram) nhưng cần mô hình tiết kiệm tài nguyên, chống kiểm duyệt.

### 1.1. Mục tiêu dự án

Xây dựng ứng dụng chat peer-to-peer (P2P) phân tán, cho phép nhiều node (máy tính) kết nối, gửi/nhận tin nhắn, khám phá lẫn nhau mà không cần máy chủ trung tâm:
- Kết nối trực tiếp giữa các peer
- Gửi và nhận tin nhắn được mã hóa
- Định tuyến tin nhắn qua nhiều node trung gian (multi-hop routing)
- Khám phá peer tự động trong mạng
- Duy trì lịch sử chat phân tán

### 1.2. Các tính năng sẽ triển khai

#### 1.2.1. Quản Lý Node 
- Chạy độc lập trên mỗi máy
- Không phụ thuộc server

#### 1.2.2. Gửi/Nhận Tin Nhắn
- Chat 1-to-1: Gửi tin tới peer được chọn
- Nhận tin: Hiển thị tin nhắn đến real-time
- Lưu DB: Lưu tin vào localStorage
- Lịch sử: Hiển thị cuộc hội thoại

#### 1.2.3. Định Tuyến và tìm kiếm
- Multi-hop routing: Forward tin qua node trung gian
- TTL & chống lặp: Tránh vòng lặp vô hạn
- Peer discovery: Tìm peer mới trong mạng (FIND_NODES)
- Cập nhật neighbor: Nhận danh sách peer từ bootstrap

#### 1.2.4. Bảo Mật
- Mã hóa tin: AES-256 encrypt payload

#### 1.2.5. Quản Lý Node và Giao Diện 
- Khởi động node: Nhập username, start node
- Giao diện UI: Dashboard hiển thị danh sách peer, chat, log, thời gian
- Xem cấu hình: Hiển thị peer ID, port, neighbor list

---

## 2. THIẾT KẾ PHẦN MỀM

### 2.1. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│                  LAYER 1: UI (PyQt5)                        │
│  MainWindow (chọn node) → ChatWindow (giao diện chat)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            LAYER 2: CORE (Quản lý & Điều phối)              │
│  ChatManager: định tuyến, khám phá, tương tác UI/Network    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────┬──────────────────────────────────┐
│  LAYER 3A: Network       │   LAYER 3B: Database             │
│ • ServerWorker           │  • ChatDatabase (SQLite)         │
│ • ClientWorker           │  • Bảng messages                 │
│ • protocol.py            │  • Bảng neighbor                 │
└──────────────────────────┴──────────────────────────────────┘
```

Giải thích kiến trúc:
- **Layer 1 (Presentation)**: Giao diện người dùng, xử lý tương tác, hiển thị dữ liệu
- **Layer 2 (Business Logic)**: Logic điều phối, định tuyến, xử lý bản tin
- **Layer 3 (Infrastructure)**: Giao tiếp mạng và lưu trữ dữ liệu

Mỗi lớp chỉ giao tiếp với lớp liền kề, đảm bảo tính module hóa và dễ bảo trì.

### 2.2. Thiết kế chi tiết các lớp

#### 2.2.1. Lớp UI (Giao diện người dùng)

**MainWindow**:
- Chức năng: Cho phép chọn node (A-M), nhập username, khởi động ChatWindow
- Thành phần: Dropdown list, text field, nút "Start Chat"
- Luồng: Load config → Khởi tạo ChatManager → Mở ChatWindow

**ChatWindow:**
- Sidebar trái:
  - Danh sách peer (neighbor)
  - Click để chọn peer chat
- Vùng chat giữa:
  - Lịch sử tin nhắn (sent bên phải, received bên trái)
  - Timestamp cho mỗi tin
  - Tự động scroll xuống khi có tin mới
- Input bar dưới:
  - Ô nhập text (QTextEdit)
  - Nút "Send" (QPushButton)
  - Gửi bằng nút "Send" (hiện chưa bind phím Enter)
- Panel log:
  - Hiển thị sự kiện: connected, disconnected, message sent/received, error
- Menu bar:
  - Discover → Find Nodes
  - Settings → Cấu hình
  - Help → Hướng dẫn

#### 2.2.2. Lớp Core - ChatManager
- Khởi tạo server & client
- Điều phối routing
- Xử lý message
- Giao tiếp database

#### 2.2.3. Lớp Network
- Mô hình kết nối:
  - Mỗi kết nối = 1 thread
  - Không block UI thread
  - Giao tiếp qua Qt signals
- Thành phần:
  - ServerWorker: lắng nghe kết nối
  - ClientWorker: kết nối chủ động
  - ServerClientWorker: xử lý socket đến

#### 2.2.4. Lớp Database
- Thiết kế phân tán:
  - SQLite riêng cho từng node
  - Không đồng bộ DB giữa các node
- Bảng chính:
  - messages
  - neighbor

### 2.3. Quy trình và giao thức

#### 2.3.1. Quy trình gửi tin nhắn (Happy Path)

```
User A (Alice):               				Network:               	  User B (Bob):
│
├─ Nhập text "Hello"
├─ Click "Send"
├─ ChatManager.send_message()
│  ├─ Tạo msg {to=B, text="Hello", ttl=5}
│  ├─ Lưu DB (is_sent=1)
│  ├─ Encode + encrypt
│  └─ ClientWorker(B).send()
│                              				├─ TCP transfer ──────────→
│                              				                          │
│                              				                          ├─ ServerClientWorker.recv()
│                              				                          ├─ Decode message
│                              				                          ├─ ChatManager.handle_incoming()
│                              				                          ├─ to==self → process
│                              				                          ├─ Lưu DB (is_sent=0)
│                              				                          └─ Hiển thị UI "Alice: Hello"

```

#### 2.3.2. Quy trình định tuyến multi-hop

Tình huống: A muốn gửi cho C nhưng không có đường trực tiếp, phải qua B:

```
Node A:                    				Node B:                    			Node C:
│
├─ send_message(to=C, "Hi")
│  ├─ Không có ClientWorker(C)
│  └─ Forward qua neighbor B
│     └─ Gửi {to=C, ttl=5, forward=A}
│                         				├─ recv() từ A
│                         				├─ message_id chưa seen → add
│                         				├─ to != self (to=C, self=B)
│                         				├─ ttl > 0 → forward
│                         				└─ Chọn neighbor C
│                         				   └─ Gửi {to=C, ttl=4, forward=B}
│                         				                           			├─ recv() từ B
│                         				                           			├─ message_id chưa seen
│                         				                           			├─ to == self (to=C, self=C)
│                         				                           			├─ Lưu DB
│                         				                           			└─ Hiển thị "A: Hi"

```

#### 2.3.3. Cơ chế chống vòng lặp

**Vấn đề:** Trong mạng P2P, tin nhắn có thể bị forward lại nhiều lần, tạo vòng lặp vô hạn.

**Giải pháp:**
1. Mỗi tin có message_id duy nhất (UUID)
2. Mỗi node giữ set seen_messages
3. Khi nhận tin:
   - Nếu message_id đã có trong set → drop
   - Nếu chưa → thêm vào set, xử lý tiếp
4. TTL giảm mỗi lần forward:
   - Nếu ttl == 0 → drop (không forward)

### 2.3.4. Luồng xử lý đa luồng (Threading Model)

```
main_thread (Qt Event Loop)
  │
  ├─ UI: MainWindow, ChatWindow
  │   └─ Signal/Slot với ChatManager
  │
  ├─ ChatManager (quản lý)
  │   ├─ Signal: message_received
  │   └─ Signal: peer_connected
  │
  ├─ ServerWorker (thread riêng)
  │   └─ Loop: accept() → tạo ServerClientWorker
  │
  ├─ ServerClientWorker_1 (thread)
  │   └─ Loop: recv → emit new_data
  │
  ├─ ServerClientWorker_2 (thread)
  │   └─ Loop: recv → emit new_data
  │
  ├─ ClientWorker_1 (thread → peer B)
  │   └─ Loop: send/recv → emit connected/new_data
  │
  └─ ClientWorker_2 (thread → peer C)
      └─ Loop: send/recv
```

**Quy tắc giao tiếp:**
- Giữa các thread: dùng Qt signal/slot (thread-safe)
- Không dùng lock/mutex trực tiếp (PyQt5 tự quản lý)
- Mọi thao tác I/O (network, DB) chạy trên thread riêng
- UI thread chỉ xử lý hiển thị, không block

---

## 3. CÀI ĐẶT VÀ TRIỂN KHAI

### 3.1. Công nghệ và thư viện

| Thành phần | Công nghệ | Ghi chú |
|-----------|----------|--------|
| Ngôn ngữ | Python 3.8+ | Dễ học, thư viện phong phú |
| Giao diện | PyQt5 | Cross-platform, event-driven tốt |
| Database | SQLite | Nhẹ, không cần server riêng |
| Mã hóa | cryptography | API đơn giản, hỗ trợ AES-256 |
| Threading | QThread (PyQt5) | Tích hợp signal/slot, thread-safe |

### 3.2. Cấu trúc thư mục

```
peer_chat/
├── config/              # Cấu hình các node
│   ├── A.json
│   ├── B.json
│   └── ...
├── db/                  # Database SQLite
│   ├── A.db
│   ├── B.db
│   └── ...
├── core/                # Logic nghiệp vụ
│   ├── __init__.py
│   ├── chat_manager.py
│   └── db.py
├── network/             # Lớp mạng
│   ├── __init__.py
│   ├── protocol.py
│   ├── server_worker.py
│   ├── server_client_worker.py
│   └── client_worker.py
├── ui/                  # Giao diện
│   ├── __init__.py
│   ├── main_window.py
│   └── chat_window.py
├── utils/               # Tiện ích
│   ├── __init__.py
│   ├── config.py
│   └── logger.py
├── crypto/              # Mã hóa (tùy chọn)
│   ├── __init__.py
│   └── encrypt.py
├── gen_data.py          # Sinh dữ liệu mẫu
├── main.py              # Điểm vào
├── requirements.txt     # Dependencies
└── README.md
```

---

## 4. HƯỚNG DẪN CHẠY DEMO

### 4.1. Chuẩn bị môi trường

#### 4.1.1. Cài đặt Python

```bash
# Kiểm tra phiên bản
python --version
# Yêu cầu: Python 3.8+
```

#### 4.1.2. Tạo môi trường ảo

```bash
cd peer_chat
python -m venv .env
```

**Windows:**
```bash
.env\Scripts\activate
```

**macOS/Linux:**
```bash
source .env/bin/activate
```

Ghi chú: nếu bạn đã dùng thư mục `.venv` trước đó thì chỉ cần thay `.env` → `.venv` trong các lệnh activate/run.

#### 4.1.3. Cài đặt hàm

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.2. Sinh dữ liệu mẫu

```bash
python gen_data.py
```

**Kết quả:**
- Tạo 13 file config: config/A.json ... config/M.json
- Tạo 13 database: db/A.db ... db/M.db

**Topology mặc định:**

Mạng được thiết kế theo ma trận kề được xác định sẵn trong `gen_data.py`.

### 4.3. Demo 1: Chạy một node

```bash
python main.py
```

**Thao tác:**
1. Chọn Node A từ dropdown
2. Nhập username: Alice
3. Nhấn "Start Chat"
4. ChatWindow hiển thị:
   - Sidebar: Neighbor của A (B, C)
   - Log: "Peer initialized. Connecting..."

### 4.4. Demo 2: Chat giữa 2 node

**Terminal 1:**
```bash
python main.py
# Chọn Node A, username "Alice"
```

**Terminal 2:**
```bash
python main.py
# Chọn Node B, username "Bob"
```

**Kịch bản:**
1. Trong ChatWindow A:
   - Click chọn B (Bob) từ sidebar
   - Nhập "Hello Bob"
   - Nhấn Send
  - Muốn quay lại broadcast: click lại đúng peer đang chọn để bỏ chọn
2. Kết quả:
   - Log A: "✓ Sent: Hello Bob to B"
   - ChatWindow B: Hiển thị "Alice: Hello Bob"
   - Log B: "✓ Received from Alice"

### 4.5. Demo 3: Định tuyến multi-hop

Lưu ý quan trọng (khớp code hiện tại):
- `send_message()` chỉ gửi 1-to-1 tới peer đang **kết nối trực tiếp** (có ClientWorker).
- Cơ chế multi-hop trong code là kiểu **forward/flood** giữa các kết nối hiện có (dựa trên TTL + seen_messages).
- Muốn A nói chuyện với C thường cần `Discover → Find Nodes` để A biết endpoint và tạo kết nối, hoặc dùng broadcast.

**Khởi động 3 node:**
- Terminal 1: Node A (Alice)
- Terminal 2: Node B (Bridge)
- Terminal 3: Node C (Charlie)

**Topology:**
- A ─── B ─── C (A không neighbor trực tiếp với C)

**Thao tác:**
1. ChatWindow A: Menu "Discover" → "Find Nodes"
2. A gửi FIND_NODES → B → C
3. C gửi FIND_ACK → B → A
4. Sidebar A cập nhật: thêm C (Charlie)
5. A gửi "Hi Charlie" → B forward → C nhận
6. Log B: "Forward message from A to C"

### 4.6. Demo 4: Chống vòng lặp

**Kịch bản:** Tạo vòng A → B → C → A

**Thao tác:**
1. A gửi tin (id=abc123, ttl=5)
2. B nhận → forward C (ttl=4)
3. C nhận → forward A (ttl=3)
4. A nhận lại: kiểm tra abc123 in seen_messages → DROP
5. Log A: "Message abc123 already processed"

---

## 5. KẾT LUẬN

Báo cáo đã trình bày phân tích yêu cầu, thiết kế phần mềm và trích dẫn các đoạn code then chốt của hệ thống chat P2P phân tán. Các tính năng chính đã được hiện thực hóa, đảm bảo tính phân tán, định tuyến động, lưu trữ cục bộ và giao diện thân thiện. Đây là nền tảng để phát triển các tính năng bảo mật, mở rộng quy mô và kiểm thử tự động trong tương lai.

---

**Phiên bản:** 1.0  
**Cập nhật:** December 2025

**Kết quả:**
	- Tạo 13 file config: config/A.json ... config/M.json
	- Tạo 13 database: db/A.db ... db/M.db

Topology mặc định:

<img width="600" height="450" alt="image" src="https://github.com/user-attachments/assets/fb97d03c-7b2e-46d1-a20d-dc1f82279703" />

#### 5.3. Demo 1: Chạy một node
```
bash
python main.py
```

**Thao tác:**

	1. Chọn Node A từ dropdown
	2. Nhập username: Alice
	3. Nhấn "Start Chat"
	4. ChatWindow hiển thị:
		- Sidebar: Neighbor của A (B, C)
		- Log: "Peer initialized. Connecting..."

#### 5.4. Demo 2: Chat giữa 2 node
**Terminal 1:**
```
bash
python main.py
# Chọn Node A, username "Alice"
```
**Terminal 2:**
```
bash
python main.py
# Chọn Node B, username "Bob"
```
**Kịch bản:**

	1. Trong ChatWindow A:
		- Click chọn B (Bob) từ sidebar
		- Nhập "Hello Bob"
		- Nhấn Send
	2. Kết quả:
		- Log A: "✓ Sent: Hello Bob to B"
		- ChatWindow B: Hiển thị "Alice: Hello Bob"
		- Log B: "✓ Received from Alice"

#### 5.5. Demo 3: Định tuyến multi-hop

**Khởi động 3 node:**

	- Terminal 1: Node A (Alice)
	- Terminal 2: Node B (Bridge)
	- Terminal 3: Node C (Charlie)

**Topology:**

	A ─── B ─── C (A không neighbor trực tiếp với C)

**Thao tác:**

	1. ChatWindow A: Menu "Discover" → "Find Nodes"
	2. A gửi FIND_NODES → B → C
	3. C gửi FIND_ACK → B → A
	4. Sidebar A cập nhật: thêm C (Charlie)
	5. A gửi "Hi Charlie" → B forward → C nhận
	6. Log B: "Forward message from A to C"

#### 5.6. Demo 4: Mã hóa tin: AES-256 encrypt payload

**Kịch bản:** Gửi tin nhắn A (mã hóa) → B (không mã hóa) → C (mã hóa)

			BẬT mã hóa + bật log so sánh (CMD)
			```
			set PEERCHAT_ENCRYPTION=1
			set PEERCHAT_AES_KEY=qdRIHAtx/2z5tHkHZs8nn0cpHQKe4ye/oaqr0k2jDTw=
			set PEERCHAT_CRYPTO_LOG_COMPARE=1
			.env\Scripts\python.exe main.py
			```
			
			TẮT mã hóa (CMD)
			```			
			set PEERCHAT_ENCRYPTION=0
			set PEERCHAT_AES_KEY=
			set PEERCHAT_CRYPTO_LOG_COMPARE=
			.env\Scripts\python.exe main.py
			```
			
**Thao tác:**

	1. Bật mã hóa trên A
	2. Bật mã hóa trên C
	3. Gửi tin nhắn A → B → C
	4. C nhận lại tin nhắn clear text
	5. B nhận lại tin nhắn đã mã hóa

#### 5.7. Demo 5: Chống vòng lặp

**Kịch bản:** Tạo vòng A → B → C → A

**Thao tác:**

	1. A gửi tin (id=abc123, ttl=5)
	2. B nhận → forward C (ttl=4)
	3. C nhận → forward A (ttl=3)
	4. A nhận lại: kiểm tra abc123 in seen_messages → DROP
	5. Log A: "Message abc123 already processed"
​
## 6. KẾT LUẬN

Báo cáo đã trình bày phân tích yêu cầu, thiết kế phần mềm và trích dẫn các đoạn code then chốt của hệ thống chat P2P phân tán. Các tính năng chính đã được hiện thực hóa, đảm bảo tính phân tán, định tuyến động, lưu trữ cục bộ và giao diện thân thiện. Đây là nền tảng để phát triển các tính năng bảo mật, mở rộng quy mô và kiểm thử tự động trong tương lai.
