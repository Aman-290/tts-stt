# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements file
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --system -r requirements.txt

# Copy the entire application
COPY . .

# Set environment variables to reduce memory usage
ENV PYTHONUNBUFFERED=1
ENV MALLOC_ARENA_MAX=2

# Expose port for health checks
EXPOSE 8080

# Make startup script executable
RUN chmod +x startup.sh

# Run the startup script
CMD ["./startup.sh"]
