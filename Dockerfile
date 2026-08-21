# Use an official, lightweight Python runtime
FROM python:3.11-slim

# Prevent Python from writing .pyc files and force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the FastAPI server will run on
EXPOSE 8000

# The default command to start the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]