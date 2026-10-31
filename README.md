# 🍳 Gourmet Vault — Full-Stack Recipe Book

A modern, responsive full-stack recipe book application built with **FastAPI**, **Svelte**, and **MongoDB**, packaged with **Docker**, managed with **uv**, and engineered with dev tooling for seamless local development and automated Google Cloud Run deployments.

---

## 🌟 Key Features

- **Full Recipe Management (CRUD)**: Create, browse, update, and delete recipes with rich metadata (ingredients, step-by-step instructions with chef tips, categories, cuisines, dietary tags, cooking times, and multi-image photo galleries).
- **Dynamic Serving Scaler**: Seamlessly adjust serving sizes (+ / -) in real time—ingredient quantities automatically scale to match your required portion size.
- **Full-Text Search & Multi-Criteria Filtering**: Search by title, ingredient, tag, or cuisine; filter by category, difficulty, max cooking time, or your upvoted recipes.
- **User-Specific Thumbs Up / Down Voting & Aggregate Rating**: Users can upvote (👍) or downvote (👎) recipes; recipes track total upvotes, downvotes, and net aggregate rating, and can be sorted by aggregate vote rating.
- **Modern Python with `uv`**: Ultra-fast dependency resolution and virtual environment management via Astral's `uv`.
- **One-Command Local Dev Environment**: `./scripts/dev.sh` boots local MongoDB container, launches FastAPI with hot reload (`:8000`), and runs Vite dev server (`:5173`) with automated process cleanup on exit.
- **Self-Contained Multi-Stage Container**: Root [`Dockerfile`](Dockerfile) packages the pre-built Svelte SPA and FastAPI backend into a single container for local Docker Compose and Google Cloud Run.
- **Automated Google Cloud Run Deployments**: Automated deploy script ([`./scripts/deploy-gcp.sh`](scripts/deploy-gcp.sh)) builds and deploys serverless containers with autoscaling.
- **Google Cloud Free Tier Storage Safeguard**: Automated script ([`./scripts/cleanup-gcp-artifacts.sh`](scripts/cleanup-gcp-artifacts.sh)) enforces GCS bucket lifecycle policies and prunes older container images to stay within free-tier limits.

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
   - **Interactive API Documentation (Swagger)**: [http://localhost:8080/docs](http://localhost:8080/docs) (not served when `ENVIRONMENT=production`; set `API_DOCS_ENABLED=true` to override)
   - **Readiness Health Check**: [http://localhost:8080/health/ready](http://localhost:8080/health/ready) (in production this returns only `{"status": "ready"}`, without version, environment or database details)
   - **Optional Mongo Express GUI**: Run with `docker compose --profile tools up` and open [http://localhost:8081](http://localhost:8081) (basic auth: `MONGO_EXPRESS_USER` / `MONGO_EXPRESS_PASSWORD` from `.env`, default `admin` / `pass`). MongoDB and Mongo Express are bound to `127.0.0.1` only.

---

## 💻 Local Development Setup

### Quick Start (One Command)
Run both backend and frontend development servers with live reload connected to local MongoDB:
```bash
./dev.sh
```
*This automatically checks if MongoDB is running (starting the Docker container if needed), verifies backend Python dependencies (`uv sync`) and frontend npm packages (`npm install`), forces `MONGODB_URI` to use local MongoDB instead of production Atlas, and launches FastAPI (`http://127.0.0.1:8000`) and Vite dev server (`http://localhost:5173`). Press `Ctrl+C` to cleanly terminate all processes and free the ports.*

You can also run automated production Docker container tests locally before deploying:
```bash
./scripts/test-docker.sh
```

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
- **Authorized Chefs / Editors**: Can add new recipes, update existing recipes, upload/reorder gallery images, and delete recipes.
- **Administrators**: Full system permissions, user role management, and database seeding verification in the Admin Panel.

### 1. Google Cloud Console Setup
1. Open the [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials) page for your project.
2. Configure the **OAuth consent screen** (User Type: External, App name: `Gourmet Vault`).
3. Click **Create Credentials** -> **OAuth client ID** -> Application type: **Web application**.
4. Under **Authorized JavaScript origins**, add:
   - `http://localhost:8080` (Docker app)
   - `http://localhost:5173` (Vite dev server)
   - `http://localhost:8000` (FastAPI local server)
   - `https://YOUR_SERVICE_URL.run.app` (Cloud Run deployment)
5. Copy the generated **Client ID** into your `.env` file (`GOOGLE_CLIENT_SECRET` is **not required** for Google Identity Services 1-click authentication):
   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   # GOOGLE_CLIENT_SECRET is optional (not needed for Google login)
   GOOGLE_CLIENT_SECRET=
   ```

### 2. Configure Initial Administrator (Bootstrap Admin) and Session Secret
In `.env`, define the initial privileged administrator email(s) and a session signing secret:
```env
# Comma-separated bootstrap administrator emails (empty = no bootstrap admin)
ALLOWED_EDITOR_EMAILS=chef.owner@example.com
# Optional: add '*' to let every signed-in user edit recipes ('*' never grants admin)
# ALLOWED_EDITOR_EMAILS=chef.owner@example.com,*

# Random secret of at least 32 characters (required in production)
JWT_SECRET=<output of: openssl rand -hex 32>
```
Bootstrap emails are always treated as **Admin** while they are listed in `ALLOWED_EDITOR_EMAILS`; removing an email from the list removes that override. Every other user's permissions come from their stored `role` (`viewer`, `editor`, or `admin`), which admins manage in the Admin Panel.

If `JWT_SECRET` is missing or weak outside production, the server logs a warning and uses a random per-process secret (sessions reset on restart). With `ENVIRONMENT=production` the server refuses to start with a weak secret or a `*` CORS origin, and `DEV_LOGIN_ENABLED=true` is refused in every environment other than `development`/`test`.

### 3. User Roles & Admin Panel
Privileged administrators can access the in-app **🛡️ Admin Panel** to manage team permissions securely:
- **Viewer**: Read-only access to browse, search, and scale recipes.
- **Editor**: Can create, update, and manage recipes.
- **Admin**: Full recipe management plus user role management and team pre-provisioning.
- **Security Hardening**: Google ID tokens are only accepted after full signature, audience, issuer and expiry verification (no fallbacks). Sessions use an `httpOnly`, `SameSite=Lax` cookie (`Secure` outside local development), and the redirect-based OAuth flow is protected with a `state` parameter. Sessions are revocable: **Sign Out** kills the token server-side, **Sign Out Everywhere** invalidates every device, and admins can revoke any user's sessions. Cross-site writes are blocked by an Origin check, every response carries a strict Content-Security-Policy and related headers, and an email already linked to one Google account can't be claimed by another. See [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for details.

---

## 🧪 Testing

The backend tests run against an in-memory MongoDB mock and cover the API, role enforcement, voting, OAuth, and security regressions:
```bash
cd backend
uv run ruff check .
uv run pytest
```
Frontend checks:
```bash
cd frontend
npm run check   # svelte-check (errors only)
npm run build
```
The same checks, plus a production Docker build, run in GitHub Actions on every push and pull request (`.github/workflows/ci.yml`).

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

2. Configure `GCP_PROJECT_ID` in your `.env` (prevents needing to set project in `gcloud` when switching workspaces):
   ```env
   GCP_PROJECT_ID=my-recipes-app
   GCP_REGION=us-central1
   GCP_SERVICE_NAME=recipe-book
   ```

3. Run the automated deployment script:
   ```bash
   ./scripts/deploy-gcp.sh
   # Or with explicit overrides:
   ./scripts/deploy-gcp.sh --project my-recipes-app --region us-central1 --dry-run
   ```

This will automatically:
- Enable Cloud Run, Cloud Build, and Artifact Registry APIs
- Build the container using Cloud Build (no local Docker daemon required)
- Deploy to Cloud Run with auto-scaling (scales to 0 when idle to eliminate idle costs)
- Set up production environment variables (`MONGODB_URI`, `MONGODB_DB_NAME`, `ENVIRONMENT=production`, `LOG_FORMAT=json`). `ENVIRONMENT` is always `production` for deploys, regardless of `.env`; override with `DEPLOY_ENVIRONMENT` if you really need to.
- Refuse to deploy unless `JWT_SECRET` is a random value of at least 32 characters
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
| `POST` | `/api/v1/auth/logout` | Sign out and revoke the current session token |
| `POST` | `/api/v1/auth/logout-all` | Revoke every session for the current user |
| `POST` | `/api/v1/admin/users/{id}/revoke-sessions` | Admin: sign a user out of all sessions |
| `POST` | `/api/v1/recipes/seed` | Seed default curated recipes into database (Admin only, requires verification if DB > 0) |

---

## 📂 Repository Structure

```
recipes/
├── .env.example                       # Environment configuration template
├── .dockerignore                      # Keeps secrets & host node_modules out of image builds
├── .github/workflows/ci.yml           # Lint, tests, frontend check/build, Docker build
├── Dockerfile                         # Unified multi-stage build (Node builder + uv Python runner, non-root)
├── docker-compose.yml                 # Unified app (port 8080) + MongoDB (localhost:27017)
├── docker-compose.override.yml.example # Example for backend hot-reload container mounts
├── dev.sh -> scripts/dev.sh           # Symlink shortcut
├── README.md                          # Documentation
├── backend/
│   ├── pyproject.toml                 # Python package configuration (uv managed, ruff config)
│   ├── uv.lock                        # Exact reproducible dependency lockfile
│   ├── app/
│   │   ├── main.py                    # FastAPI app, SPA static asset serving & CORS
│   │   ├── config.py                  # Pydantic BaseSettings config & production safety checks
│   │   ├── database.py                # Async Motor client, pool & indexes
│   │   ├── seed_data.py               # Curated initial recipes
│   │   ├── dependencies/              # Auth dependencies (current user, editor/admin guards)
│   │   ├── models/                    # Pydantic models (Recipe, Ingredient, User)
│   │   ├── repositories/              # Database queries, filtering, pagination & voting
│   │   ├── services/                  # Auth/permissions, recipe scaling & business logic
│   │   ├── routers/                   # REST API (recipes, auth, admin) & health probes
│   │   └── static/                    # Built Svelte SPA static assets (generated by build)
│   └── tests/                         # Pytest suite on an in-memory MongoDB mock
├── frontend/
│   ├── package.json                   # Svelte & Vite package definitions
│   ├── vite.config.js                 # Vite config (builds to backend/app/static)
│   ├── svelte.config.js               # Svelte preprocessor configuration
│   ├── index.html                     # HTML root
│   └── src/                           # Svelte components & stores
└── scripts/
    ├── dev.sh                         # Unified local dev environment with hot-reload
    ├── build.sh                       # Single-container production build & test runner
    ├── test-docker.sh                 # Local production-container smoke test
    ├── deploy-gcp.sh                  # Automated Google Cloud Run build & deployment
    └── cleanup-gcp-artifacts.sh       # GCP Cloud Storage & Artifact Registry pruner
```
