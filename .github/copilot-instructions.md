# Hướng dẫn Copilot — peer_chat (Phân tán P2P Chat)

## Bắt đầu nhanh ⚡

1. **Cấu hình môi trường (Windows):**
   ```bash
   python -m virtualenv .env
   .env\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Tạo dữ liệu mẫu:** `python gen_data.py` → sinh 13 node (A-M) với config JSON và SQLite DB

3. **Chạy ứng dụng:** `python main.py` → chọn node, đặt username, nhấn "Start Chat"

4. **Kiểm tra khám phá mạng:** Chạy 2 instance, dùng menu `Discover → Find Nodes`

## Kiến trúc tổng quan 🔧

**Các lớp & class chính:**
- **UI** (`ui/`): PyQt5. Điểm vào: `main.py` → `MainWindow` → `ChatWindow`
- **Core** (`core/`): 
  - `ChatManager` — điều phối peers, định tuyến tin nhắn, quản lý DB
  - `ChatDatabase` — SQLite per-node tại `db/{node}.db` với schema `messages` + `neighbor`
- **Network** (`network/`): Lớp socket đa luồng với Qt signals
  - `ServerWorker` — bind port, phát `new_connection` cho mỗi socket đến
  - `ServerClientWorker` — xử lý socket từ peer, phát `new_data`
  - `ClientWorker` — kết nối chủ động, tự động retry, phát `connected`/`disconnected`/`new_data`
  - `protocol.py` — encode/decode JSON tin nhắn thành bytes UTF-8
- **Config** (`utils/config.py`): Load/save JSON cấu hình từ `config/{node}.json`

## Mẫu tin nhắn & quy tắc định tuyến 💬

**Cấu trúc tin nhắn** (`network/protocol.py`):
```python
{
  "type": "MESSAGE|FIND_NODES|FIND_ACK",
  "from": "<sender_peer_id>",
  "from_n": "<sender_username>",
  "to": "<receiver_peer_id>",
  "to_n": "<receiver_username>",
  "message_id": "<uuid>",
  "content": "<payload>",
  "ttl": 5,
  "forward": "<forwarder_id>",
  "timestamp": <unix_time>
}
```
- `encode_message(...)` → bytes UTF-8
- `decode_message(bytes)` → dict

**Quy tắc định tuyến:**
- **Ngăn vòng lặp:** `ChatManager.seen_messages` (set) lưu message_id đã xử lý; giảm TTL mỗi lần forward
- **Khám phá:** `FIND_NODES` được flood với TTL; peers trả `FIND_ACK` chứa danh sách neighbors
- **Forwarding:** `ChatManager.handle_forward_msg()` + `handle_find_nodes()` — logic chọn neighbor để forward

## Quy ước threading / worker 🧵

**Mô hình chuẩn** (xem `network/*_worker.py`):
1. Tạo `QThread` + instance worker
2. `worker.moveToThread(thread)` → `thread.started.connect(worker.entry_method)`
3. Kết nối signals cleanup:
   - `worker.finished` → `thread.quit()` + `.deleteLater()`
   - `thread.finished` → `thread.deleteLater()`
4. Khi tắt: gọi `worker.stop()` + `thread.quit()` / `thread.wait()` để tránh memory leak

**Giao tiếp thread:** Dùng Qt signals (`send_data`, `new_data`, `status`, `connected`, `disconnected`) — KHÔNG dùng locks/queues trực tiếp

## Quy trình phát triển & debug 🔍

- **Kiểm thử thủ công:** `gen_data.py` sinh ra 13 node với ma trận neighbor được định sẵn; chạy 2+ UI instance và thử `Find Nodes` + gửi tin nhắn
- **Logging:** Xem console output + panel "Logs" trong app
- **Kiểm tra DB:** `sqlite3` CLI hoặc DB browser trên `db/{node}.db`
- **Topo mạng:** Được định nghĩa trong `gen_data.py` dưới dạng ma trận kề (adjacency matrix); sửa + regenerate DB để test topology khác

## Những quy ước & lưu ý dự án ⚠️

- **Tên file config:** `A.json`..`M.json` được load bằng `Config(f'{text}.json')` trong `ui/main_window.py`
- **Network protocol:** Truyền raw bytes (`encode_message`/`decode_message`). Đừng thay đổi format mà không update cả hai đầu
- **Lỗi phát hiện:**
  - **Bug tên bảng (đã được sửa trước đây):** Trước đây có vài query tham chiếu nhầm bảng `message` trong `core/db.py` (trong khi schema tạo bảng `messages`) gây lỗi SQL; đã sửa các truy vấn để dùng `messages` đồng nhất và thêm migration để đảm bảo cột `id` (UUID) tồn tại và backfill các bản ghi cũ.
  - **Chạy migration (TODO script):** dự kiến sẽ có script `scripts/migrate_db.py` để áp dụng migration cho các DB cũ. Script này HIỆN CHƯA được thêm vào repository, hãy tự viết dựa trên logic trong `core/db.py` (hoặc bỏ qua bước này nếu bạn chỉ dùng DB mới tạo bằng `gen_data.py`). Khi script tồn tại, có thể chạy từ thư mục gốc của dự án. **Hãy sao lưu thư mục `db/` trước khi chạy.**
    - **Ví dụ cách chạy dự kiến trên Windows / PowerShell (nếu dùng virtualenv):**
      ```powershell
      .env\Scripts\activate
      python scripts/migrate_db.py
      ```
    - **Hoặc chạy trực tiếp với Python của virtualenv (khi script đã tồn tại):**
      ```powershell
      & ".\.env\Scripts\python.exe" scripts/migrate_db.py
      ```
  - **Modules để trống:** `crypto/key_exchange.py`, `utils/helper.py` chưa implement; `crypto/encrypt.py` chỉ là stub (đảo chuỗi)
  - **Không có tests tự động hay CI**

## Nơi chỉnh khi thêm tính năng ✍️

- **Thêm loại tin nhắn mới:** cập nhật `network/protocol.py` + thêm handler trong `ChatManager.handle_incoming()`
- **Thêm hành động UI:** sửa `ui/chat_window.py` → emit signal hoặc gọi phương thức `ChatManager`
- **Thêm dữ liệu persist:** thêm schema/migration trong `core/db.py`; regenerate DB bằng `gen_data.py`

## File nên đọc đầu tiên 📂

- [core/chat_manager.py](core/chat_manager.py) — routing, forward, lifecycle peer
- [network/protocol.py](network/protocol.py) — định dạng tin nhắn
- [network/client_worker.py](network/client_worker.py) & [network/server_worker.py](network/server_worker.py) — pattern xử lý socket và threading
- [core/db.py](core/db.py) — schema & persistence API
- [gen_data.py](gen_data.py) — cách sinh config & DB mẫu

---

**Tập làm quen nhanh:** Chạy `gen_data.py`, mở 2 instance `main.py`, test `Find Nodes` + gửi tin nhắn qua lại. Xem console & panel Logs để hiểu luồng dữ liệu.
