# Contributing to ArXivPaperHound

Thank you for your interest in contributing to ArXivPaperHound! This guide will help you get started with development.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Just Commands Reference](#just-commands-reference)
- [Pull Request Process](#pull-request-process)

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Git
- Docker and Docker Compose (for Qdrant)
- Google Cloud account with Vertex AI enabled
- Notion integration token
- Telegram bot token
- S3-compatible storage credentials

### Local Development Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/ArXivPaperHound.git
   cd ArXivPaperHound
   ```

2. **Create Virtual Environment**

   ```bash
   python -m venv .venv
   ```

3. **Activate Virtual Environment**

   On macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

   On Windows:

   ```cmd
   .venv\Scripts\activate
   ```

4. **Install Dependencies**

   ```bash
   # Production dependencies
   pip install -r requirements.txt

   # Development dependencies (linting, testing, etc.)
   pip install -r requirements-dev.txt
   ```

5. **Install Pre-commit Hooks** (Optional but recommended)

   ```bash
   pre-commit install
   ```

6. **Configure Environment Variables**

   ```bash
   cp template.env .env
   # Edit .env with your credentials
   ```

   See [docs/SETUP.md](docs/SETUP.md) for detailed configuration instructions.

7. **Start Qdrant**

   Using Docker Compose:

   ```bash
   docker-compose up -d qdrant
   ```

   Or standalone Docker:

   ```bash
   docker run -p 6333:6333 \
     -v $(pwd)/storage/qdrant_storage:/qdrant/storage \
     qdrant/qdrant
   ```

8. **Run the Application**

   Using Uvicorn directly:

   ```bash
   uvicorn src.app:create_app --factory --reload --port 8001
   ```

   Or using the Just command:

   ```bash
   just run
   ```

9. **Verify Setup**

   ```bash
   curl http://localhost:8001/health/ping
   # Expected: "🏓 pong!"
   ```

### Development with Telegram Bot

To run the Telegram bot locally:

```bash
python telegram_bot/bot.py
```

The bot will start polling for messages. You can test it by messaging your bot on Telegram.

## Project Structure

```text
ArXivPaperHound/
├── src/                          # Main application source code
│   ├── app.py                    # FastAPI application factory
│   ├── settings.py               # Configuration management (pydantic-settings)
│   │
│   ├── containers/               # Dependency injection
│   │   └── containers.py         # AppContainer with service singletons
│   │
│   ├── routes/                   # API endpoints
│   │   ├── routers.py            # Router definitions
│   │   ├── health_endpoints.py  # Health check endpoints
│   │   ├── processor_endpoints.py  # Paper processing API
│   │   ├── workflow_endpoints.py   # Workflow trigger API
│   │   └── ai_endpoint.py        # AI-related endpoints
│   │
│   ├── service/                  # Core business logic
│   │   ├── workflow.py           # Main workflow orchestration
│   │   ├── processor.py          # Paper processing coordinator
│   │   │
│   │   ├── ai_researcher/        # LLM-based services
│   │   │   ├── classifier.py     # Paper relevance classifier
│   │   │   └── summarizer.py     # PDF summarization with vision
│   │   │
│   │   ├── vector_db/            # Vector database integration
│   │   │   ├── embedder.py       # Gemini embedding service
│   │   │   ├── vector_storage.py # Qdrant client wrapper
│   │   │   └── processing_cache.py  # Caching layer
│   │   │
│   │   ├── arxiv/                # ArXiv API integration
│   │   │   ├── api.py            # ArXiv API client
│   │   │   └── fetcher.py        # Paper fetching logic
│   │   │
│   │   └── notion_db/            # Notion integration
│   │       ├── client.py         # Notion API client
│   │       └── uploader.py       # Paper upload logic
│   │
│   └── utils/                    # Utilities and schemas
│       ├── schemas.py            # Pydantic models for requests/responses
│       ├── logging_config.py     # Logging configuration
│       └── helpers.py            # Helper functions
│
├── telegram_bot/                 # Telegram bot application
│   ├── bot.py                    # Bot initialization and entry point
│   ├── handlers/                 # Command and callback handlers
│   │   ├── search_handlers.py   # Search and discovery commands
│   │   ├── paper_handlers.py    # Paper management commands
│   │   ├── subscription_handlers.py  # Subscription commands
│   │   └── admin_handlers.py    # Admin-only commands
│   ├── subscriptions.py          # Subscription management logic
│   └── notifications.py          # Notification system
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures and configuration
│   ├── test_workflow_endpoints.py   # Workflow API tests
│   ├── test_processor_endpoints.py  # Processor API tests
│   ├── test_classifier.py        # Classifier unit tests
│   ├── test_summarizer.py        # Summarizer unit tests
│   └── test_embeddings.py        # Embedding service tests
│
├── prompts/                      # LLM prompt templates
│   ├── classifier/               # Classification prompts by category
│   │   ├── default.txt
│   │   ├── machine_learning.txt
│   │   └── quantum_computing.txt
│   └── summarizer/
│       └── summarize.txt
│
├── storage/                      # Local storage directories
│   ├── qdrant_storage/           # Qdrant data persistence
│   ├── pdfs/                     # Downloaded PDFs cache
│   └── images/                   # Extracted images cache
│
├── credentials/                  # Service account credentials (gitignored)
│   └── gen_lang_client.json      # Google Cloud service account
│
├── docs/                         # Documentation
│   ├── SETUP.md                  # External services setup guide
│   └── API.md                    # REST API reference
│
├── docker-compose.yml            # Docker services configuration
├── Dockerfile                    # Application container image
├── justfile                      # Just command recipes
├── pyproject.toml                # Project metadata and tool configuration
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
├── template.env                  # Environment variable template
├── .env                          # Local environment config (gitignored)
├── .gitignore                    # Git ignore rules
├── .pre-commit-config.yaml       # Pre-commit hooks configuration
├── README.md                     # Project overview and quick start
├── CONTRIBUTING.md               # This file
├── LICENSE                       # MIT license
└── CLAUDE.md                     # Project instructions for Claude Code
```

## Development Workflow

### Making Changes

1. **Create a Feature Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**

   - Write code following the existing style
   - Add tests for new functionality
   - Update documentation if needed

3. **Run Tests and Linting**

   ```bash
   just lint    # Format and lint code
   just test    # Run test suite
   ```

4. **Commit Your Changes**

   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

   Follow conventional commit format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for test additions/changes
   - `refactor:` for code refactoring
   - `chore:` for maintenance tasks

5. **Push and Create Pull Request**

   ```bash
   git push origin feature/your-feature-name
   ```

   Then create a pull request on GitHub.

### Adding New Features

When adding significant features:

1. **Update Tests**: Add comprehensive test coverage
2. **Update Documentation**:
   - Update README.md if user-facing
   - Update API.md for new endpoints
   - Update SETUP.md for new configuration
3. **Update CLAUDE.md**: Document architecture changes for AI assistance
4. **Update Type Hints**: Maintain full type coverage

## Testing

### Test-Driven Development

We prefer Test-Driven Development (TDD):

1. Write failing tests first
2. Implement minimal code to pass tests
3. Refactor while keeping tests green

### Running Tests

```bash
# Run all tests
just test

# Run specific test file
just test tests/test_workflow_endpoints.py

# Run tests matching a pattern
pytest -k "test_search"

# Run with verbose output
pytest -v

# Run with coverage report
just coverage
```

### Test Coverage

We aim for >80% test coverage. Check coverage with:

```bash
just coverage
```

This generates an HTML report at `htmlcov/index.html`.

### Writing Tests

Example test structure:

```python
import pytest
from src.service.processor import PapersProcessor


def test_search_papers_returns_results(processor: PapersProcessor):
    """Test that search returns relevant papers."""
    # Arrange
    query = "machine learning"

    # Act
    results = processor.search_papers(query, top_k=5, threshold=0.65)

    # Assert
    assert len(results) > 0
    assert all(r.score >= 0.65 for r in results)


@pytest.mark.parametrize("query,expected_count", [
    ("deep learning", 10),
    ("quantum computing", 5),
])
def test_search_with_different_queries(processor, query, expected_count):
    """Test search with various queries."""
    results = processor.search_papers(query, top_k=expected_count)
    assert len(results) <= expected_count
```

## Code Quality

### Linting and Formatting

We use Ruff for both linting and formatting:

```bash
# Format and lint
just lint

# Check without modifying
ruff check .
ruff format --check .
```

### Pre-commit Hooks

Pre-commit hooks automatically run linting before commits:

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### Type Checking

We use Python type hints throughout the codebase. While we don't currently run mypy in CI, please:

- Add type hints to all function signatures
- Use proper generic types (list[str], dict[str, int], etc.)
- Import types from `typing` when needed

### Code Style Guidelines

- **Line length**: Max 120 characters
- **Imports**: Organized by standard library, third-party, local
- **Docstrings**: Google style for all public functions/classes
- **Naming**:
  - Classes: PascalCase
  - Functions/variables: snake_case
  - Constants: UPPER_SNAKE_CASE
  - Private members: _leading_underscore

Example:

```python
from datetime import date

from pydantic import BaseModel

from src.utils.schemas import Paper


class PaperProcessor:
    """Process and analyze arXiv papers.

    Attributes:
        vector_store: Vector database client for embeddings.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        """Initialize the processor.

        Args:
            vector_store: Vector database client instance.
        """
        self.vector_store = vector_store

    def search_papers(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.65,
    ) -> list[Paper]:
        """Search for papers using semantic similarity.

        Args:
            query: Natural language search query.
            top_k: Maximum number of results to return.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of Paper objects ordered by relevance score.

        Raises:
            ValueError: If threshold is not between 0 and 1.
        """
        if not 0 <= threshold <= 1:
            raise ValueError("Threshold must be between 0 and 1")

        # Implementation here
        return []
```

## Just Commands Reference

We use [Just](https://github.com/casey/just) as a command runner. Here are all available commands:

### Development Commands

```bash
# Show all available commands
just list

# Run the application with auto-reload
just run

# Run the Telegram bot
just bot
```

### Testing Commands

```bash
# Run all tests
just test

# Run specific test file
just test tests/test_workflow_endpoints.py

# Generate HTML coverage report
just coverage
```

### Code Quality Commands

```bash
# Format code and run linter
just lint

# Check formatting without modifying
just check

# Run pre-commit hooks on all files
just pre-commit
```

### Build Commands

```bash
# Build Python package
just build

# Clean build artifacts
just clean

# Print current version
just version
```

### Release Commands

```bash
# Tag current version and push to GitHub
just tag

# Build and publish to PyPI (if configured)
just publish
```

### Docker Commands

```bash
# Build Docker image
just docker-build

# Run with Docker Compose
just docker-up

# Stop Docker services
just docker-down

# View logs
just docker-logs
```

## Pull Request Process

1. **Ensure Tests Pass**

   All tests must pass and coverage should not decrease.

2. **Update Documentation**

   Update relevant documentation for your changes.

3. **Follow Code Style**

   Run `just lint` before committing.

4. **Write Clear Commit Messages**

   Use conventional commits format with clear descriptions.

5. **Describe Your Changes**

   In the PR description, explain:
   - What problem does this solve?
   - How did you solve it?
   - Are there any breaking changes?
   - How can reviewers test this?

6. **Request Review**

   Tag relevant maintainers for review.

7. **Address Feedback**

   Respond to review comments and make requested changes.

8. **Squash Commits** (if requested)

   Maintainers may ask you to squash commits before merging.

## Common Development Tasks

### Adding a New LLM Prompt

1. Create prompt file in `prompts/classifier/` or `prompts/summarizer/`
2. Use clear variable placeholders (e.g., `{query}`, `{abstract}`)
3. Test prompt with actual data
4. Update tests to verify prompt loading

### Adding a New API Endpoint

1. Define request/response schemas in `src/utils/schemas.py`
2. Implement endpoint in appropriate router file
3. Add endpoint to router in `src/routes/routers.py`
4. Write tests in `tests/test_*_endpoints.py`
5. Update `docs/API.md` with endpoint documentation

### Adding a New Telegram Command

1. Create handler function in `telegram_bot/handlers/`
2. Register handler in `telegram_bot/bot.py`
3. Add command to bot description (via BotFather)
4. Update README with command documentation
5. Write integration tests if applicable

### Modifying the Workflow

1. Update `src/service/workflow.py`
2. Ensure backward compatibility or add migration path
3. Update tests in `tests/test_workflow_endpoints.py`
4. Document changes in commit message

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with reproduction steps
- **Feature Requests**: Open a GitHub Issue with use case description

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
