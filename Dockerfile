# 使用官方基於 Python 的輕量級映像
FROM python:3.9-slim

# 設定環境變數，避免輸出與互動問題
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    unixodbc-dev \
    unixodbc \
    curl \
    apt-transport-https \
    gnupg \
    build-essential \
    && apt-get clean

# 安裝 Microsoft ODBC Driver for SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# 設置工作目錄
WORKDIR /app

# 複製 requirements.txt 到工作目錄
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼到容器中
COPY . .

# 開放服務所需的端口（假設 Flask 默認端口為 5000）
EXPOSE 5000

# 啟動應用程式
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]