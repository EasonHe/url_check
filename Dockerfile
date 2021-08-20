FROM python:3.6.10-alpine

WORKDIR /app
ADD .  /app
RUN pip install --trusted-host mirrors.aliyun.com --no-cache-dir -r requirements.txt
CMD ["python", "url-check.py"]
