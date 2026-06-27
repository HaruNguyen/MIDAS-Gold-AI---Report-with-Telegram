# MIDAS Gold AI — Report App (Telegram)

App theo dõi tài khoản đang chạy **MIDAS Gold AI EA** (Zone Recovery, XAUUSD), tự động báo cáo
sức khỏe tài khoản, volume/doanh thu IB, hạn thuê bot, và hiệu suất AI về Telegram cho chủ bot.

Đã được test end-to-end (xem phần "Đã kiểm tra" dưới).

## Kiến trúc

```
EA (MQL5, mỗi tài khoản client)
   │  WebRequest POST JSON, mỗi 60s (cấu hình được)
   ▼
Report Server (FastAPI + SQLite/Postgres)
   │  - Lưu snapshot, phân loại sức khỏe (SAFE/WATCH/CRITICAL/HEDGE_LOCKED)
   │  - So sánh với trạng thái trước -> quyết định có alert hay không (escalation only)
   │  - Cron: digest hàng ngày + check hạn license
   ▼
Telegram Bot
   - Push: alert tức thời khi tài khoản xấu đi / được giải cứu, nhắc hết hạn license
   - Pull: /accounts /account <login> /risk /volume /licenses /digest
```

## Vì sao chọn "EA tự báo cáo" thay vì đọc trực tiếp tài khoản MT5

Bạn hỏi: dùng login + investor password (passview) có đủ không, hay cần trade password (passtrade)?

- **Investor password là đủ** cho mục đích xem (balance, equity, lệnh mở, lịch sử) — không cần trade
  password, vì app này chỉ *đọc*, không đặt lệnh. Trade password chỉ cần khi muốn *điều khiển* tài
  khoản (mở/đóng lệnh) từ xa.
- **Nhưng nên dùng cách EA tự báo cáo (đã triển khai ở đây) thay vì đăng nhập MT5 hộ khách**, vì 3 lý do:
  1. Không phải lưu trữ mật khẩu của khách (kể cả investor password) trên server của bạn — giảm rủi ro
     bảo mật/pháp lý, và khách sẽ an tâm hơn khi không phải đưa thêm mật khẩu cho bên thứ ba.
  2. EA đã có sẵn toàn bộ trạng thái nội bộ (Zone, TP, Multiplier, AI confidence, preset Alpha/Elite,
     Loop/Hedge) — những thứ này **không** đọc được nếu chỉ login MT5 xem tài khoản thông thường.
  3. Đăng nhập MT5 song song để "xem" thường yêu cầu chạy một terminal MT5 hoặc dùng dịch vụ trung gian
     (ví dụ MetaApi.cloud) cho từng tài khoản — tốn tài nguyên/chi phí hơn nhiều so với 1 dòng code
     `WebRequest` có sẵn trong EA của chính bạn.

→ File `ea_snippet/ReportModule.mqh` là module nhúng vào EA hiện tại, không cần thêm hạ tầng nào khác
ngoài 1 server nhỏ.

## Các chỉ số được ưu tiên (theo yêu cầu)

1. **Sức khỏe & rủi ro**: số lệnh mở (ngưỡng 15 = AI bắt đầu nâng lot, 26 = sát Hedge), drawdown %,
   trạng thái Loop/Hedge, alert chỉ bắn khi *xấu đi* hoặc *vừa được giải cứu* (tránh spam).
2. **Volume & doanh thu IB**: tổng lot khớp/ngày mỗi tài khoản, quy đổi ra doanh thu IB ước tính
   theo `$/lot` bạn cấu hình — phục vụ đối soát hoa hồng.
3. **Hạn thuê bot**: cảnh báo tự động ở các mốc 30/14/7/1 ngày trước khi hết hạn (~$600/năm giá gốc).
4. **Hiệu suất AI & cấu hình**: AI confidence hiện tại, preset (Master Alpha/Elite), Zone/TP/Multiplier
   đang chạy.

## Mẫu báo cáo chi tiết theo tài khoản ("Report Daily")

Lệnh `/account <login>` và job tự động hàng ngày (`daily_account_reports`, chạy 1 phút sau digest)
gửi 1 tin chi tiết riêng cho từng tài khoản — Balance/Equity/Drawdown/Margin, sức khỏe bộ lệnh,
Buy/Sell/Net lot — cộng thêm 3 nhóm chỉ số tối ưu mà mẫu báo cáo cơ bản chưa có: Volume & doanh thu IB
hôm nay, AI & cấu hình (preset/multiplier/AI confidence/Zone-TP/Loop-Hedge), và hạn thuê bot còn lại.
Xem hàm `format_account_report()` trong `backend/telegram_bot.py`. Cần EA gửi thêm `free_margin`,
`buy_lots`, `sell_lots` (đã thêm vào `ReportModule.mqh`) để hiển thị đầy đủ.

## Cách chạy thử (prototype)

```bash
cd Telegram_Report_App
pip install -r requirements.txt --break-system-packages
cp .env.example .env        # rồi điền TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, REPORT_API_KEY thật

uvicorn backend.main:app --reload --port 8000
# terminal khác:
python demo/simulate_accounts.py
```

Trong Telegram, chat với bot: `/accounts`, `/risk`, `/volume`, `/licenses`, `/digest`.

## Đã kiểm tra (trong sandbox, không cần Telegram token)

- Server FastAPI khởi động, tạo DB, scheduler chạy không lỗi.
- `demo/simulate_accounts.py` gửi 7 snapshot mô phỏng 3 tài khoản → toàn bộ trả `200 OK`.
- Logic phân loại đúng: 6 lệnh → SAFE, 17 lệnh/DD10% → WATCH, 27 lệnh/DD28% → CRITICAL,
  Hedge ON → HEDGE_LOCKED, sau đó về 2 lệnh/DD1% → SAFE.
- Alert chỉ bắn đúng lúc cần (escalation + tin giải cứu), không bắn khi trạng thái không đổi.
- `build_daily_digest_text()` tổng hợp đúng số tài khoản theo từng nhóm, volume, doanh thu ước tính,
  danh sách cần chú ý, và license sắp hết hạn.

## Deploy miễn phí (không cần VPS trả phí)

Xem `deploy/DEPLOY_ORACLE.md` — hướng dẫn đầy đủ deploy lên **Oracle Cloud Always Free VM**
(miễn phí vĩnh viễn, chạy 24/7, HTTPS tự động qua Caddy). Có sẵn `deploy/Dockerfile`,
`deploy/docker-compose.yml`, `deploy/Caddyfile`, và phương án không-Docker `deploy/midas-report.service`
(systemd) nếu muốn nhẹ RAM hơn trên VM cấu hình thấp.

## Bước tiếp theo khi triển khai thật

1. Đưa `ReportModule.mqh` vào EA, set `Report_ServerURL`/`Report_ApiKey`, whitelist URL trong MT5.
2. Deploy backend theo `deploy/DEPLOY_ORACLE.md` (hoặc VPS khác nếu muốn), đổi `DATABASE_URL` sang Postgres nếu nhiều tài khoản.
3. Tạo bot qua @BotFather, lấy `TELEGRAM_BOT_TOKEN`, lấy `TELEGRAM_CHAT_ID` (chat riêng hoặc group quản trị).
4. Tinh chỉnh `IB_RATE_USD_PER_LOT` và các ngưỡng rủi ro trong `.env` theo thực tế từng sàn.
5. (Nâng cấp) gắn `owner_label` cho từng tài khoản để biết tài khoản của khách nào, hoặc tách
   digest riêng theo từng đối tác/IB nếu có nhiều downline.
