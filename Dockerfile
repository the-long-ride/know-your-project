FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "python", "-m", "know_your_project.app"]
