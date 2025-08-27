# Use Python 3.8 slim image as base
FROM python:3.8-slim

# Set working directory in container
WORKDIR /app

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash signage && \
    chown -R signage:signage /app

# Copy application files
COPY main.py .
COPY config.json .
COPY static/ static/
COPY scripts/ scripts/

# Create necessary directories and set permissions
RUN mkdir -p /app/static && \
    chown -R signage:signage /app

# Switch to non-root user
USER signage

# Expose the application port
EXPOSE 5000

# Health check to ensure the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000')" || exit 1

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "5000"]