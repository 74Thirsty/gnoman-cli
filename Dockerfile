# File: Dockerfile
# GNOMAN CLI container build
FROM python:3.11-slim

# Set up working directory
WORKDIR /app

# Install dependencies first (caches better)
COPY pyproject.toml requirements.txt* setup.cfg* ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy code into container
COPY . .

# Install package (editable mode optional)
RUN pip install --no-cache-dir .

# Set GNOMAN as entrypoint
ENTRYPOINT ["gnoman"]
CMD ["--help"]

