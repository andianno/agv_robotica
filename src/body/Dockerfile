# Use Python 3.10 as the runtime for the Body service.
FROM python:3.10

ENV PYTHONUNBUFFERED=1
# Allow Python to import the service modules from /app.
ENV PYTHONPATH=/app

WORKDIR /app

# 1. Install the compiler tools required to build Python dependencies.
# Git is not required by the Body image; build-essential provides the basic
# toolchain needed by packages that contain native extensions.
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Upgrade pip before installing the Python dependencies.
RUN pip install --upgrade pip

# 3. Install the Body service dependencies.
# The CoppeliaSim ZMQ Remote API client and CBOR support are supplied by the
# external_libs directory rather than installed from this requirements file.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the Body service source code and supporting files into the image.
COPY . .

# Start the Body service when the container launches.
CMD ["python", "-u", "main_body.py"]