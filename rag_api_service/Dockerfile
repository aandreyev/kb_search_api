# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . /app

# Make port $RAG_API_PORT available
ENV RAG_API_PORT=${RAG_API_PORT:-8002}
EXPOSE 8002

# Define environment variable for the Uvicorn server
ENV HOST 0.0.0.0

# Run main.py when the container launches
# The main.py script itself reads RAG_API_PORT for Uvicorn
CMD ["python", "main.py"] 