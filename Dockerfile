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



# Expose port (adjust if needed)
EXPOSE 8080

# Run download-files at startup, then start the agent in production mode
CMD python run_agent.py download-files && python run_agent.py start
