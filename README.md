# Transcription History Manager

A FastAPI-based web application for managing transcription history, built with Python 3.13.

## Features

- Fast and modern API built with FastAPI
- Python 3.13 support
- Type hints and validation with Pydantic
- Auto-generated interactive API documentation (Swagger UI)
- Health check endpoints
- CORS middleware support
- Docker support
- Task automation with Taskfile

## Prerequisites

- Python 3.13 or higher
- pip
- (Optional) Docker and Docker Compose
- (Optional) Task (https://taskfile.dev/)

## Project Structure

```
transcription-history-manager/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── health.py      # Health check endpoints
│   ├── core/
│   │   └── config.py          # Application configuration
│   ├── models/                # Database models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   └── main.py                # FastAPI application entry point
├── tests/                     # Test files
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml             # Project dependencies
├── Taskfile.yml               # Task automation
├── LICENSE
└── README.md
```

## Installation

### Option 1: Using pip

1. Clone the repository:
```bash
git clone <repository-url>
cd transcription-history-manager
```

2. Create a virtual environment:
```bash
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. For development, install dev dependencies:
```bash
pip install -e ".[dev]"
```

### Option 2: Using Task

If you have Task installed:

```bash
# Install dependencies
task install

# Install with dev dependencies
task install-dev
```

## Running the Application

### Development Mode (with hot reload)

Using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Using Task:
```bash
task dev
```

### Production Mode

Using uvicorn directly:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Using Task:
```bash
task run
```

### Using Docker

Build and run with Docker:
```bash
docker build -t transcription-history-manager:latest .
docker run -p 8000:8000 transcription-history-manager:latest
```

Or use Docker Compose:
```bash
docker-compose up -d
```

Using Task:
```bash
task docker-up
```

## API Documentation

Once the application is running, you can access:

- Interactive API docs (Swagger UI): http://localhost:8000/docs
- Alternative API docs (ReDoc): http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

## Available Endpoints

- `GET /` - Root endpoint with welcome message
- `GET /api/v1/health` - Health check endpoint
- `GET /api/v1/ready` - Readiness check endpoint
- `GET /api/v1/live` - Liveness check endpoint

## Development

### Running Tests

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Using Task
task test
task test-cov
```

### Code Quality

```bash
# Lint code
task lint

# Auto-fix linting issues
task lint-fix

# Format code
task format

# Check formatting
task format-check

# Type checking
task typecheck

# Run all checks
task check
```

### Available Task Commands

Run `task --list` to see all available commands:

- `task install` - Install project dependencies
- `task install-dev` - Install with dev dependencies
- `task dev` - Run development server with hot reload
- `task run` - Run production server
- `task test` - Run tests
- `task test-cov` - Run tests with coverage
- `task lint` - Run ruff linter
- `task lint-fix` - Auto-fix linting issues
- `task format` - Format code
- `task format-check` - Check formatting
- `task typecheck` - Run mypy type checker
- `task check` - Run all checks
- `task docker-build` - Build Docker image
- `task docker-run` - Run Docker container
- `task docker-up` - Start with docker-compose
- `task docker-down` - Stop docker-compose services
- `task clean` - Clean temporary files and caches

## Environment Variables

Create a `.env` file in the project root to customize settings:

```env
# Application
APP_NAME=Transcription History Manager
APP_VERSION=0.1.0
DEBUG=false

# Server
HOST=0.0.0.0
PORT=8000

# API
API_PREFIX=/api/v1

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

## License

See LICENSE file for details.
