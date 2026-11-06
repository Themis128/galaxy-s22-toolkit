FROM python:3.12-slim

# adb client: the container reaches the device over wireless ADB
RUN apt-get update \
    && apt-get install -y --no-install-recommends adb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY phone-lib/ /app/phone-lib/
# Full diagnostics package (logs/reports stay out via .dockerignore) so
# POST /api/diagnostics/run works inside the container
COPY diagnostics/ /app/diagnostics/
COPY dashboard/ /app/dashboard/
COPY tools/ /app/tools/

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" jinja2 pyyaml

EXPOSE 8081
ENV DASHBOARD_PORT=8081
CMD ["python", "dashboard/app.py"]
