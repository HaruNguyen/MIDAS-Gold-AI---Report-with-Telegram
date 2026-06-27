# Deploy lên Oracle Cloud "Always Free" VM (miễn phí vĩnh viễn)

Hướng dẫn này đưa Report Server chạy 24/7 trên 1 VM Oracle Cloud free-forever (ARM Ampere A1),
public qua HTTPS để EA gọi `WebRequest` ổn định. Có 2 phương án ở cuối bài (Docker — khuyên dùng,
và systemd+venv — nhẹ hơn nếu muốn tránh Docker).

## 1. Tạo VM Oracle Free

1. Đăng ký tại https://signup.oraclecloud.com (cần thẻ Visa/Mastercard để xác minh danh tính,
   **không bị trừ tiền** nếu chỉ dùng tài nguyên Always Free).
2. Vào **Compute > Instances > Create Instance**.
3. Chọn Image: **Ubuntu 22.04** (hoặc 24.04 nếu có).
4. Chọn Shape: **VM.Standard.A1.Flex** (Ampere ARM) — đặt **1 OCPU / 6GB RAM** (dư nhiều cho app
   này; do giới hạn free đã giảm xuống 2 OCPU/12GB tổng từ tháng 6/2026 nên để dư cho VM khác nếu cần).
   - Nếu vùng (region) bạn chọn báo hết capacity Ampere, đổi sang **Always Free Micro (AMD, x86,
     1GB RAM)** tạm — vẫn chạy được app này vì tải rất nhẹ, chỉ hơi chật RAM khi dùng Docker.
5. Thêm SSH key của bạn (hoặc để Oracle tự sinh, tải file `.pem` về).
6. Create. Ghi lại **Public IP**.

## 2. Mở firewall (Security List + iptables nội bộ Ubuntu)

Oracle có 2 lớp firewall, phải mở cả 2:

```bash
# Tren chinh VM (Ubuntu mac dinh khoa gan het port qua iptables/netfilter)
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT   # bo qua buoc nay neu dung Caddy (443 la du)
sudo netfilter-persistent save 2>/dev/null || sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

Trên **Oracle Console**: vào VCN của bạn > **Security Lists** > Default Security List > **Add
Ingress Rules** > mở `0.0.0.0/0` cho port `80`, `443` (và `8000` nếu không dùng Caddy/HTTPS).

## 3. (Nếu có domain) Trỏ DNS về IP của VM

Tạo 1 bản ghi `A` ví dụ `report.yourdomain.com -> <Public IP>`. Không có domain riêng cũng được —
dùng domain miễn phí kiểu DuckDNS (https://www.duckdns.org) để có 1 hostname ổn định trỏ IP động,
hoặc bỏ qua hẳn bước này và dùng `http://<IP>:8000` thẳng (xem ghi chú trong `Caddyfile`).

## 4. SSH vào VM và lấy code

```bash
ssh -i your-key.pem ubuntu@<Public-IP>

sudo apt update && sudo apt install -y git
git clone https://github.com/HaruNguyen/MIDAS-Gold-AI---Report-with-Telegram.git midas-report
cd midas-report/Telegram_Report_App
cp .env.example .env
nano .env   # dien TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REPORT_API_KEY thuc te
```

## 5A. Phương án Docker (khuyên dùng — auto HTTPS qua Caddy)

```bash
# Cai Docker + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

cd deploy
nano Caddyfile   # sua "report.yourdomain.com" thanh domain thuc cua ban (hoac xoa block, doc ghi chu trong file)
docker compose up -d --build
docker compose logs -f report-server   # kiem tra log, Ctrl+C de thoat xem log (khong tat container)
```

Caddy sẽ tự xin chứng chỉ Let's Encrypt cho domain trong `Caddyfile` ở lần chạy đầu (mất ~10-30s).
App reachable tại `https://report.yourdomain.com/api/report`.

Cập nhật code sau này:

```bash
cd ~/midas-report && git pull
cd Telegram_Report_App/deploy && docker compose up -d --build
```

## 5B. Phương án không Docker (systemd + venv — nhẹ RAM hơn)

```bash
sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx

cd ~/midas-report/Telegram_Report_App
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

sudo cp deploy/midas-report.service /etc/systemd/system/
# Sua duong dan trong file nay (WorkingDirectory/ExecStart) neu username/path khac "ubuntu"
sudo systemctl daemon-reload
sudo systemctl enable --now midas-report
sudo systemctl status midas-report   # phai thay "active (running)"
```

Bật HTTPS qua Nginx + certbot (nếu có domain):

```bash
sudo tee /etc/nginx/sites-available/midas-report <<'EOF'
server {
    listen 80;
    server_name report.yourdomain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/midas-report /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d report.yourdomain.com   # tu xin SSL + tu sua config nginx, lam theo prompt
```

## 6. Whitelist URL trong MT5 và set EA

Trên MT5 (mỗi máy/VPS client chạy EA): **Tools > Options > Expert Advisors** > tick "Allow
WebRequest for listed URL" > thêm đúng URL server, ví dụ:

```
https://report.yourdomain.com/api/report
```

Trong input của EA (`Report_ServerURL`), điền cùng URL này, và `Report_ApiKey` khớp với
`REPORT_API_KEY` trong `.env` trên server.

## 7. Kiểm tra cuối

```bash
curl -X POST https://report.yourdomain.com/api/report \
  -H "Content-Type: application/json" \
  -d '{"api_key":"GIA_TRI_TRONG_ENV","login":999,"server":"test","symbol":"XAUUSD","preset":"Master Alpha","is_cent":false,"balance":1000,"equity":1000,"margin_level":500,"free_margin":900,"floating_pl":0,"drawdown_pct":0,"total_orders":1,"buy_orders":1,"sell_orders":0,"total_lots":0.1,"buy_lots":0.1,"sell_lots":0,"closed_lots_today":0,"loop_active":true,"hedge_active":false,"ai_confidence":0,"zone_points":50,"tp_points":100,"multiplier":1.3,"max_orders":30,"health_status":"SAFE","license_expiry":"2026-12-31","timestamp":"2026-06-27 00:00:00"}'
```

Nếu trả `{"status":"ok",...}` (hoặc tương tự) → server đã sẵn sàng nhận dữ liệu thật từ EA.
Kiểm tra Telegram bot bằng lệnh `/accounts`.

## Ghi chú quan trọng

- **Backup DB định kỳ**: dù chạy Docker hay venv, copy file SQLite (`/app/data/midas_report.db`
  hoặc `midas_report.db`) về máy bạn hoặc lên cloud storage mỗi ngày — VM free vẫn có thể bị Oracle
  thu hồi nếu tài khoản bị đánh dấu "idle" theo chính sách Always Free (xem mục dưới).
- **Idle reclamation**: Oracle có thể tự thu hồi VM Always Free nếu họ đánh giá là "không hoạt
  động" liên tục (CPU < 10%, network < ngưỡng...) trong nhiều ngày. App này luôn có request đến
  mỗi 60s từ EA + cron job, nên rất khó bị coi là idle trong thực tế — nhưng vẫn nên bật email
  cảnh báo trong Oracle Console (Notifications) để biết sớm nếu có cảnh báo thu hồi.
- **Nhiều tài khoản (> 50)**: đổi `DATABASE_URL` sang Postgres (có thể chạy Postgres luôn trên
  cùng VM bằng container riêng trong `docker-compose.yml`, hoặc dùng free tier Postgres của
  Neon/Supabase để đỡ tốn RAM của VM free).
