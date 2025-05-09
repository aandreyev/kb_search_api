# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . /app

# Make port $EMBEDDING_SERVICE_PORT available to the world outside this container
# The actual port will be set by the EMBEDDING_SERVICE_PORT env var at runtime
# Docker Compose will map a host port to this.
# We don't EXPOSE $PORT directly from an ARG here, Uvicorn will use it.
ENV EMBEDDING_SERVICE_PORT=${EMBEDDING_SERVICE_PORT:-8001}
EXPOSE 8001

# Define environment variable for the Uvicorn server
ENV HOST 0.0.0.0
# PORT will be dynamically set by EMBEDDING_SERVICE_PORT or Docker Compose mapping for Uvicorn

# Run main.py when the container launches
# The main.py script itself reads EMBEDDING_SERVICE_PORT for Uvicorn
CMD ["python", "main.py"] 