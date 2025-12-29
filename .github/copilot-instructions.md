# Hướng dẫn Copilot — peer_chat

## Bắt đầu nhanh ✅
- Tạo virtualenv và cài deps (Windows):
  - python -m virtualenv .env
  - .env\Scripts\activate
  - pip install -r requirements.txt
- Tạo dữ liệu mẫu (config và DB): `python gen_data.py` (viết `config/*.json` và `db/*.db`)
- Chạy ứng dụng: `python main.py` → chọn node (A..M), đặt username, nhấn `Start Chat`.
- Để tái tạo cơ chế khám phá (discovery): chạy hai instance, vào menu `Discover → Find Nodes`.

## Kiến trúc tổng quan 🔧
- UI: `ui/` (PyQt5). Điểm vào: `main.py` → `ui.main_window.MainWindow` → `ui.chat_window.ChatWindow`.
- Core: `core/` chứa logic ứng dụng. `core.chat_manager.ChatManager` điều phối peers, định tuyến tin nhắn và truy cập DB.
- Network: `network/` chứa tầng socket:
  - `ServerWorker` bind và phát `new_connection` cho mỗi socket vào
  - `ServerClientWorker` xử lý socket kết nối tới server, phát `new_data`
  - `ClientWorker` chủ động kết nối tới peers, phát `new_data`, `connected`, `disconnected` và hỗ trợ retry
  - `protocol.py` mã hóa/giải mã tin nhắn (JSON bytes)
- Lưu trữ: `core.db.ChatDatabase` → các file sqlite tại `db/{node}.db`.
- Cấu hình: từng node có file JSON trong `config/{A..M}.json`. `utils.config.Config` dùng để load/save.

## Mẫu tin nhắn & quy tắc định tuyến 💬
- Mẫu tin nhắn (xem `network/protocol.py`): JSON với các trường
  - `type` (ví dụ: `MESSAGE`, `FIND_NODES`, `FIND_ACK`), `from`, `from_n`, `to`, `message_id`, `content`, `ttl`, `forward`, v.v.
  - `encode_message(...)` trả về bytes; `decode_message(...)` nhận bytes và trả dict
- Khám phá mạng: `FIND_NODES` được forward kèm TTL; `FIND_ACK` trả payload gồm `self` và `neighbors`.
- Ngăn vòng lặp: `ChatManager.seen_messages` (tập message_id) và giảm TTL được dùng.
- Forwarding: `ChatManager.handle_forward_msg` và `handle_find_nodes` thực hiện logic forward và chọn neighbor.

## Quy ước threading / worker 🧵
- Mô hình thread: tạo `QThread`, `moveToThread(worker)`, connect `thread.started` → hàm entry của worker, và kết nối các signal cleanup:
  - `worker.finished` → `thread.quit()` + `.deleteLater()`
  - `thread.finished` → `thread.deleteLater()`
- Dùng signals cho giao tiếp giữa thread (`send_data`, `new_data`, `status`, `connected`, `disconnected`).
- Khi tắt ứng dụng, gọi `worker.stop()` và `thread.quit()`/`thread.wait()` để tránh leak.

## Quy trình phát triển & debug 🔍
- Kiểm thử thủ công: tạo dữ liệu mẫu bằng `gen_data.py`, chạy nhiều instance UI và thử `Find Nodes` + gửi tin nhắn.
- Logging: UI hiển thị `status` và `log_received`; nhiều module in log ra console — xem cả console và panel Logs trong app.
- Kiểm tra DB: file `db/{node}.db` (SQLite). Dùng `sqlite3` hoặc DB browser.

## Những quy ước & lưu ý dự án ⚠️
- File cấu hình đặt tên `A.json`..`M.json` và được load bằng `Config(f'{text}.json')` trong `ui.main_window`.
- Network truyền nhận raw bytes (`encode_message`/`decode_message`). Không thay đổi định dạng payload mà không cập nhật cả hai đầu.
- Vấn đề đã phát hiện khi kiểm tra:
  - `ChatDatabase` tạo bảng `message` nhưng phương thức tham chiếu tới `messages` (lỗi tên bảng) — các truy vấn sẽ lỗi.
  - `crypto/key_exchange.py` và `utils/helper.py` hiện để trống; `crypto/encrypt.py` chỉ là ví dụ đảo chuỗi.
  - Chưa có tests tự động hay CI; nên thêm tests trước khi bật CI.

## Nơi chỉnh khi thêm tính năng ✍️
- Thêm loại tin nhắn mới: cập nhật `network/protocol.py` và thêm xử lý trong `core.chat_manager.handle_incoming`.
- Thêm hành động UI: sửa `ui.chat_window` và phát event tới `ChatManager`.
- Thêm dữ liệu persist: thêm migration/schema trong `core/db.py`.

## File nên đọc đầu tiên 📂
- core/chat_manager.py — routing, forward, lifecycle peer
- network/protocol.py — định dạng tin nhắn
- network/*_worker.py — pattern xử lý socket và threading
- utils/config.py — cách resolve đường dẫn config
- gen_data.py — cách sinh config & DB mẫu

---
Nếu bạn muốn, tôi có thể: (1) mở PR thêm file này, (2) thêm unit tests nhỏ cho `protocol.encode_message/decode_message`, hoặc (3) tạo issue ghi nhận lỗi DB và file trống. Bạn muốn tôi làm gì tiếp theo? 💡
