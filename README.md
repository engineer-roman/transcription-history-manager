# Transcription History Manager

A FastAPI-based web application for managing and viewing transcription history from various providers, built with Python 3.13.

## Features

### Backend
- **Clean Architecture**: Organized in layers (Facade, Service, Repository)
- **FastAPI Framework**: Fast, modern API with automatic OpenAPI documentation
- **Python 3.13**: Latest Python features and performance improvements
- **Type Safety**: Full type hints and validation with Pydantic
- **Multiple Providers**: Extensible repository pattern (Superwhisper supported)
- **Search**: Full-text search across all transcriptions
- **Version Management**: Track multiple transcription versions of the same audio

### Frontend
- **Modern UI**: Clean, responsive interface with sticky search bar
- **Conversation List**: Browse all transcriptions with metadata
- **Version History**: View and compare different transcription versions
- **Audio Player**: Full-featured player with:
  - Play/pause controls
  - Skip forward/backward (10 seconds)
  - Adjustable playback speed (0.75x, 1x, 1.25x, 1.5x, 2x)
  - Timeline scrubbing
  - Current position and total duration display
  - Jump to specific timestamps
- **Tabbed View**: Switch between:
  - Raw transcription text
  - Timestamped transcription segments (clickable to jump in audio)
  - LLM-processed output
- **Search Functionality**:
  - Search across all transcriptions
  - Highlighted search results
  - Context snippets showing matches
  - Clear/reset search

### Infrastructure
- Docker support with health checks
- Task automation with Taskfile
- Comprehensive test suite
- CORS middleware support

## Prerequisites

- Python 3.13 or higher
- pip
- (Optional) Docker and Docker Compose
- (Optional) Task (https://taskfile.dev/)

## Architecture

The application follows **Clean Architecture** principles with clear separation of concerns:

### Layers

1. **Facade Layer** (`app/api/`): API endpoints and HTTP handling
2. **Service Layer** (`app/services/`): Business logic, conversation grouping, search
3. **Repository Layer** (`app/repositories/`): Data access, file system operations

### Project Structure

```
transcription-history-manager/
├── app/
│   ├── api/
│   │   ├── dependencies.py         # Dependency injection
│   │   └── routes/
│   │       ├── conversations.py    # Conversation endpoints
│   │       └── health.py           # Health check endpoints
│   ├── core/
│   │   └── config.py               # Application configuration
│   ├── models/
│   │   └── transcription.py        # Domain models
│   ├── repositories/
│   │   ├── base.py                 # Repository interface
│   │   └── superwhisper.py         # Superwhisper implementation
│   ├── schemas/
│   │   └── transcription.py        # API schemas
│   ├── services/
│   │   └── transcription_service.py # Business logic
│   ├── static/
│   │   ├── index.html              # Frontend HTML
│   │   ├── styles.css              # Styling
│   │   └── app.js                  # Frontend JavaScript
│   └── main.py                     # FastAPI application
├── tests/
│   ├── test_main.py
│   ├── test_api.py
│   └── test_transcription_service.py
├── data/
│   └── superwhisper/               # Transcription files directory
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── Taskfile.yml
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

### Web Interface
- `GET /` - Main application (serves static frontend)
- `GET /static/*` - Static assets (CSS, JavaScript)

### API Endpoints

#### Health Checks
- `GET /api/v1/health` - Health check endpoint
- `GET /api/v1/ready` - Readiness check endpoint
- `GET /api/v1/live` - Liveness check endpoint

#### Conversations
- `GET /api/v1/conversations` - List all conversations (summary view)
- `GET /api/v1/conversations/{conversation_id}` - Get conversation details with all versions
- `GET /api/v1/conversations/search?q={query}` - Search transcriptions
- `GET /api/v1/conversations/{conversation_id}/audio/{version_id}` - Stream audio file

## Data Directory Structure

The application expects transcription files in the following structure:

```
data/superwhisper/
├── 1234567890/          # Unix timestamp directory
│   ├── metadata.json    # Transcription metadata
│   └── audio.wav        # Audio file (.wav, .mp3, .m4a, or .ogg)
├── 1234567891/
│   ├── metadata.json
│   └── audio.wav
└── ...
```

### Metadata File Format

The `metadata.json` file should contain:

```json
{
  "transcription": "Raw transcription text here...",
  "timecodes": [
    {
      "start_time": 0.0,
      "end_time": 5.5,
      "text": "First segment of transcription"
    },
    {
      "start_time": 5.5,
      "end_time": 12.3,
      "text": "Second segment of transcription"
    }
  ],
  "llm_output": "Processed output from LLM...",
  "duration": 120.5
}
```

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

## Configuration

Create a `.env` file in the project root to customize settings (see `.env.example`):

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

# Transcription Provider
SUPERWHISPER_DIRECTORY=./data/superwhisper
```

### Key Settings

- `SUPERWHISPER_DIRECTORY`: Path to directory containing Superwhisper transcription files
- `DEBUG`: Enable debug mode (not recommended for production)
- `CORS_ORIGINS`: Allowed origins for CORS (customize for your frontend)

## Usage

1. **Configure the transcription directory**: Set `SUPERWHISPER_DIRECTORY` in `.env` to point to your Superwhisper files
2. **Start the application**: Run `task dev` or `uvicorn app.main:app --reload`
3. **Open your browser**: Navigate to `http://localhost:8000`
4. **Browse conversations**: Click on any conversation in the left panel to view details
5. **Search**: Use the search bar at the top to find specific transcriptions
6. **Play audio**: Use the audio player controls to listen and navigate
7. **View versions**: Use the version dropdown to compare different transcription attempts

## Adding New Transcription Providers

To add support for a new transcription provider:

1. Create a new repository class in `app/repositories/` that extends `TranscriptionRepository`
2. Implement the required methods:
   - `get_all_transcriptions()`
   - `get_transcription_by_timestamp()`
   - `read_audio_file()`
3. Update `app/api/dependencies.py` to use your new repository
4. Add configuration settings in `app/core/config.py`

## License

See LICENSE file for details.
