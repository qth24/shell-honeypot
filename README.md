# Honeypot

Honeypot shell giả lập dùng `Cowrie` cho dịch vụ bẫy và `FastAPI` cho web terminal.


1. Tạo file môi trường:

```bash
cp .env.example .env
```

2. Build và chạy:

```bash
docker compose up -d --build
```

3. Kiểm tra trạng thái:

```bash
docker compose ps
docker compose logs -f cowrie
docker compose logs -f web
```

4. Truy cập:

```text
Web terminal nội bộ VPS: http://127.0.0.1:7788
SSH honeypot nội bộ VPS: ssh root@127.0.0.1 -p 2222
Telnet honeypot nội bộ VPS: telnet 127.0.0.1 2223
```

