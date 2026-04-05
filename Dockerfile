# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install system dependencies (including ffmpeg for video merging)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# FORCE UPDATE yt-dlp to the absolute latest nightly version for bypass
RUN pip install --no-cache-dir -U https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=app.py

# Run app.py when the container launches
CMD ["python", "app.py"]
