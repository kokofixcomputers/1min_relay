FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# Optionally set defaults for environment variables
ENV SUBSET_OF_ONE_MIN_PERMITTED_MODELS
ENV PERMIT_MODELS_FROM_SUBSET_ONLY

EXPOSE 5001

CMD ["python", "main.py"]