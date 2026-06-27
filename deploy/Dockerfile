# MIDAS Gold AI Report Server — image nhe, chay tot tren Oracle Free VM (ARM Ampere A1)
FROM python:3.12-slim

WORKDIR /app

# Cai dependency truoc de tan dung Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

# Thu muc luu DB SQLite (mount volume vao day de du lieu khong mat khi container restart)
RUN mkdir -p /app/data

EXPOSE 8000

# Khong --reload trong production; 1 worker la du vi APScheduler/Telegram polling
# khong duoc chay nhieu worker (se bi nhan job/poll trung lap).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
