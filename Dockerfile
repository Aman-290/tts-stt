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



# Make startup script executable
RUN chmod +x startup.sh

# Run the startup script
CMD ["./startup.sh"]
