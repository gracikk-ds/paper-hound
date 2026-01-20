# ArXivPaperHound

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A semantic search engine for discovering ArXiv academic papers. Combines vector embeddings, LLM-powered classification and summarization, Notion integration, and a Telegram bot for automated paper discovery workflows.

## Overview

ArXivPaperHound helps researchers stay on top of relevant academic papers by:

- **Semantic Search**: Find papers by meaning using Gemini embeddings and Qdrant vector database
- **Intelligent Classification**: LLM-powered relevance filtering tailored to your research interests
- **Automated Summarization**: Generate concise summaries from PDFs with image extraction
- **Knowledge Management**: Automatically upload paper summaries to Notion databases
- **Interactive Bot**: Search and manage papers via Telegram with subscription notifications
- **Scheduled Workflows**: Daily automated pipeline for continuous paper discovery

## Features

- **Vector-based semantic search** using Google Gemini embeddings (3072 dimensions) and Qdrant
- **LLM-powered paper classification** with customizable prompts per research category
- **PDF summarization** with Gemini vision model and automatic image extraction
- **Notion integration** for organized paper storage with categories and metadata
- **Telegram bot** for interactive search, subscriptions, and notifications
- **Scheduled daily jobs** with configurable timezone (default: 06:00 Europe/Moscow)
- **Processing cache** to avoid re-classifying and re-summarizing papers
- **REST API** for programmatic access to all features
- **Prometheus metrics** for monitoring

## Architecture

```text
                                    ArXiv API
                                        |
                                        v
                              +-------------------+
                              |   ArxivFetcher    |
                              +-------------------+
                                        |
                                        v
                              +-------------------+
                              | EmbeddingService  |  <-- Gemini Embedding API
                              +-------------------+
                                        |
                                        v
                              +-------------------+
                              | QdrantVectorStore |  <-- Qdrant DB
                              +-------------------+
                                        |
            +--------------+------------+------------+--------------+
            |              |                         |              |
            v              v                         v              v
      +----------+   +-----------+            +------------+  +----------+
      |  Search  |   | Classifier|            | Summarizer |  | Telegram |
      +----------+   +-----------+            +------------+  |   Bot    |
            |              |                         |        +----------+
            |              v                         v              |
            |        +------------+           +------------+        |
            |        |   Cache    |           |   Notion   |        |
            |        +------------+           +------------+        |
            |                                       |              |
            +---------------+-----------------------+--------------+
                            |
                            v
                      +-----------+
                      |   User    |
                      +-----------+
```

### Data Flow

1. **Ingest**: Fetch papers from ArXiv API for specified date range and categories
2. **Embed**: Generate vector embeddings via Gemini embedding model
3. **Store**: Save papers with embeddings in Qdrant vector database
4. **Search**: Perform semantic similarity search based on user queries
5. **Classify**: Filter papers by relevance using LLM classifier
6. **Summarize**: Generate markdown summaries from PDFs with extracted images
7. **Upload**: Push summaries to Notion database with proper formatting
8. **Notify**: Send Telegram notifications to subscribed users

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose (recommended)
- Google Cloud account with Vertex AI enabled
- Notion integration token
- Telegram bot token
- S3-compatible storage (AWS S3, MinIO, etc.)

### Docker Deployment (Recommended)

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/ArXivPaperHound.git
    cd ArXivPaperHound
    ```

2. Copy the environment template and configure:

    ```bash
    cp template.env .env
    # Edit .env with your credentials
    ```

3. Start the services:

    ```bash
    docker-compose up -d
    ```

The application will be available at `http://localhost:8001`.

### Local Development

1. Create and activate a virtual environment:

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

2. Install dependencies:

    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt  # For development
    ```

3. Start Qdrant (via Docker):

    ```bash
    docker-compose up -d qdrant
    ```

4. Run the application:

    ```bash
    uvicorn src.app:create_app --factory --reload
    ```

## Configuration

### Environment Variables

| Variable                         | Required | Default                 | Description                                    |
| -------------------------------- | -------- | ----------------------- | ---------------------------------------------- |
| `GOOGLE_APPLICATION_CREDENTIALS` | Yes      | -                       | Path to Google Cloud service account JSON      |
| `TELEGRAM_TOKEN`                 | Yes      | -                       | Telegram bot API token from BotFather          |
| `TELEGRAM_CHAT_ID`               | Yes      | -                       | Chat ID for admin notifications                |
| `NOTION_TOKEN`                   | Yes      | -                       | Notion integration API token                   |
| `NOTION_DATABASE_ID`             | No       | -                       | Notion database ID for paper storage           |
| `NOTION_COMMAND_DATABASE_ID`     | No       | -                       | Notion database ID for category settings       |
| `AWS_ACCESS_KEY_ID`              | Yes      | -                       | S3-compatible storage access key               |
| `AWS_SECRET_ACCESS_KEY`          | Yes      | -                       | S3-compatible storage secret key               |
| `ENDPOINT_URL`                   | Yes      | -                       | S3 endpoint URL                                |
| `S3_BUCKET`                      | Yes      | -                       | S3 bucket name for images                      |
| `QDRANT_HOST`                    | No       | `localhost`             | Qdrant server hostname                         |
| `QDRANT_PORT`                    | No       | `6333`                  | Qdrant server port                             |
| `QDRANT_API_KEY`                 | No       | -                       | Qdrant API key (if authentication enabled)     |
| `GEMINI_MODEL_NAME`              | No       | `gemini-3-flash-preview`| Gemini model for classification/summarization  |
| `EMBEDDING_SERVICE_MODEL_NAME`   | No       | `gemini-embedding-001`  | Embedding model name                           |
| `SCHEDULER_TIMEZONE`             | No       | `Europe/Moscow`         | Timezone for scheduled jobs                    |
| `CLASSIFIER_THINKING_LEVEL`      | No       | `LOW`                   | Extended thinking level for classifier         |
| `SUMMARIZER_THINKING_LEVEL`      | No       | `MEDIUM`                | Extended thinking level for summarizer         |

### Example `.env` File

```bash
GOOGLE_APPLICATION_CREDENTIALS=credentials/gen_lang_client.json
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
NOTION_TOKEN=ntn_your_notion_token
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ENDPOINT_URL=https://s3.your-provider.com
S3_BUCKET=your-bucket-name
```

## Usage

### REST API

#### Processor Endpoints (`/processor`)

| Endpoint               | Method | Description                            |
| ---------------------- | ------ | -------------------------------------- |
| `/insert-papers`       | POST   | Ingest papers from ArXiv for date range|
| `/search-papers`       | POST   | Semantic search for papers             |
| `/find-similar-papers` | POST   | Find papers similar to a reference     |
| `/delete-papers`       | DELETE | Remove papers from the database        |
| `/count-papers`        | GET    | Get total paper count                  |

#### Workflow Endpoints (`/workflow`)

| Endpoint | Method | Description                       |
| -------- | ------ | --------------------------------- |
| `/run`   | POST   | Trigger the full workflow pipeline|

#### Health Endpoints (`/health`)

| Endpoint   | Method | Description        |
| ---------- | ------ | ------------------ |
| `/status`  | GET    | Health check       |
| `/metrics` | GET    | Prometheus metrics |

### Telegram Bot Commands

#### Paper Discovery

- `/search <query> [k:N] [t:N] [from:DATE] [to:DATE]` - Semantic search with options
  - `k:N` - Return top N results (default: 10)
  - `t:N` - Similarity threshold 0-100 (default: 65)
  - `from:DATE`, `to:DATE` - Date range filter (YYYY-MM-DD)
- `/paper <paper_id>` - Get paper details with action buttons
- `/similar <paper_id> [k:N] [t:N] [from:DATE] [to:DATE]` - Find similar papers
- `/topics` - List available research categories

#### Paper Management

- `/summarize <paper_id|url> [cat:CategoryName]` - Generate and upload summary to Notion

#### Subscriptions (Personal)

- `/subscribe` - Subscribe to research topics
- `/unsubscribe` - Manage your subscriptions
- `/subscriptions` - List your active subscriptions

#### Subscriptions (Group - Admin Only)

- `/groupsubscribe` - Subscribe group to a topic
- `/groupunsubscribe` - Remove group subscription
- `/groupsubscriptions` - View group subscriptions

#### Storage Management

- `/insert` - Fetch papers for a date range
- `/stats` - View database statistics

#### General

- `/start` - Welcome message and quick start guide
- `/help` - Command reference

## External Services Setup

### Qdrant Vector Database

Qdrant stores paper embeddings for semantic search. Using Docker:

```bash
docker run -p 6333:6333 -v $(pwd)/storage/qdrant_storage:/qdrant/storage qdrant/qdrant
```

Collections created automatically:

- `arxiv_papers` - Paper embeddings and metadata
- `arxiv_processing_cache` - Classification/summarization cache

### Google Cloud (Vertex AI)

1. Create a Google Cloud project
2. Enable the Vertex AI API
3. Create a service account with Vertex AI User role
4. Download the JSON credentials file
5. Set `GOOGLE_APPLICATION_CREDENTIALS` to the file path

### Notion Integration

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create a new integration
3. Copy the integration token
4. Share your target database with the integration
5. Copy the database ID from the URL

### S3-Compatible Storage

Any S3-compatible service works (AWS S3, MinIO, Cloudflare R2, etc.):

1. Create a bucket for paper images
2. Generate access credentials
3. Configure endpoint URL if not AWS

### Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the API token
4. Get your chat ID (message the bot and check updates API)

## Development

### Project Structure

```text
ArXivPaperHound/
├── src/
│   ├── app.py                 # FastAPI application entry point
│   ├── settings.py            # Configuration management
│   ├── containers/            # Dependency injection
│   ├── routes/                # API endpoints
│   ├── service/
│   │   ├── workflow.py        # Main orchestration
│   │   ├── processor.py       # Paper processing
│   │   ├── ai_researcher/     # LLM services (classifier, summarizer)
│   │   ├── vector_db/         # Qdrant integration
│   │   ├── arxiv/             # ArXiv API client
│   │   └── notion_db/         # Notion integration
│   └── utils/                 # Utilities and schemas
├── telegram_bot/
│   ├── bot.py                 # Bot initialization
│   ├── handlers/              # Command handlers
│   ├── subscriptions.py       # Subscription management
│   └── notifications.py       # Notification system
├── tests/                     # Test suite
├── prompts/                   # LLM prompt templates
├── storage/                   # Local storage directories
├── docker-compose.yml         # Docker services
├── Dockerfile                 # Application container
├── justfile                   # Just command recipes
└── pyproject.toml             # Project configuration
```

### Running Tests

```bash
# Run all tests
just test

# Run specific test file
just test tests/test_workflow_endpoints.py

# Run with pattern matching
pytest -k "test_search"

# Generate coverage report
just coverage
```

### Code Quality

```bash
# Format and lint with Ruff
just lint

# Run pre-commit hooks
pre-commit run --all-files
```

### Just Commands Reference

```bash
just list      # Show available commands
just lint      # Format and lint with Ruff
just test      # Run all tests
just coverage  # Generate HTML coverage report
just build     # Build project package
just clean     # Remove build artifacts
just version   # Print current version
just tag       # Tag and push version to GitHub
```

## Deployment

### Docker Compose

The included `docker-compose.yml` sets up:

- **qdrant**: Vector database on port 6333
- **app**: FastAPI application on port 8001

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./storage/qdrant_storage:/qdrant/storage

  app:
    build: .
    ports:
      - "8001:8001"
    depends_on:
      - qdrant
    env_file:
      - .env
```

### Production Considerations

- Use `QDRANT_API_KEY` for Qdrant authentication
- Configure proper logging and monitoring
- Set up backup for Qdrant storage
- Use secrets management for credentials
- Consider running multiple Gunicorn workers for higher throughput

### Scheduled Jobs

The application automatically schedules a daily workflow at 06:00 (configurable via `SCHEDULER_TIMEZONE`):

- Fetches papers from the last 4 days
- Processes all configured categories
- Classifies and summarizes relevant papers
- Uploads to Notion and sends Telegram notifications

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025, Gordeev A.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests and linting (`just lint && just test`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request
