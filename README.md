# ArXivPaperHound

![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A semantic search engine for discovering ArXiv academic papers. Combines vector embeddings, LLM-powered classification and summarization, Notion integration, and a Telegram bot for automated paper discovery workflows.

## Features

- **Semantic Search**: Vector-based paper search using Gemini embeddings and Qdrant
- **AI Classification**: LLM-powered relevance filtering with customizable prompts per category
- **Smart Summarization**: PDF processing with Gemini vision model and automatic image extraction
- **Notion Integration**: Automated upload of paper summaries with metadata and categorization
- **Telegram Bot**: Interactive search, subscriptions, and automatic notifications
- **Scheduled Workflows**: Daily automated pipeline for continuous paper discovery
- **Processing Cache**: Avoid re-processing papers with intelligent caching
- **REST API**: Programmatic access with comprehensive endpoints

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Google Cloud account with Vertex AI API enabled ([setup guide](docs/SETUP.md#google-cloud--vertex-ai))
- Notion integration token ([setup guide](docs/SETUP.md#notion-integration))
- Telegram bot token ([setup guide](docs/SETUP.md#telegram-bot))
- S3-compatible storage credentials ([setup guide](docs/SETUP.md#s3-compatible-storage))

Full setup instructions: [docs/SETUP.md](docs/SETUP.md)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/ArXivPaperHound.git
   cd ArXivPaperHound
   ```

2. **Configure environment**

   ```bash
   cp template.env .env
   # Edit .env with your credentials (see Configuration section below)
   ```

3. **Start the application**

   ```bash
   docker-compose up -d
   ```

The API will be available at `http://localhost:8001` and the Telegram bot will start automatically.

Verify it's running:

```bash
curl http://localhost:8001/health/ping
# Expected: "🏓 pong!"
```

## Configuration

### Required Environment Variables

Configure these in your `.env` file:

```bash
# Google Cloud / Vertex AI
GOOGLE_APPLICATION_CREDENTIALS=credentials/gen_lang_client.json

# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Notion
NOTION_TOKEN=ntn_your_notion_token
NOTION_DATABASE_ID=your_database_id  # Optional

# S3 Storage
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
ENDPOINT_URL=https://s3.your-provider.com
S3_BUCKET=your-bucket-name
```

See all configuration options in [`template.env`](template.env) or the [setup guide](docs/SETUP.md).

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

1. **Ingest**: Fetch papers from ArXiv API for configured date ranges and categories
2. **Embed**: Generate 3072-dimensional vector embeddings using Gemini
3. **Store**: Save papers with embeddings in Qdrant vector database
4. **Classify**: Filter papers by relevance using LLM with category-specific prompts
5. **Summarize**: Generate markdown summaries from PDFs with extracted images
6. **Notify**: Send results to Notion and Telegram subscribers

## Usage

### REST API

Key endpoints (see [full API documentation](docs/API.md)):

| Endpoint | Method | Description |
| --- | --- | --- |
| `/processor/insert-papers` | POST | Ingest papers from ArXiv for a date range |
| `/processor/search-papers` | POST | Semantic search for papers by query |
| `/processor/find-similar-papers` | POST | Find papers similar to a reference paper |
| `/workflow/run` | POST | Trigger the full discovery pipeline |
| `/health/ping` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

Example: Search for papers

```bash
curl -X POST "http://localhost:8001/processor/search-papers" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "quantum computing algorithms",
    "top_k": 5,
    "threshold": 0.7
  }'
```

Full API reference: [docs/API.md](docs/API.md)

### Telegram Bot

#### Discovery Commands

- `/search <query> [k:N] [t:N] [from:DATE] [to:DATE]` - Semantic search with filters
- `/paper <paper_id>` - Get detailed paper information
- `/similar <paper_id> [k:N]` - Find similar papers
- `/topics` - List available research categories

#### Management Commands

- `/summarize <paper_id|url> [cat:Category]` - Generate summary and upload to Notion
- `/insert` - Fetch papers for a date range
- `/stats` - View database statistics

#### Subscription Commands

- `/subscribe` - Subscribe to research topics for automatic notifications
- `/unsubscribe` - Manage subscriptions
- `/subscriptions` - List active subscriptions

#### Group Commands (Admin Only)

- `/groupsubscribe` - Subscribe group to topics
- `/groupunsubscribe` - Remove group subscriptions
- `/groupsubscriptions` - View group subscriptions

**Search syntax examples:**

```bash
/search quantum computing k:10 t:70
/search machine learning for drug discovery from:2025-01-01 to:2025-01-31
/similar 2501.12345 k:5
```

## Development

### Local Setup

For local development without Docker, see [CONTRIBUTING.md](CONTRIBUTING.md).

### Running Tests

```bash
just test
```

### Code Quality

```bash
just lint
```

For detailed development guidelines, project structure, and contribution process, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Scheduled Jobs

The application runs a daily workflow at 06:00 (configurable via `SCHEDULER_TIMEZONE` in `.env`):

- Fetches papers from the last 4 days
- Processes all configured research categories
- Classifies and summarizes relevant papers
- Uploads to Notion and sends Telegram notifications

## Troubleshooting

**Qdrant connection errors:**

- Verify Qdrant is running: `docker ps | grep qdrant`
- Check `QDRANT_HOST` and `QDRANT_PORT` in `.env`

**Google Cloud authentication errors:**

- Verify `GOOGLE_APPLICATION_CREDENTIALS` path is correct
- Ensure Vertex AI API is enabled in your Google Cloud project

**Telegram bot not responding:**

- Check `TELEGRAM_TOKEN` is valid
- Verify bot is running: check logs with `docker-compose logs app`

**S3 upload failures:**

- Verify S3 credentials and `ENDPOINT_URL`
- Check bucket exists and permissions are correct

For detailed troubleshooting and service setup, see [docs/SETUP.md](docs/SETUP.md).

## Documentation

- [External Services Setup Guide](docs/SETUP.md) - Detailed configuration for Qdrant, Google Cloud, Notion, S3, and Telegram
- [REST API Reference](docs/API.md) - Complete API documentation with examples
- [Contributing Guide](CONTRIBUTING.md) - Development setup, project structure, and contribution guidelines

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Copyright (c) 2025, Gordeev A.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Setting up your development environment
- Running tests and linting
- Code style and best practices
- Pull request process

Quick start for contributors:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests and linting: `just lint && just test`
5. Commit: `git commit -m 'feat: add amazing feature'`
6. Push and open a Pull Request
