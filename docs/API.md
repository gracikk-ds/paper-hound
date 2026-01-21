# REST API Documentation

Complete reference for the ArXivPaperHound REST API.

Base URL: `http://localhost:8001`

## Table of Contents

- [Paper Processing Endpoints](#paper-processing-endpoints)
- [Workflow Endpoints](#workflow-endpoints)
- [Health Check Endpoints](#health-check-endpoints)
- [Request/Response Schemas](#requestresponse-schemas)
- [Error Handling](#error-handling)

## Paper Processing Endpoints

All processor endpoints are prefixed with `/processor`.

### Insert Papers

Fetch and store arXiv papers from a date range.

**Endpoint:** `POST /processor/insert-papers`

**Request Body:**

```json
{
  "start_date_str": "2025-01-01",
  "end_date_str": "2025-01-07"
}
```

**Parameters:**

- `start_date_str` (string, required): Start date in YYYY-MM-DD format (inclusive)
- `end_date_str` (string, required): End date in YYYY-MM-DD format (inclusive)

**Response:** `201 Created`

**Example:**

```bash
curl -X POST "http://localhost:8001/processor/insert-papers" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date_str": "2025-01-01",
    "end_date_str": "2025-01-07"
  }'
```

**Errors:**

- `400 Bad Request`: Invalid date format

---

### Search Papers

Perform semantic search for papers using natural language queries.

**Endpoint:** `POST /processor/search-papers`

**Request Body:**

```json
{
  "query": "quantum computing algorithms",
  "top_k": 10,
  "threshold": 0.65,
  "start_date_str": "2024-01-01",
  "end_date_str": "2025-01-31"
}
```

**Parameters:**

- `query` (string, required): Natural language search query
- `top_k` (integer, optional): Maximum number of results to return. Default: 10
- `threshold` (float, optional): Minimum similarity score (0-1). Default: 0.65
- `start_date_str` (string, optional): Filter results from this date (YYYY-MM-DD)
- `end_date_str` (string, optional): Filter results until this date (YYYY-MM-DD)

**Response:** `200 OK`

```json
[
  {
    "id": "2501.12345",
    "title": "Advances in Quantum Computing Algorithms",
    "authors": ["John Doe", "Jane Smith"],
    "abstract": "We present novel quantum computing algorithms...",
    "published_date": "2025-01-15",
    "pdf_url": "https://arxiv.org/pdf/2501.12345.pdf",
    "score": 0.89
  }
]
```

**Example:**

```bash
curl -X POST "http://localhost:8001/processor/search-papers" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning for drug discovery",
    "top_k": 5,
    "threshold": 0.7
  }'
```

---

### Get Paper by ID

Retrieve detailed information about a specific paper.

**Endpoint:** `GET /processor/papers/{paper_id}`

**Path Parameters:**

- `paper_id` (string, required): The arXiv paper ID (e.g., "2501.12345")

**Response:** `200 OK`

```json
{
  "id": "2501.12345",
  "title": "Advances in Quantum Computing Algorithms",
  "authors": ["John Doe", "Jane Smith"],
  "abstract": "We present novel quantum computing algorithms...",
  "published_date": "2025-01-15",
  "pdf_url": "https://arxiv.org/pdf/2501.12345.pdf"
}
```

**Example:**

```bash
curl -X GET "http://localhost:8001/processor/papers/2501.12345"
```

**Errors:**

- `404 Not Found`: Paper not found in database

---

### Find Similar Papers

Find papers similar to a reference paper using vector similarity.

**Endpoint:** `POST /processor/find-similar-papers`

**Request Body:**

```json
{
  "paper_id": "2501.12345",
  "top_k": 5,
  "threshold": 0.65,
  "start_date_str": "2024-01-01",
  "end_date_str": "2025-01-31"
}
```

**Parameters:**

- `paper_id` (string, required): The arXiv ID of the reference paper
- `top_k` (integer, optional): Maximum number of similar papers to return. Default: 5
- `threshold` (float, optional): Minimum similarity score (0-1). Default: 0.65
- `start_date_str` (string, optional): Filter results from this date (YYYY-MM-DD)
- `end_date_str` (string, optional): Filter results until this date (YYYY-MM-DD)

**Response:** `200 OK`

```json
[
  {
    "id": "2501.23456",
    "title": "Related Work on Quantum Algorithms",
    "authors": ["Alice Brown"],
    "abstract": "Building upon previous quantum computing research...",
    "published_date": "2025-01-20",
    "pdf_url": "https://arxiv.org/pdf/2501.23456.pdf",
    "score": 0.82
  }
]
```

**Example:**

```bash
curl -X POST "http://localhost:8001/processor/find-similar-papers" \
  -H "Content-Type: application/json" \
  -d '{
    "paper_id": "2501.12345",
    "top_k": 5,
    "threshold": 0.7
  }'
```

---

### Delete Papers

Permanently remove papers from the database.

**Endpoint:** `POST /processor/delete-papers`

**Request Body:**

```json
{
  "paper_ids": ["2501.12345", "2501.23456"]
}
```

**Parameters:**

- `paper_ids` (array of strings, required): List of arXiv paper IDs to delete

**Response:** `204 No Content`

**Example:**

```bash
curl -X POST "http://localhost:8001/processor/delete-papers" \
  -H "Content-Type: application/json" \
  -d '{
    "paper_ids": ["2501.12345", "2501.23456"]
  }'
```

---

### Count Papers

Get the total number of papers in the database.

**Endpoint:** `GET /processor/count-papers`

**Response:** `200 OK`

```json
15420
```

**Example:**

```bash
curl -X GET "http://localhost:8001/processor/count-papers"
```

---

## Workflow Endpoints

All workflow endpoints are prefixed with `/workflow`.

### Run Workflow

Trigger the complete paper discovery and summarization workflow.

**Endpoint:** `POST /workflow/run`

**Request Body:**

```json
{
  "start_date_str": "2025-01-15",
  "end_date_str": "2025-01-21",
  "skip_ingestion": false,
  "use_classifier": true,
  "top_k": 10,
  "category": "Machine Learning"
}
```

**Parameters:**

- `start_date_str` (string, optional): Start date for paper fetching (YYYY-MM-DD). Default: yesterday
- `end_date_str` (string, optional): End date for paper fetching (YYYY-MM-DD). Default: today
- `skip_ingestion` (boolean, optional): Skip fetching new papers if true. Default: false
- `use_classifier` (boolean, optional): Use LLM classifier to filter papers. Default: true
- `top_k` (integer, optional): Number of top papers to process. Default: 10
- `category` (string, optional): Research category name for prompt selection

**Response:** `202 Accepted`

```json
{
  "status": "accepted",
  "message": "Workflow started in background."
}
```

**Description:**

The workflow runs asynchronously in the background and performs:

1. **Ingestion** (if not skipped): Fetch papers from arXiv for the date range
2. **Search**: Find relevant papers using semantic search
3. **Classification** (if enabled): Filter papers by relevance using LLM
4. **Summarization**: Generate summaries for top papers
5. **Upload**: Push summaries to Notion database
6. **Notification**: Send Telegram notifications to subscribers

**Example:**

```bash
curl -X POST "http://localhost:8001/workflow/run" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date_str": "2025-01-15",
    "end_date_str": "2025-01-21",
    "use_classifier": true,
    "top_k": 5,
    "category": "Deep Learning"
  }'
```

**Errors:**

- `400 Bad Request`: Invalid date format

---

## Health Check Endpoints

All health endpoints are prefixed with `/health`.

### Ping

Simple connectivity test.

**Endpoint:** `GET /health/ping`

**Response:** `200 OK`

```json
"🏓 pong!"
```

**Example:**

```bash
curl -X GET "http://localhost:8001/health/ping"
```

---

### Health Checker

Service health status check.

**Endpoint:** `GET /health/health_checker`

**Response:** `200 OK` (empty body)

**Example:**

```bash
curl -X GET "http://localhost:8001/health/health_checker"
```

---

### URL List

Get all available API routes.

**Endpoint:** `GET /health/url_list`

**Response:** `200 OK`

```json
[
  {
    "path": "/health/ping",
    "name": "ping"
  },
  {
    "path": "/processor/search-papers",
    "name": "search_papers"
  }
]
```

**Example:**

```bash
curl -X GET "http://localhost:8001/health/url_list"
```

---

### Metrics

Prometheus metrics endpoint.

**Endpoint:** `GET /metrics`

**Response:** `200 OK` (Prometheus text format)

**Example:**

```bash
curl -X GET "http://localhost:8001/metrics"
```

---

## Request/Response Schemas

### Paper Object

```json
{
  "id": "2501.12345",
  "title": "Paper Title",
  "authors": ["Author 1", "Author 2"],
  "abstract": "Paper abstract text...",
  "published_date": "2025-01-15",
  "pdf_url": "https://arxiv.org/pdf/2501.12345.pdf",
  "score": 0.89  // Only present in search/similarity results
}
```

### Date Range Request

```json
{
  "start_date_str": "2025-01-01",
  "end_date_str": "2025-01-07"
}
```

### Search Request

```json
{
  "query": "search query text",
  "top_k": 10,
  "threshold": 0.65,
  "start_date_str": "2024-01-01",  // Optional
  "end_date_str": "2025-01-31"     // Optional
}
```

### Similar Papers Request

```json
{
  "paper_id": "2501.12345",
  "top_k": 5,
  "threshold": 0.65,
  "start_date_str": "2024-01-01",  // Optional
  "end_date_str": "2025-01-31"     // Optional
}
```

### Delete Papers Request

```json
{
  "paper_ids": ["2501.12345", "2501.23456", "2501.34567"]
}
```

### Workflow Request

```json
{
  "start_date_str": "2025-01-15",     // Optional, defaults to yesterday
  "end_date_str": "2025-01-21",       // Optional, defaults to today
  "skip_ingestion": false,            // Optional, defaults to false
  "use_classifier": true,             // Optional, defaults to true
  "top_k": 10,                        // Optional, defaults to 10
  "category": "Machine Learning"      // Optional
}
```

---

## Error Handling

### Error Response Format

All errors return a standard JSON format:

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `202 Accepted`: Request accepted for async processing
- `204 No Content`: Request successful with no response body
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Common Error Scenarios

**Invalid Date Format:**

```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD"
}
```

Status Code: `400`

**Paper Not Found:**

```json
{
  "detail": "Paper not found"
}
```

Status Code: `404`

---

## Rate Limiting

Currently, there are no rate limits enforced by the API. However, be mindful of:

- Google Cloud Vertex AI API quotas for embeddings and LLM calls
- ArXiv API rate limits (recommended: max 1 request per 3 seconds)
- Qdrant database performance constraints

## Authentication

The current API does not require authentication. For production deployments, consider:

- Adding API key authentication
- Implementing OAuth2/JWT tokens
- Using reverse proxy with auth (nginx, Caddy, etc.)
- Firewall rules to restrict access

## Versioning

The API is currently unversioned. Future versions may include version prefixes (e.g., `/v1/processor/search-papers`).

## Support

For API issues or questions:

- Check application logs for detailed error messages
- Review the [main README](../README.md) for setup instructions
- See [SETUP.md](./SETUP.md) for external service configuration
