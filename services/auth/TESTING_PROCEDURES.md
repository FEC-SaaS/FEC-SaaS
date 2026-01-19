# Auth Service Testing Procedures

This document provides comprehensive testing procedures for the FEC SaaS Auth Service.

## Prerequisites

```bash
# 1. Install dependencies
cd services/auth
poetry install

# 2. Start PostgreSQL (using Docker)
docker run -d --name auth-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=auth_db \
  -p 5432:5432 \
  postgres:15

# 3. Start Redis (using Docker)
docker run -d --name auth-redis \
  -p 6379:6379 \
  redis:7-alpine

# 4. Create .env file
cat > .env << 'EOF'
ENV=local
DEBUG=true
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/auth_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-key-change-in-production
EOF

# 5. Run migrations
poetry run alembic upgrade head

# 6. Start the server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 1. Basic Functionality Tests

### 1.1 Health Check
```bash
# Health endpoint
curl http://localhost:8000/api/v1/auth/health

# Expected: {"status":"healthy","service":"fec-saas-auth-service","version":"0.1.0","redis":"connected"}

# Readiness endpoint
curl http://localhost:8000/api/v1/auth/ready

# Expected: {"status":"ready","database":"connected","redis":"connected"}
```

### 1.2 User Registration
```bash
# Valid registration
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "SecurePass123!",
    "first_name": "Test",
    "last_name": "User"
  }'

# Expected: 201 Created with user data and tokens
```

### 1.3 User Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@example.com",
    "password": "SecurePass123!"
  }'

# Expected: 200 OK with user data and tokens
# Save the access_token and refresh_token for subsequent tests
```

### 1.4 Get Current User
```bash
# Replace ACCESS_TOKEN with actual token from login
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Expected: 200 OK with user profile
```

### 1.5 Token Refresh
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "REFRESH_TOKEN"}'

# Expected: 200 OK with new token pair (refresh token rotation)
# Old refresh token should now be invalid
```

### 1.6 Logout
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "REFRESH_TOKEN"}'

# Expected: 204 No Content
```

---

## 2. Security Tests

### 2.1 Password Validation (Weak Password Rejection)
```bash
# Too short
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weak1@test.com", "password": "Ab1!"}'

# Expected: 422 - Password must be at least 8 characters

# No uppercase
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weak2@test.com", "password": "password123!"}'

# Expected: 422 - Password must contain at least one uppercase letter

# No lowercase
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weak3@test.com", "password": "PASSWORD123!"}'

# Expected: 422 - Password must contain at least one lowercase letter

# No digit
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weak4@test.com", "password": "SecurePass!"}'

# Expected: 422 - Password must contain at least one digit

# No special character
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "weak5@test.com", "password": "SecurePass123"}'

# Expected: 422 - Password must contain at least one special character
```

### 2.2 Account Lockout (Brute Force Protection)
```bash
# Attempt login with wrong password 5 times
for i in {1..5}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "testuser@example.com", "password": "WrongPassword!"}'
  echo ""
  sleep 1
done

# Expected: After 5 attempts, account gets locked for 15 minutes
# Response: 429 Too Many Requests with "Account is locked. Try again in X seconds."

# Verify lockout persists
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com", "password": "SecurePass123!"}'

# Expected: Still locked even with correct password
```

### 2.3 Rate Limiting
```bash
# Rapid registration attempts (limit: 3/minute)
set +H

for i in {1..5}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"rate1limit$i@test.com\", \"password\": \"SecurePass123!\"}"
  echo ""
done


# Expected: After 3 requests, you get 429 Too Many Requests

# Rapid login attempts (limit: 5/minute)
for i in {1..7}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "ratelimit1@test.com", "password": "SecurePass123!"}'
  echo ""
done

# Expected: After 5 requests, you get 429 Too Many Requests
```

### 2.4 Token Blacklisting
```bash
# 1. Login and get tokens
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com", "password": "SecurePass123!"}')

ACCESS_TOKEN=$(echo $RESPONSE | jq -r '.tokens.access_token')
REFRESH_TOKEN=$(echo $RESPONSE | jq -r '.tokens.refresh_token')

# 2. Verify token works
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# Expected: 200 OK

# 3. Logout (blacklists the token)
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# 4. Try to use blacklisted access token
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# Expected: 401 Unauthorized - "Token has been revoked"

# 5. Try to refresh with blacklisted refresh token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
# Expected: 401 Unauthorized - "Refresh token has been revoked"
```

### 2.5 Refresh Token Rotation
```bash
# 1. Login
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com", "password": "SecurePass123!"}')

OLD_REFRESH=$(echo $RESPONSE | jq -r '.tokens.refresh_token')

# 2. Refresh tokens
NEW_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$OLD_REFRESH\"}")

NEW_REFRESH=$(echo $NEW_RESPONSE | jq -r '.refresh_token')

echo "Old refresh token: ${OLD_REFRESH:0:50}..."
echo "New refresh token: ${NEW_REFRESH:0:50}..."

# 3. Try to use old refresh token again (should be blacklisted)
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$OLD_REFRESH\"}"
# Expected: 401 Unauthorized - old token is blacklisted after rotation
```

### 2.6 Security Headers
```bash
curl -v http://localhost:8000/api/v1/auth/health 2>&1 | grep -E "^< [A-Z]"

# Expected headers:
# X-Request-ID: <uuid>
# Content-Security-Policy: default-src 'self'; ...
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
# Permissions-Policy: accelerometer=(), ...
```

---

## 3. Edge Case Tests

### 3.1 Duplicate Email Registration
```bash
# First registration
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "duplicate@test.com", "password": "SecurePass123!"}'
# Expected: 201 Created

# Second registration with same email
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "duplicate@test.com", "password": "DifferentPass123!"}'
# Expected: 400 Bad Request - "Email already registered"
```

### 3.2 Invalid Email Format
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "not-an-email", "password": "SecurePass123!"}'
# Expected: 422 - Invalid email format
```

### 3.3 Very Long Inputs
```bash
# Long password (should fail - bcrypt limit is 72 bytes)
LONG_PASS=$(python -c "print('A' * 100 + '1!')")
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"longpass@test.com\", \"password\": \"$LONG_PASS\"}"
# Expected: 422 - Password cannot exceed 72 characters
```

### 3.4 Unicode in Names
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "unicode@test.com",
    "password": "SecurePass123!",
    "first_name": "日本語",
    "last_name": "Émile"
  }'
# Expected: 201 Created - Unicode should be supported
```

### 3.5 SQL Injection Attempt
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@test.com'; DROP TABLE users;--",
    "password": "password"
  }'
# Expected: 422 - Invalid email format (SQLAlchemy ORM prevents injection)
```

### 3.6 JWT Tampering
```bash
# Get a valid token
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com", "password": "SecurePass123!"}')

TOKEN=$(echo $RESPONSE | jq -r '.tokens.access_token')

# Tamper with token (change one character)
TAMPERED_TOKEN="${TOKEN:0:-5}AAAAA"

curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TAMPERED_TOKEN"
# Expected: 401 Unauthorized - Invalid token
```

### 3.7 Expired Token
```bash
# Wait for token to expire (15 minutes by default)
# Or use a token from a previous session
# Expected: 401 Unauthorized - Invalid or expired token
```

---

## 4. GDPR Compliance Tests

### 4.1 Data Export
```bash
curl http://localhost:8000/api/v1/auth/export-data \
  -H "Authorization: Bearer ACCESS_TOKEN"

# Expected: Full user data export including sessions and privacy consents
```

### 4.2 Privacy Consents
```bash
# Grant consent
curl -X POST http://localhost:8000/api/v1/auth/privacy-consents \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"consent_type": "marketing", "granted": true}'

# Revoke consent
curl -X POST http://localhost:8000/api/v1/auth/privacy-consents \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"consent_type": "marketing", "granted": false}'
```

### 4.3 Account Deletion
```bash
curl -X DELETE http://localhost:8000/api/v1/auth/account \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"password": "SecurePass123!", "confirmation": "DELETE"}'
# Expected: 204 No Content - Account permanently deleted
```

---

## 5. Load Testing

### 5.1 Concurrent Registrations
```bash
# Using Apache Bench or wrk
# Install: apt install apache2-utils

ab -n 100 -c 10 -p register.json -T application/json \
  http://localhost:8000/api/v1/auth/register

# Create register.json:
# {"email": "loadtest${RANDOM}@test.com", "password": "SecurePass123!"}
```

### 5.2 Login Storm
```bash
# Using wrk (install: apt install wrk)
wrk -t4 -c100 -d30s -s login.lua http://localhost:8000/api/v1/auth/login

# Create login.lua:
# wrk.method = "POST"
# wrk.headers["Content-Type"] = "application/json"
# wrk.body = '{"email": "testuser@example.com", "password": "SecurePass123!"}'
```

---

## 6. Integration Tests

### 6.1 Database Connection Failure
```bash
# Stop PostgreSQL
docker stop auth-postgres

# Try health check
curl http://localhost:8000/api/v1/auth/ready
# Expected: 503 - database: error

# Restart PostgreSQL
docker start auth-postgres
```

### 6.2 Redis Connection Failure
```bash
# Stop Redis
docker stop auth-redis

# Login should still work (Redis is optional)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "testuser@example.com", "password": "SecurePass123!"}'
# Expected: 200 OK (but rate limiting and blacklisting won't work)

# Health check shows Redis status
curl http://localhost:8000/api/v1/auth/health
# Expected: {"redis": "not_configured"}

# Restart Redis
docker start auth-redis
```

---

## 7. Audit Log Verification

Check application logs for audit events:

```bash
# View logs (structured JSON format)
docker logs auth-service 2>&1 | grep "audit_event"

# Expected log entries for:
# - login_success / login_failed
# - register
# - logout
# - password_change
# - account_locked
# - token_refresh
# - data_export_requested
# - account_deleted
```

---

## 8. Docker Compose Full Stack Test

```bash
cd services/auth

# Start full stack
docker-compose up -d

# Wait for services to be ready
sleep 10

# Run all tests against containerized service
curl http://localhost:8000/api/v1/auth/health

# Check logs
docker-compose logs auth
```

---

## Summary Checklist

| Test Category | Status |
|--------------|--------|
| Basic Registration/Login | [ ] |
| Password Validation | [ ] |
| Account Lockout | [ ] |
| Rate Limiting | [ ] |
| Token Blacklisting | [ ] |
| Refresh Token Rotation | [ ] |
| Security Headers | [ ] |
| Edge Cases (Unicode, Long inputs) | [ ] |
| SQL Injection Prevention | [ ] |
| JWT Tampering Prevention | [ ] |
| GDPR Compliance | [ ] |
| Load Testing | [ ] |
| Database Failover | [ ] |
| Redis Failover | [ ] |
| Audit Logging | [ ] |

## Production Readiness Checklist

- [x] Password strength validation
- [x] Rate limiting on all sensitive endpoints
- [x] Account lockout after failed attempts
- [x] JWT token expiry (15 min access, 30 day refresh)
- [x] Refresh token rotation
- [x] Token blacklisting with Redis
- [x] Security headers (CSP, XSS, HSTS)
- [x] Request ID tracing
- [x] Structured audit logging
- [x] GDPR compliance (data export, deletion)
- [x] Health/readiness endpoints
- [ ] Email service integration (pending)
- [ ] SMS service integration (pending)
- [ ] Social OAuth implementation (pending)
