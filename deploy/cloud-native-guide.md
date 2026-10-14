# Cloud-Native Architecture & Migration Guide

This application is built from the ground up following the **12-Factor App methodology**, making it easily portable between local Docker environments and production cloud-native platforms.

---

## 1. Database Migration: Local MongoDB to Cloud-Native DB

The application uses `motor` with standard MongoDB connection strings. No code changes are required to switch from the local containerized MongoDB to a cloud provider:

### MongoDB Atlas (Recommended for Multi-Cloud)
1. Create a cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. Create a database user and whitelist your server IPs / VPC peering / PrivateLink.
3. Set your environment variable:
   ```bash
   MONGODB_URI="mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
   MONGODB_DB_NAME="recipe_book"
   ```

### AWS DocumentDB
1. Create an Amazon DocumentDB cluster.
2. Download the AWS RDS CA certificate.
3. Configure the connection string with TLS:
   ```bash
   MONGODB_URI="mongodb://<user>:<password>@<cluster-endpoint>:27017/?tls=true&tlsCAFile=/path/to/global-bundle.pem&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false"
   ```

### Azure Cosmos DB (for MongoDB API)
```bash
MONGODB_URI="mongodb://<account-name>:<password>@<account-name>.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000"
```

---

## 2. Serverless Container Deployments

Because the backend and frontend are packaged as lightweight, multi-stage containers with fast startup times, you can deploy them directly to managed serverless container runtimes:

### Google Cloud Run
1. Build and push images to Google Artifact Registry:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/recipe-backend ./backend
   gcloud builds submit --tag gcr.io/$PROJECT_ID/recipe-frontend ./frontend
   ```
2. Deploy backend:
   ```bash
   gcloud run deploy recipe-backend \
     --image gcr.io/$PROJECT_ID/recipe-backend \
     --platform managed \
     --set-env-vars MONGODB_URI="$SECRET_URI",MONGODB_DB_NAME="recipe_book",ENVIRONMENT="production",LOG_FORMAT="json" \
     --allow-unauthenticated
   ```
3. Deploy frontend (or host the built static `dist/` directly on Firebase Hosting / Cloud Storage CDN).

### AWS ECS Fargate or AWS App Runner
- Backend container runs on ECS Fargate behind an Application Load Balancer.
- Frontend static assets can be uploaded to an Amazon S3 bucket fronted by Amazon CloudFront CDN, with `/api/*` routed to the Application Load Balancer.

---

## 3. Kubernetes Deployment (EKS, GKE, AKS)

Pre-configured Kubernetes manifests are provided in `deploy/k8s/`:
- `namespace.yaml`: Isolated namespace `recipe-book`.
- `configmap.yaml`: Production settings (structured JSON logging, DB name).
- `secret.yaml`: Secure database connection string.
- `backend-deployment.yaml`: Deployment with 2 replicas, resource requests/limits, non-root security context (`uid: 1001`), liveness probe (`/health/live`), readiness probe (`/health/ready`), and startup probe (`/health/startup`).
- `frontend-deployment.yaml`: Nginx SPA deployment with healthchecks.
- `ingress.yaml`: Ingress controller routing `/api` and `/health` to backend, and root `/` to frontend with SSL/TLS termination.

Apply the manifests:
```bash
kubectl apply -f deploy/k8s/
```

---

## 4. Customizing Image Storage (S3 / Cloud Storage / Azure Blob)

Currently, recipes support image URLs (e.g. Unsplash, CDN links). To add direct user file uploads in the cloud:
1. Add an abstract storage interface in `backend/app/services/storage.py`:
   ```python
   from abc import ABC, abstractmethod

   class StorageProvider(ABC):
       @abstractmethod
       async def upload_file(self, file_bytes: bytes, filename: str) -> str:
           """Uploads file and returns public CDN URL."""
           pass
   ```
2. Implement providers:
   - `LocalStorageProvider` for development.
   - `S3StorageProvider` (using `aioboto3` or `boto3`).
   - `GCSStorageProvider` (using `google-cloud-storage`).
3. Select provider dynamically via `STORAGE_BACKEND=s3` in `app/config.py`.

---

## 5. Observability & Monitoring

The backend includes built-in cloud observability features:
- **Health Probes**:
  - `GET /health/live`: Fast process liveness check.
  - `GET /health/ready`: Deep health check verifying MongoDB ping and reporting database latency in milliseconds.
- **Structured JSON Logging**:
  - Set `LOG_FORMAT=json` in production to output single-line JSON log events ready for Datadog, AWS CloudWatch Insights, Google Cloud Logging, or Grafana Loki.
- **Latency Headers**:
  - Every API response includes `X-Process-Time` recording processing latency.
