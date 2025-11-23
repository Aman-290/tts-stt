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

# Run the download-files command
RUN python run_agent.py download-files

# Expose port (adjust if needed)
EXPOSE 8080

# Run the agent
CMD ["python", "run_agent.py"]
