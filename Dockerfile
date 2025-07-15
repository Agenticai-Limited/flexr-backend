# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install uv for faster package installation
RUN pip install uv

# Copy the requirements file and install dependencies
COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --no-config --python=$(which python3)

# Copy the rest of the application code
COPY ./api /app/api
COPY ./src /app/src

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["/bin/sh", "-c", ". .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8000"]