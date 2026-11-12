FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 默认不装 Ollama（宿主机运行），Docker 只跑 Python 应用
EXPOSE 8000 8501

CMD ["python", "run.py"]
