FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 5001

CMD ["python", "main.py"]
