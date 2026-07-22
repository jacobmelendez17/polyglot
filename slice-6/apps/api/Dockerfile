FROM python:3.12-slim

# bash for the entrypoint
RUN apt-get update && apt-get install -y --no-install-recommends bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the whole project FIRST so the package source (app/) is present when
# pip builds the wheel. pyproject.toml declares packages=["app"], so app/ must
# exist at install time. Runtime deps only — the test toolchain stays out of
# the running image to keep it small.
COPY . .
RUN pip install --no-cache-dir . \
    && chmod +x entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
