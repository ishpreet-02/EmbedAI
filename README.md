# EmbedAI

A SaaS dashboard where a business pastes a website URL, gets that site scraped and embedded into a knowledge base, and receives an embeddable AI chatbot that answers from the site's content.

## Why This Project

Businesses often want AI-powered chat support without manually writing FAQs or uploading documentation. EmbedAI removes that step: it crawls a business's own public website, builds a searchable knowledge base from the actual page content, and generates an embeddable chatbot grounded strictly in that content — no manual data entry, no hallucinated answers outside the site's scope.

## Features

- Email/password signup and login with JWT authentication.
- Protected dashboard for creating, listing, opening, and deleting chatbots.
- Website ingestion from a submitted URL:
  - uses Playwright/Chromium to load pages,
  - discovers internal links under the same starting path,
  - extracts readable text with BeautifulSoup,
  - crawls up to 20 pages per chatbot.
- RAG knowledge base creation:
  - chunks scraped text with `RecursiveCharacterTextSplitter`,
  - embeds chunks locally with `sentence-transformers/all-MiniLM-L6-v2`,
  - stores vectors and source metadata in an isolated Qdrant collection per chatbot.
- Optional website summary point generated with Groq and stored in Qdrant for broad "what is this site?" questions.
- Public streaming chat endpoint for embedded widgets.
- Retrieval grounded in Qdrant search results, with Groq generating responses from retrieved context.
- Conversation and message persistence in Supabase.
- Dashboard conversation browser for reading visitor conversations.
- One-line JavaScript embed served from the backend at `/widget.js`.
- Widget settings exposed in the dashboard:
  - brand color,
  - header text,
  - welcome message,
  - left/right bubble position.
- Per-chatbot allowed-origin settings for widget chat/history requests.
- Resync action that re-scrapes the website and rebuilds the Qdrant collection.
- Redis + Celery background worker for durable website ingestion jobs.
- Health endpoints at `/` and `/health`.

## Planned Or Incomplete

- File upload ingestion is not implemented in the current routers, services, schemas, or dashboard pages.

## Tech Stack

### Frontend

- React 18
- TypeScript
- Vite
- React Router
- TanStack React Query
- Axios
- Tailwind CSS/PostCSS/Autoprefixer
- Lucide React icons

### Backend

- FastAPI
- Uvicorn
- Pydantic
- Supabase Python client
- Passlib/bcrypt
- python-jose
- python-dotenv
- httpx
- slowapi rate limiting
- Celery for background jobs
- Redis as the Celery broker/result backend

### AI/RAG Pipeline

- Playwright Chromium for rendered-page scraping
- BeautifulSoup and lxml for text extraction
- LangChain text splitters
- sentence-transformers with `all-MiniLM-L6-v2` local embeddings
- PyTorch CPU runtime via sentence-transformers
- Qdrant client for vector storage and search
- Groq SDK using `llama-3.3-70b-versatile`
- Tenacity retries around Groq/Qdrant operations

### Infrastructure

- Docker Compose for the backend service
- Backend Docker image based on `python:3.11-slim`
- Nginx reverse proxy config for an EC2 host
- Redis service for queued ingestion jobs
- Supabase for relational data
- Qdrant Cloud or local Qdrant, depending on `QDRANT_API_KEY`
- Vercel frontend deployment config

## Project Structure

```
backend/
├── routers/          # auth, chatbots, chat — API route handlers
├── services/         # scraper, rag, embedder, qdrant_service, database
├── models/           # Pydantic request/response schemas
├── tasks/            # Celery ingestion task and ingestion pipeline
├── middleware/        # JWT auth dependency
├── widget/            # embeddable widget.js served to customer sites
└── main.py            # FastAPI app entrypoint, CORS, health checks

frontend/
├── src/
│   ├── pages/          # Dashboard, ChatbotDetail, Conversations, Login, Signup
│   ├── components/     # Sidebar, ChatbotCard, EmbedCodeBox, TestChatPanel
│   ├── api/             # axios client, typed API wrappers
│   └── hooks/           # useAuth
└── vercel.json          # SPA rewrite + env config for Vercel deploy
```

## Architecture Overview

### System diagram

```
                    ┌──────────────────┐
                    │  React Dashboard │
                    │   (Vercel)       │
                    └────────┬─────────┘
                             │ REST (JWT)
                             ▼
                    ┌──────────────────┐
                    │  FastAPI Backend │
                    │      (EC2)       │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   INGESTION FLOW      CHAT FLOW           SHARED DATA
   (POST /chatbots)    (POST /chat/{id})
          │                  │
          ▼                  ▼
   ┌─────────────┐
   │ Redis Queue │
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │Celery Worker│
   └──────┬──────┘
          ▼
   ┌─────────────┐    ┌──────────────┐
   │ Playwright  │    │ sentence-    │
   │ + Chromium  │    │ transformers │
   └──────┬──────┘    │ (embed query)│
          ▼            └──────┬───────┘
   ┌─────────────┐            ▼
   │BeautifulSoup│    ┌──────────────┐
   │(text clean) │    │   Qdrant     │
   └──────┬──────┘    │ (similarity  │
          ▼            │   search)   │
   ┌─────────────┐    └──────┬───────┘
   │ sentence-   │            ▼
   │transformers │    ┌──────────────┐
   │  (embed)    │    │     Groq     │
   └──────┬──────┘    │ (llama-3.3,  │
          ▼            │  streaming)  │
   ┌─────────────┐    └──────┬───────┘
   │   Qdrant    │            │
   │ (store      │            │
   │  vectors)   │            │
   └──────┬──────┘            │
          ▼                    ▼
   ┌──────────────────────────────────┐
   │            Supabase              │
   │  users · chatbots · conversations │
   │           · messages              │
   └───────────────────────────────────┘
```

Ingestion and chat share the same Qdrant collections and Supabase tables, but run as two independent flows. Ingestion is queued through Redis and executed by a Celery worker, while chat happens per visitor message on the public streaming endpoint.

### Chatbot creation and ingestion

1. The dashboard calls `POST /api/chatbots` with a chatbot name and website URL.
2. The backend inserts a `chatbots` row in Supabase with `pending` status and a generated Qdrant collection name.
3. The backend queues `run_ingestion_task` in Celery through Redis.
4. A Celery worker runs `run_ingestion()`, marks the chatbot `processing`, then `scrape_website()` opens the site with Playwright, follows same-domain internal links, and extracts cleaned text.
5. `ingest_pages()` splits page text into 500-character chunks with 50-character overlap, embeds the chunks locally, creates a fresh Qdrant collection, and upserts vectors with URL/title/text payloads.
6. `generate_and_store_summary()` attempts to summarize selected key pages with Groq, embeds that summary, and stores it as a special Qdrant point. If summary generation fails, ingestion can still complete.
7. Supabase is updated to `ready` with `pages_indexed` and `chunks_stored`, or `failed` if scraping/embedding produced no usable data or raised an error.

### Chat query flow

1. The widget or test panel posts a message to `POST /api/chat/{chatbot_id}`.
2. The backend verifies the chatbot exists, checks the request origin against `allowed_origins`, requires `status == "ready"`, and verifies the Qdrant collection exists.
3. The user message is saved in Supabase under a visitor conversation.
4. `query_rag()` embeds the question, searches Qdrant, and filters low-scoring results. General site-overview questions also try to include the stored website summary.
5. Retrieved chunks are passed to Groq with a system prompt that instructs the model to answer only from provided context.
6. The response streams back as `text/plain`. After streaming completes, the full assistant message is saved in Supabase.
7. Repeated identical questions for the same collection can be served from an in-memory response cache.

## API Reference

### Create a chatbot

```http
POST /api/chatbots
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "name": "Acme Support",
  "website_url": "https://acme.com"
}
```

Response:

```json
{
  "id": "b3e1...",
  "status": "pending",
  "qdrant_collection": "chatbot_a1b2c3d4e5f6",
  "pages_indexed": 0,
  "chunks_stored": 0
}
```

### Check ingestion status

```http
GET /api/chatbots/{id}/status
Authorization: Bearer <jwt>
```

### Send a chat message (public, called by the widget)

```http
POST /api/chat/{chatbot_id}
Content-Type: application/json

{
  "message": "What services do you offer?",
  "visitor_id": "visitor_a1b2c3d4",
  "conversation_id": null
}
```

Response is a streamed `text/plain` body. `X-Conversation-Id` is returned as a response header on the first message and should be sent back as `conversation_id` on subsequent messages in the same session to keep the conversation grouped.

## Setup / Running Locally

### Backend

Start Redis first:

```powershell
docker run -d --name embedai-redis -p 6379:6379 redis:7-alpine
```

Then install and run the API:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal, run the Celery worker:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
celery -A celery_app:celery_app worker --loglevel=info --pool=solo
```

`--pool=solo` is recommended on Windows local development. On Linux/EC2, use the Docker Compose worker command.

On Linux, Playwright may also need:

```bash
python -m playwright install-deps chromium
```

Backend environment variables read by the code:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `JWT_EXPIRATION_MINUTES`
- `GROQ_API_KEY`
- `QDRANT_HOST`
- `QDRANT_PORT`
- `QDRANT_API_KEY`
- `REDIS_URL`
- `FRONTEND_URL`
- `CORS_ORIGINS`
- `DEBUG`

For the current implemented code paths, Supabase, Groq, Qdrant, and Redis settings must be valid before creating and chatting with a bot.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend environment variable:

- `VITE_API_URL`

If `VITE_API_URL` is not set, the frontend calls `http://localhost:8000`.

## Deployment

The checked-in deployment files target this split:

- Backend and Celery worker run on EC2 with Docker Compose using `backend/Dockerfile`.
- Redis runs as an internal Docker Compose service for Celery.
- Nginx proxies public traffic to the backend container on port `8000` and disables proxy buffering for streaming chat responses.
- Supabase is external and stores users, chatbots, conversations, and messages.
- Qdrant is external when `QDRANT_API_KEY` is set, matching the Qdrant Cloud comments in `docker-compose.yml` and `.env.production.template`.
- Frontend is deployed separately on Vercel. `frontend/vercel.json` sets `VITE_API_URL` and rewrites SPA routes to `index.html`.

`docker-compose.yml` defines the backend API, Celery worker, and Redis. It does not start local Supabase, Qdrant, or the frontend.

## Known Limitations

- Scraping is capped at 20 pages per chatbot.
- The crawler only follows internal links on the same domain and under the starting URL path.
- Sites that block headless browsers, require authentication, hide content behind forms, or need long-running client-side interactions can fail ingestion.
- JavaScript-rendered pages are supported through Playwright, but the scraper waits with fixed timeouts and does not perform custom app interactions.
- The backend Docker command runs a single Uvicorn worker to fit small EC2 instances.
- Chat response caching is in memory, so it is per-process and lost on restart.
- The landing page copy includes broad claims such as "works on any site"; the implemented scraper is best read as "works on publicly accessible pages that Playwright can render within the scraper limits."
