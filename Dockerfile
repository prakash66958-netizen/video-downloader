# Use a modern Python runtime (3.11 is required by newer yt-dlp)
FROM python:3.11-slim

# Install system dependencies (including ffmpeg and build tools for source install)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Set permissions for the non-root user (Hugging Face uses UID 1000)
RUN chown -R 1000:1000 /app

# Install dependencies and FORCE UPDATE yt-dlp to latest code
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U "https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz"

# Make port 7860 available to the world outside this container
EXPOSE 7860

# Define environment variable
ENV FLASK_APP=app.py

# Switch to the non-root user
USER 1000

# Run app.py when the container launches
CMD ["python", "app.py"]
