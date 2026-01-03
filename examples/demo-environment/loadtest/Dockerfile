FROM python:3.12-slim

LABEL maintainer="Helios Team"
LABEL description="Locust load testing for Saleor e-commerce"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy locust files
COPY locustfiles/ ./locustfiles/

# Set Python path
ENV PYTHONPATH=/app/locustfiles

# Default environment variables
ENV LOCUST_HOST=http://saleor-api.saleor.svc.cluster.local
ENV ADMIN_EMAIL=admin@example.com
ENV ADMIN_PASSWORD=admin123456

# Expose Locust web UI and worker ports
EXPOSE 8089 5557 5558

# Default command runs web UI mode
CMD ["locust", "-f", "/app/locustfiles/locustfile.py", "--web-host", "0.0.0.0"]
