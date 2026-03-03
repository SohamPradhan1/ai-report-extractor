
# ---------- BASE IMAGE ----------
FROM python:3.11-slim

# ---------- SYSTEM DEPENDENCIES ----------
# Install Tesseract OCR + Poppler (for pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    tini \
    && rm -rf /var/lib/apt/lists/*

# ---------- PYTHON ENV ----------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---------- INSTALL PYTHON DEPENDENCIES ----------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ---------- COPY APP CODE ----------
COPY . /app

# Render provides PORT automatically
ENV PORT=8080

# ---------- ENTRYPOINT ----------
ENTRYPOINT ["/usr/bin/tini", "--"]

# ---------- START COMMAND (Render-friendly shell form) ----------
CMD gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT app:app
