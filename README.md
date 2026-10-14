# 🍳 Gourmet Vault — Full-Stack Recipe Book

A modern, responsive full-stack recipe book application built with **FastAPI**, **Svelte**, and **MongoDB**, packaged with **Docker**, managed with **uv**, and engineered with dev tooling for seamless local development and automated Google Cloud Run deployments.

---

## 🌟 Key Features

- **Full Recipe Management (CRUD)**: Create, browse, update, and delete recipes with rich metadata (ingredients, step-by-step instructions with chef tips, categories, cuisines, dietary tags, cooking times, and multi-image photo galleries).
- **Dynamic Serving Scaler**: Seamlessly adjust serving sizes (+ / -) in real time—ingredient quantities automatically scale to match your required portion size.
- **Interactive Cooking Checklist**: Check off ingredients as you prepare your mise-en-place and mark off cooking steps as you progress.
- **Full-Text Search & Multi-Criteria Filtering**: Search by title, ingredient, tag, or cuisine; filter by category, difficulty, max cooking time, or favorites.
- **Auto-Seeding**: Comes pre-loaded with curated, delicious recipes from around the world (Artisan Margherita Pizza, Creamy Tuscan Garlic Chicken, Beef Barbacoa Tacos, Thai Coconut Red Curry, Mediterranean Quinoa Salad, Warm Molten Chocolate Lava Cakes).
- **Modern Python with `uv`**: Ultra-fast dependency resolution and virtual environment management via Astral's `uv`.
- **One-Command Local Dev Environment**: `./scripts/dev.sh` boots local MongoDB container, launches FastAPI with hot reload (`:8000`), and runs Vite dev server (`:5173`) with automated process cleanup on exit.
- **Self-Contained Multi-Stage Container**: Root [`Dockerfile`](file:///home/mfort/projects/recipes/Dockerfile) packages the pre-built Svelte SPA and FastAPI backend into a single container for local Docker Compose and Google Cloud Run.
- **Automated Google Cloud Run Deployments**: Automated deploy script ([`./scripts/deploy-gcp.sh`](file:///home/mfort/projects/recipes/scripts/deploy-gcp.sh)) builds and deploys serverless containers with autoscaling.
- **Google Cloud Free Tier Storage Safeguard**: Automated script ([`./scripts/cleanup-gcp-artifacts.sh`](file:///home/mfort/projects/recipes/scripts/cleanup-gcp-artifacts.sh)) enforces GCS bucket lifecycle policies and prunes older container images to stay within free-tier limits.

---

## 🏗️ Architecture & Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser Client                      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                       Port 8080 (Docker) / Cloud Run HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             Unified Container (FastAPI + SPA Static)        │
│   - Python 3.11 + uv, Uvicorn ASGI Runner                   │
│   - Embedded Svelte 4 SPA Static Assets & Route Fallback    │
│   - Health Probes (/health/live, /health/ready, /health/up) │
│   - Pydantic v2 validation, Async Motor driver              │
└──────────────────────────────┬──────────────────────────────┘
                               │ mongodb://... (Port 27017 or Atlas)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Database: MongoDB 7.0                     │
│   - Text search indexes, Query indexing, Volume persistence │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Technology | Key Components |
| :--- | :--- | :--- |
| **Backend** | Python 3.11, FastAPI, Motor | Managed with `uv`, Pydantic v2, async MongoDB driver |
| **Frontend** | Svelte 4, Vite | Custom responsive culinary UI, reactive stores, SPA build |
| **Database** | MongoDB 7.0 / Atlas | Document store with text search & multi-key indexing |
| **Containerization** | Docker, Docker Compose | Unified multi-stage container, healthchecks |
| **Cloud Platform** | Google Cloud Run & Cloud Build | Serverless auto-scaling containers (0 to 10 instances) |

---

## 🚀 Quick Start with Docker (Recommended)

To run the complete application with Docker Compose:

1. **Clone and navigate to the directory**:
   ```bash
   cd /home/mfort/projects/recipes
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

3. **Start the containers**:
   ```bash
   docker compose up --build
   ```

4. **Access the Application**:
   - **Recipe Book Web App**: [http://localhost:8080](http://localhost:8080)
   - **Interactive API Documentation (Swagger)**: [http://localhost:8080/docs](http://localhost:8080/docs)
   - **Readiness Health Check**: [http://localhost:8080/health/ready](http://localhost:8080/health/ready)
   - **Optional Mongo Express GUI**: Run with `docker compose --profile tools up` and open [http://localhost:8081](http://localhost:8081).

---

## 💻 Local Development Setup

### Quick Start (One Command)
Run both backend and frontend development servers with live reload connected to local MongoDB:
```bash
./scripts/dev.sh
```
*This automatically starts the local MongoDB container (port 27017), forces `MONGODB_URI` to use the local MongoDB container instead of production Atlas, and launches FastAPI (`http://127.0.0.1:8000`) and the Vite dev server (`http://localhost:5173`). Press `Ctrl+C` to cleanly terminate both processes and release ports.*

---

### Manual Setup (Step-by-Step)

#### Prerequisites
- Node.js 20+ & npm
- Python 3.11+
- Astral `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Local MongoDB running on `localhost:27017` (e.g. `docker compose up -d mongodb`)

#### 1. Backend Setup
```bash
cd backend

# Install dependencies with uv
uv sync --extra dev

# Run unit and integration tests
uv run pytest tests/

# Start FastAPI development server with hot-reload
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### 2. Frontend Setup
```bash
cd frontend

# Install npm packages
npm install

# Start Vite development server (proxies /api and /health to localhost:8000)
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

#### 3. Build Static Frontend for FastAPI Serving
```bash
cd frontend
npm run build
```
This compiles the static assets into `backend/app/static`, allowing FastAPI at `http://localhost:8000` to serve the entire application autonomously without Vite!

Or run the all-in-one build and verification script:
```bash
./scripts/build.sh
```

---

## 🔑 Google OAuth & Role-Based Access Control Setup

Gourmet Vault employs role-based access control (RBAC):
- **Public & Foodie Viewers**: Can browse, filter, search, view recipes, scale serving portions, and utilize the interactive mise-en-place checklist.
- **Authorized Chefs / Editors**: Can add new recipes, update existing recipes, upload/reorder gallery images, delete recipes, and seed curated datasets.

### 1. Google Cloud Console Setup
1. Open the [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials) page for your project.
2. Configure the **OAuth consent screen** (User Type: External, App name: `Gourmet Vault`).
3. Click **Create Credentials** -> **OAuth client ID** -> Application type: **Web application**.
4. Under **Authorized JavaScript origins**, add:
   - `http://localhost:8080` (Docker app)
   - `http://localhost:5173` (Vite dev server)
   - `http://localhost:8000` (FastAPI local server)
   - `https://YOUR_SERVICE_URL.run.app` (Cloud Run deployment)
5. Under **Authorized redirect URIs**, add:
   - `http://localhost:8080/api/v1/auth/google/callback`
   - `http://localhost:5173/api/v1/auth/google/callback`
   - `http://localhost:8000/api/v1/auth/google/callback`
   - `https://YOUR_SERVICE_URL.run.app/api/v1/auth/google/callback`
6. Copy the generated **Client ID** and **Client Secret** into your `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-your-secret
   ```

### 2. Configure Authorized Recipe Editors
In `.env`, define who has permission to modify recipes:
```env
# Specific chef email accounts allowed to add/edit/delete recipes:
ALLOWED_EDITOR_EMAILS=mef231@gmail.com,chef@gourmetvault.com

# Or allow any authenticated Google user:
# ALLOWED_EDITOR_EMAILS=*
```

### 3. Local Dev & Demo Testing Mode
When developing locally (`./scripts/dev.sh`), click **Sign In** to access:
- **👨‍🍳 Head Chef (Editor)**: Instant 1-click test login with full edit/delete privileges.
- **👤 Foodie Guest (Viewer)**: Instant 1-click test login in read-only mode to verify restrictions.

---

## 🧪 Testing

The backend includes comprehensive async test coverage testing all endpoints, role enforcement, health checks, CRUD operations, ingredient scaling, and static SPA serving:
```bash
cd backend
uv run pytest tests/
```
Output:
```
tests/test_auth_and_permissions.py ......                                                                    [ 40%]
tests/test_recipes_api.py .........                                                                         [100%]
=============================================== 15 passed in 0.18s ===============================================
```

---

## ☁️ Google Cloud Deployment (Cloud Run)

The application is packaged as a single self-contained multi-stage Docker container (Svelte static build + FastAPI + Uvicorn) designed for **Google Cloud Run**.

### Prerequisites
1. **Google Cloud Project**:
   - An active GCP project with billing enabled.
2. **MongoDB Atlas**:
   - Create a cluster on [MongoDB Atlas](https://cloud.mongodb.com/).
   - Under **Security** > **Network Access** > **IP Access List**:
     - Click **Add IP Address** -> Select **Allow Access From Anywhere** (`0.0.0.0/0`) so Google Cloud Run's dynamic IP addresses can connect.
   - Configure your database connection string in `.env`:
     ```env
     MONGODB_URI="mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
     MONGODB_DB_NAME="recipe_book"
     ```

---

### Automated Deployment Script (`gcloud` CLI)

1. If you haven't installed the `gcloud` CLI yet:
   ```bash
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

2. Set your active project:
   ```bash
   gcloud config set project YOUR_GCP_PROJECT_ID
   ```

3. Run the automated deployment script:
   ```bash
   ./scripts/deploy-gcp.sh
   ```

This will automatically:
- Enable Cloud Run, Cloud Build, and Artifact Registry APIs
- Build the container using Cloud Build (no local Docker daemon required)
- Deploy to Cloud Run with auto-scaling (scales to 0 when idle to eliminate idle costs)
- Set up production environment variables (`MONGODB_URI`, `MONGODB_DB_NAME`, `ENVIRONMENT=production`, `LOG_FORMAT=json`)
- Retrieve and configure your live HTTPS URL (e.g. `https://recipe-book-xyz-uc.a.run.app`)
- Automatically execute `./scripts/cleanup-gcp-artifacts.sh --prune-now` to purge older build artifacts and protect your Google Cloud Free Tier quotas

---

### Managing GCP Free Tier Storage & Build Artifacts

To prevent Google Cloud Build and Artifact Registry from exceeding free-tier allowances (0.5 GB Artifact Registry and 5.0 GB Cloud Storage):

```bash
# Check current storage usage and configure automated lifecycle policies
./scripts/cleanup-gcp-artifacts.sh

# Immediately prune older image digests beyond the active version
./scripts/cleanup-gcp-artifacts.sh --prune-now
```

---

### Custom Domain Mapping
To point your own domain name (e.g. `recipes.yourdomain.com`):
1. In `.env`, optionally set `CUSTOM_DOMAIN=recipes.yourdomain.com` before running `./scripts/deploy-gcp.sh` (or set `FRONTEND_URL=https://recipes.yourdomain.com`).
2. In Google Cloud Console, visit [Cloud Run Domain Mappings](https://console.cloud.google.com/run/domains) and follow the DNS verification steps.

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health/live` | Liveness probe (200 OK if server running) |
| `GET` | `/health/ready` | Readiness probe (verifies MongoDB ping & latency) |
| `GET` | `/health/startup`| Startup probe verifying initialization |
| `GET` | `/api/v1/recipes` | List recipes with search, filtering, and pagination |
| `POST` | `/api/v1/recipes` | Create a new recipe |
| `GET` | `/api/v1/recipes/{id}` | Get recipe by ID |
| `PUT` | `/api/v1/recipes/{id}` | Update existing recipe |
| `DELETE` | `/api/v1/recipes/{id}` | Delete recipe |
| `GET` | `/api/v1/recipes/{id}/scale` | Dynamically scale recipe ingredients for $N$ servings |
| `GET` | `/api/v1/recipes/meta/tags` | List all unique tags across recipes |
| `GET` | `/api/v1/recipes/meta/cuisines`| List all unique cuisines |
| `GET` | `/api/v1/recipes/meta/categories`| List all meal categories |
| `POST` | `/api/v1/recipes/seed` | Seed default curated recipes into database |

---

## 📂 Repository Structure

```
recipes/
├── .env.example                       # Environment configuration template
├── .gitignore                         # Git ignore patterns for Python, Node, Vite & secrets
├── Dockerfile                         # Unified multi-stage build (Node builder + uv Python runner)
├── docker-compose.yml                 # Unified app (port 8080) + MongoDB (port 27017)
├── docker-compose.override.yml.example # Example for hot-reload container mounts
├── README.md                          # Documentation
├── scripts/
│   ├── dev.sh                         # One-command local development environment
│   ├── build.sh                       # Frontend build + backend pytest test runner
│   ├── deploy-gcp.sh                  # Automated Google Cloud Run build & deploy
│   └── cleanup-gcp-artifacts.sh       # Cloud Storage lifecycle & Artifact Registry cleaner
├── backend/
│   ├── pyproject.toml                 # Python package configuration (uv managed)
│   ├── uv.lock                        # Exact reproducible dependency lockfile
│   ├── Dockerfile                     # Standalone backend container
│   ├── .dockerignore
│   ├── app/
│   │   ├── main.py                    # FastAPI app, SPA static asset serving & CORS
│   │   ├── config.py                  # Pydantic BaseSettings 12-factor config
│   │   ├── database.py                # Async Motor client, pool & text indexes
│   │   ├── seed_data.py               # Curated initial recipes
│   │   ├── models/                    # Pydantic models (Recipe, Ingredient, Scale)
│   │   ├── repositories/              # Database queries, filtering & pagination
│   │   ├── services/                  # Recipe scaling & business logic
│   │   ├── routers/                   # REST API & health probes
│   │   └── static/                    # Built Svelte SPA static assets (generated by build)
│   └── tests/
│       ├── conftest.py                # In-memory mock MongoDB test fixtures
│       └── test_recipes_api.py        # Pytest API test suite & SPA fallback tests
├── frontend/
│   ├── package.json                   # Svelte & Vite package definitions
│   ├── vite.config.js                 # Vite config (builds to backend/app/static)
│   ├── svelte.config.js               # Svelte preprocessor configuration
│   ├── nginx.conf                     # Optional standalone Nginx reverse-proxy & SPA config
│   ├── Dockerfile                     # Optional standalone frontend container
│   ├── .dockerignore
│   ├── index.html                     # HTML root
│   └── src/                           # Svelte components & stores
└── scripts/
    ├── dev.sh                         # Unified local dev environment with hot-reload
    ├── build.sh                       # Single-container production build & test runner
    ├── deploy-gcp.sh                  # Automated Google Cloud Run build & deployment
    └── cleanup-gcp-artifacts.sh       # GCP Cloud Storage & Artifact Registry pruner
```
