# External Services Setup Guide

This guide provides detailed instructions for setting up the external services required by ArXivPaperHound.

## Table of Contents

- [Qdrant Vector Database](#qdrant-vector-database)
- [Google Cloud / Vertex AI](#google-cloud--vertex-ai)
- [Notion Integration](#notion-integration)
- [S3-Compatible Storage](#s3-compatible-storage)
- [Telegram Bot](#telegram-bot)

## Qdrant Vector Database

Qdrant is used to store paper embeddings for semantic search.

### Installation

#### Using Docker (Recommended)

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/storage/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

#### Using Docker Compose

The project's `docker-compose.yml` already includes Qdrant:

```bash
docker-compose up -d qdrant
```

### Configuration

Set these environment variables in your `.env` file:

```bash
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=your_api_key  # Optional, for authentication
```

### Collections

The application automatically creates two collections:

- `arxiv_papers` - Stores paper embeddings (3072 dimensions) and metadata
- `arxiv_processing_cache` - Caches classification and summarization results

### Accessing Qdrant UI

Once running, access the Qdrant web UI at `http://localhost:6333/dashboard`

## Google Cloud / Vertex AI

Google Cloud's Vertex AI provides the embedding and LLM models for classification and summarization.

### Setup Steps

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Note your Project ID

2. **Enable Vertex AI API**
   - Navigate to APIs & Services > Library
   - Search for "Vertex AI API"
   - Click "Enable"

3. **Create a Service Account**
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Name: `arxiv-paper-hound` (or your preference)
   - Click "Create and Continue"

4. **Assign Roles**
   - Add the following role:
     - `Vertex AI User` - Allows calling Vertex AI models
   - Click "Continue" and then "Done"

5. **Generate Credentials**
   - Click on the newly created service account
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" format
   - Download the file and save it securely (e.g., `credentials/gen_lang_client.json`)

6. **Configure Environment Variable**

   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=credentials/gen_lang_client.json
   ```

### Model Configuration

You can customize which models to use:

```bash
# For classification and summarization
GEMINI_MODEL_NAME=gemini-3-flash-preview

# For embeddings
EMBEDDING_SERVICE_MODEL_NAME=gemini-embedding-001
```

### Thinking Levels

Configure extended thinking for LLM tasks:

```bash
CLASSIFIER_THINKING_LEVEL=LOW      # Options: LOW, MEDIUM, HIGH
SUMMARIZER_THINKING_LEVEL=MEDIUM   # Options: LOW, MEDIUM, HIGH
```

## Notion Integration

Notion is used to store categorized paper summaries and manage research topics.

### Configuration Steps

1. **Create a Notion Integration**
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name: `ArXivPaperHound`
   - Select the workspace where you want to use it
   - Click "Submit"

2. **Copy Integration Token**
   - After creation, copy the "Internal Integration Token"
   - Save it as `NOTION_TOKEN` in your `.env` file:

     ```bash
     NOTION_TOKEN=ntn_your_integration_token_here
     ```

3. **Create Paper Storage Database**
   - Create a new Notion database for storing papers
   - Share the database with your integration:
     - Click "..." in the top-right
     - Select "Add connections"
     - Find and select your integration
   - Copy the database ID from the URL:
     - Format: `https://notion.so/your-workspace/DATABASE_ID?v=...`
   - Set in `.env`:

     ```bash
     NOTION_DATABASE_ID=your_database_id_here
     ```

4. **Create Command/Category Database** (Optional)
   - Create another database for research categories and queries
   - Share with the integration (same process as above)
   - Copy the database ID and set:

     ```bash
     NOTION_COMMAND_DATABASE_ID=your_command_database_id_here
     ```

### Database Schema

#### Paper Storage Database

Recommended properties:

- Title (Title)
- Authors (Rich Text)
- Published (Date)
- ArXiv ID (Rich Text)
- Category (Select or Multi-select)
- Summary (Rich Text or Page content)
- URL (URL)
- PDF URL (URL)

#### Command Database

Recommended properties:

- Category Name (Title)
- Search Query (Rich Text)
- Classification Prompt (Rich Text)
- Active (Checkbox)

## S3-Compatible Storage

S3-compatible storage is used for storing paper images extracted during PDF processing.

### Supported Services

- AWS S3
- MinIO (self-hosted)
- Cloudflare R2
- DigitalOcean Spaces
- Any other S3-compatible service

### Setup with AWS S3

1. **Create an S3 Bucket**
   - Go to AWS S3 Console
   - Click "Create bucket"
   - Name: `arxiv-paper-images` (or your preference)
   - Select region
   - Configure access (public or private based on needs)
   - Click "Create bucket"

2. **Create IAM User**
   - Go to IAM > Users
   - Click "Add users"
   - Name: `arxiv-paper-hound-s3`
   - Select "Programmatic access"
   - Attach policy: `AmazonS3FullAccess` (or create custom policy)

3. **Get Credentials**
   - After user creation, copy:
     - Access Key ID
     - Secret Access Key

4. **Configure Environment**

   ```bash
   AWS_ACCESS_KEY_ID=your_access_key_id
   AWS_SECRET_ACCESS_KEY=your_secret_access_key
   S3_BUCKET=arxiv-paper-images
   # For AWS S3, ENDPOINT_URL is optional
   # ENDPOINT_URL=https://s3.amazonaws.com
   ```

### Setup with MinIO (Self-Hosted)

1. **Install MinIO**

   ```bash
   docker run -p 9000:9000 -p 9001:9001 \
     -e "MINIO_ROOT_USER=minioadmin" \
     -e "MINIO_ROOT_PASSWORD=minioadmin" \
     -v $(pwd)/storage/minio:/data \
     minio/minio server /data --console-address ":9001"
   ```

2. **Access MinIO Console**
   - Open `http://localhost:9001`
   - Login with credentials (minioadmin/minioadmin)

3. **Create Bucket**
   - Click "Buckets" > "Create Bucket"
   - Name: `arxiv-paper-images`
   - Click "Create"

4. **Create Access Keys**
   - Click "Access Keys"
   - Click "Create Access Key"
   - Copy the Access Key and Secret Key

5. **Configure Environment**

   ```bash
   AWS_ACCESS_KEY_ID=your_minio_access_key
   AWS_SECRET_ACCESS_KEY=your_minio_secret_key
   ENDPOINT_URL=http://localhost:9000
   S3_BUCKET=arxiv-paper-images
   ```

### Setup with Cloudflare R2

1. **Create R2 Bucket**
   - Go to Cloudflare Dashboard > R2
   - Click "Create bucket"
   - Name: `arxiv-paper-images`

2. **Generate API Token**
   - Click "Manage R2 API Tokens"
   - Click "Create API token"
   - Set permissions: "Object Read & Write"
   - Copy Access Key ID and Secret Access Key

3. **Configure Environment**

   ```bash
   AWS_ACCESS_KEY_ID=your_r2_access_key_id
   AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key
   ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
   S3_BUCKET=arxiv-paper-images
   ```

## Telegram Bot

The Telegram bot provides an interactive interface for searching and managing papers.

### Bot Creation

1. **Create a Bot with BotFather**
   - Open Telegram and message [@BotFather](https://t.me/botfather)
   - Send `/newbot`
   - Follow the prompts:
     - Choose a display name (e.g., "ArXiv Paper Hound")
     - Choose a username (must end in `bot`, e.g., `arxiv_paper_hound_bot`)
   - Copy the API token provided

2. **Configure Bot Token**

   ```bash
   TELEGRAM_TOKEN=your_bot_token_here
   ```

3. **Get Your Chat ID**

   Option 1: Using a bot
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram
   - Copy your ID

   Option 2: Using the Telegram API
   - Message your new bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the JSON response under `message.chat.id`

4. **Configure Chat ID**

   ```bash
   TELEGRAM_CHAT_ID=your_chat_id
   ```

### Optional: Bot Customization

Set bot commands for better UX (via BotFather):

```text
start - Welcome message and quick start guide
help - Command reference
search - Semantic search for papers
paper - Get paper details
similar - Find similar papers
topics - List available research categories
summarize - Generate paper summary
subscribe - Subscribe to research topics
unsubscribe - Manage subscriptions
subscriptions - List active subscriptions
insert - Fetch papers for date range
stats - View database statistics
```

Send to BotFather:

```text
/setcommands
[Select your bot]
[Paste the commands above]
```

### Group Chat Setup (Optional)

To use the bot in group chats:

1. **Disable Privacy Mode** (to let bot read all messages)
   - Message @BotFather
   - Send `/setprivacy`
   - Select your bot
   - Choose "Disable"

2. **Add Bot to Group**
   - Add the bot to your group chat
   - Make it an admin if needed for group subscriptions

3. **Get Group Chat ID**
   - Message in the group
   - Visit the getUpdates endpoint
   - Copy the group chat ID (will be negative number)

## Timezone Configuration

Configure the timezone for scheduled jobs:

```bash
SCHEDULER_TIMEZONE=Europe/Moscow  # Default
# Other examples:
# SCHEDULER_TIMEZONE=America/New_York
# SCHEDULER_TIMEZONE=Asia/Tokyo
# SCHEDULER_TIMEZONE=UTC
```

The daily workflow runs at 06:00 in the configured timezone.

## Verification

After configuring all services, verify your setup:

1. Start the application
2. Check the health endpoint:

   ```bash
   curl http://localhost:8001/health/status
   ```

3. Test the Telegram bot by sending `/start`
4. Try inserting and searching papers

If you encounter issues, check the application logs for detailed error messages.
