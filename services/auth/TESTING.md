# Auth Service - Testing & Deployment Guide

This document provides comprehensive procedures for testing and deploying the Auth & User Management Service locally using Poetry, Docker, Docker Compose, and K3s.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Testing with Poetry (Local Development)](#testing-with-poetry)
3. [Testing with Docker](#testing-with-docker)
4. [Testing with Docker Compose](#testing-with-docker-compose)
5. [Testing with K3s (Kubernetes)](#testing-with-k3s)
6. [Running Migrations](#running-migrations)
7. [API Testing](#api-testing)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

```bash
# Python 3.11+
python --version  # Should be 3.11 or higher

# Poetry
curl -sSL https://install.python-poetry.org | python3 -
poetry --version

# Docker & Docker Compose
docker --version
docker-compose --version

# K3s (for Kubernetes testing)
curl -sfL https://get.k3s.io | sh -
k3s --version

# kubectl (comes with K3s, or install separately)
kubectl version --client
```

### Environment Variables

Create a `.env` file in the `services/auth` directory:

```bash
# services/auth/.env
AUTH_ENV=local
AUTH_DEBUG=true
AUTH_SECRET_KEY=your-super-secret-key-change-in-production
AUTH_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/auth_db
AUTH_REDIS_URL=redis://localhost:6379/0
AUTH_BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:8080
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=15
AUTH_REFRESH_TOKEN_EXPIRE_DAYS=30
```

---

## Testing with Poetry

### 1. Setup Environment

```bash
# Navigate to auth service directory
cd services/auth

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 2. Start PostgreSQL (Required)

```bash
# Option 1: Using Docker
docker run -d \
  --name auth-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=auth_db \
  -p 5432:5432 \
  postgres:16-alpine

# Option 2: Use existing PostgreSQL installation
# Update AUTH_DATABASE_URL in .env accordingly
```

### 3. Run Migrations

```bash
# Run Alembic migrations
poetry run alembic upgrade head

# Check migration status
poetry run alembic current

# View migration history
poetry run alembic history
```

### 4. Start Development Server

```bash
# Start with hot reload
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the shorthand
poetry run python -m uvicorn app.main:app --reload
```

### 5. Run Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/test_auth.py -v

# Run with verbose output
poetry run pytest -v --tb=short
```

### 6. Code Quality Checks

```bash
# Format code with Black
poetry run black app/

# Sort imports with isort
poetry run isort app/

# Lint with Ruff
poetry run ruff check app/

# Type checking with mypy
poetry run mypy app/

# Run all checks
poetry run black app/ && poetry run isort app/ && poetry run ruff check app/
```

### 7. Verify Service

```bash
# Health check
curl http://localhost:8000/api/v1/auth/health

# Readiness check
curl http://localhost:8000/api/v1/auth/ready

# API docs (if DEBUG=true)
# Open: http://localhost:8000/api/v1/docs
```

---

## Testing with Docker

### 1. Build Docker Image

```bash
cd services/auth

# Build production image
docker build -t fec-auth-service:latest .

# Build development image
docker build -t fec-auth-service:dev --target development .

# Build with specific tag
docker build -t fec-auth-service:v0.1.0 .
```

### 2. Run Container

```bash
# Start PostgreSQL first
docker run -d \
  --name auth-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=auth_db \
  -p 5432:5432 \
  postgres:16-alpine

# Wait for PostgreSQL to be ready
sleep 5

# Run auth service
docker run -d \
  --name auth-service \
  -p 8000:8000 \
  -e AUTH_ENV=local \
  -e AUTH_DEBUG=true \
  -e AUTH_SECRET_KEY=dev-secret-key \
  -e AUTH_DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/auth_db \
  --add-host=host.docker.internal:host-gateway \
  fec-auth-service:latest
```

### 3. Run Migrations in Container

```bash
# Execute migrations
docker exec -it auth-service alembic upgrade head

# Check migration status
docker exec -it auth-service alembic current
```

### 4. View Logs

```bash
# Follow logs
docker logs -f auth-service

# View last 100 lines
docker logs --tail 100 auth-service
```

### 5. Cleanup

```bash
# Stop containers
docker stop auth-service auth-postgres

# Remove containers
docker rm auth-service auth-postgres

# Remove image
docker rmi fec-auth-service:latest
```

---

## Testing with Docker Compose

### 1. Start All Services

```bash
cd services/auth

# Start in detached mode
docker-compose up -d

# Start with build
docker-compose up -d --build

# Start with tools (Adminer)
docker-compose --profile tools up -d
```

### 2. Run Migrations

```bash
# Execute migrations
docker-compose exec auth alembic upgrade head

# Check status
docker-compose exec auth alembic current
```

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f auth

# Last 50 lines
docker-compose logs --tail 50 auth
```

### 4. Access Services

```bash
# Auth Service API
curl http://localhost:8000/api/v1/auth/health

# API Documentation
# Open: http://localhost:8000/api/v1/docs

# Adminer (Database UI) - if started with --profile tools
# Open: http://localhost:8080
# Server: postgres, Username: postgres, Password: postgres, Database: auth_db
```

### 5. Run Tests in Container

```bash
# Run tests
docker-compose exec auth pytest

# Run with coverage
docker-compose exec auth pytest --cov=app

# Interactive shell
docker-compose exec auth bash
```

### 6. Cleanup

```bash
# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Remove everything including images
docker-compose down -v --rmi all
```

---

## Testing with K3s

### 1. Create Kubernetes Manifests

Create the following files in `services/auth/k8s/`:

#### namespace.yaml
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fec-auth
```

#### configmap.yaml
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: auth-config
  namespace: fec-auth
data:
  AUTH_ENV: "production"
  AUTH_DEBUG: "false"
  AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: "15"
  AUTH_REFRESH_TOKEN_EXPIRE_DAYS: "30"
```

#### secret.yaml
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: auth-secrets
  namespace: fec-auth
type: Opaque
stringData:
  AUTH_SECRET_KEY: "your-production-secret-key"
  AUTH_DATABASE_URL: "postgresql://postgres:postgres@postgres-service:5432/auth_db"
  AUTH_REDIS_URL: "redis://redis-service:6379/0"
```

#### postgres.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: fec-auth
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          value: postgres
        - name: POSTGRES_DB
          value: auth_db
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: fec-auth
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: fec-auth
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

#### deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: fec-auth
spec:
  replicas: 2
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: fec-auth-service:latest
        imagePullPolicy: Never  # Use local image for k3s
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: auth-config
        - secretRef:
            name: auth-secrets
        livenessProbe:
          httpGet:
            path: /api/v1/auth/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/auth/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: auth-service
  namespace: fec-auth
spec:
  selector:
    app: auth-service
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auth-ingress
  namespace: fec-auth
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
  - host: auth.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 8000
```

### 2. Deploy to K3s

```bash
# Create k8s directory
mkdir -p services/auth/k8s

# Copy manifests to k8s directory (create the files above)

# Build and import image to k3s
docker build -t fec-auth-service:latest services/auth/
docker save fec-auth-service:latest | sudo k3s ctr images import -

# Apply manifests
kubectl apply -f services/auth/k8s/namespace.yaml
kubectl apply -f services/auth/k8s/configmap.yaml
kubectl apply -f services/auth/k8s/secret.yaml
kubectl apply -f services/auth/k8s/postgres.yaml
kubectl apply -f services/auth/k8s/deployment.yaml

# Or apply all at once
kubectl apply -f services/auth/k8s/
```

### 3. Run Migrations

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n fec-auth -l app=auth-service -o jsonpath='{.items[0].metadata.name}')

# Run migrations
kubectl exec -n fec-auth $POD_NAME -- alembic upgrade head

# Check migration status
kubectl exec -n fec-auth $POD_NAME -- alembic current
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n fec-auth

# Check services
kubectl get svc -n fec-auth

# Check ingress
kubectl get ingress -n fec-auth

# View logs
kubectl logs -n fec-auth -l app=auth-service -f

# Describe deployment
kubectl describe deployment auth-service -n fec-auth
```

### 5. Access Service

```bash
# Port forward for local testing
kubectl port-forward -n fec-auth svc/auth-service 8000:8000

# Test health endpoint
curl http://localhost:8000/api/v1/auth/health

# Or add to /etc/hosts for ingress:
# echo "127.0.0.1 auth.local" | sudo tee -a /etc/hosts
# curl http://auth.local/api/v1/auth/health
```

### 6. Scaling

```bash
# Scale up
kubectl scale deployment auth-service -n fec-auth --replicas=3

# Scale down
kubectl scale deployment auth-service -n fec-auth --replicas=1

# Check scaling
kubectl get pods -n fec-auth -w
```

### 7. Cleanup

```bash
# Delete all resources
kubectl delete namespace fec-auth

# Or delete specific resources
kubectl delete -f services/auth/k8s/
```

---

## Running Migrations

### Alembic Commands Reference

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Upgrade to latest
alembic upgrade head

# Upgrade one step
alembic upgrade +1

# Downgrade one step
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# Show current revision
alembic current

# Show history
alembic history

# Show SQL without executing
alembic upgrade head --sql
```

---

## API Testing

### Using cURL

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123",
    "first_name": "Test",
    "last_name": "User"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "SecurePass123"
  }'

# Get current user (with token)
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"

# Refresh token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

### Using HTTPie

```bash
# Install httpie
pip install httpie

# Register
http POST localhost:8000/api/v1/auth/register \
  email=test@example.com password=SecurePass123

# Login
http POST localhost:8000/api/v1/auth/login \
  email=test@example.com password=SecurePass123

# Get current user
http localhost:8000/api/v1/auth/me \
  Authorization:"Bearer <token>"
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection
psql -h localhost -U postgres -d auth_db

# Check logs
docker logs auth-postgres
```

#### 2. Migration Errors
```bash
# Reset migrations (development only!)
alembic downgrade base
alembic upgrade head

# Check for pending migrations
alembic current
alembic heads
```

#### 3. Container Won't Start
```bash
# Check logs
docker logs auth-service

# Check container status
docker ps -a | grep auth

# Inspect container
docker inspect auth-service
```

#### 4. K3s Pod Issues
```bash
# Check pod status
kubectl describe pod -n fec-auth <pod-name>

# Check events
kubectl get events -n fec-auth --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n fec-auth <pod-name> --previous
```

### Health Check Endpoints

| Endpoint | Description | Expected Response |
|----------|-------------|-------------------|
| `/api/v1/auth/health` | Service health | `{"status": "healthy"}` |
| `/api/v1/auth/ready` | Database connectivity | `{"status": "ready"}` |

---

## Environment-Specific Configurations

| Environment | AUTH_ENV | AUTH_DEBUG | Notes |
|-------------|----------|------------|-------|
| Local | `local` | `true` | Auto-creates tables, shows docs |
| Development | `development` | `true` | Uses migrations |
| Staging | `staging` | `false` | Production-like |
| Production | `production` | `false` | Secured, no docs |
