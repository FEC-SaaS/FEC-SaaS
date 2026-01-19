# FEC SaaS Testing Guide

This guide provides step-by-step procedures to test the components built so far.

---

## Prerequisites

Ensure you have installed:
- Node.js 18+ and pnpm
- Python 3.12+ and Poetry
- PostgreSQL 15+
- Redis (optional, for caching)

---

## Step 1: Database Setup

### Create Required Databases

Open your PostgreSQL client (pgAdmin, psql, or DBeaver) and run:

```sql
-- Create databases for each service
CREATE DATABASE auth_db;
CREATE DATABASE notification_db;
CREATE DATABASE venue_db;
CREATE DATABASE booking_db;
CREATE DATABASE customer_db;

-- Optional: Create a dedicated user
CREATE USER fec_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE auth_db TO fec_user;
GRANT ALL PRIVILEGES ON DATABASE notification_db TO fec_user;
GRANT ALL PRIVILEGES ON DATABASE venue_db TO fec_user;
GRANT ALL PRIVILEGES ON DATABASE booking_db TO fec_user;
GRANT ALL PRIVILEGES ON DATABASE customer_db TO fec_user;
```

### Using psql command line (if available):

```bash
# Windows (if PostgreSQL bin is in PATH)
psql -U postgres -c "CREATE DATABASE notification_db;"
psql -U postgres -c "CREATE DATABASE auth_db;"

# Or connect to psql first
psql -U postgres
# Then run: CREATE DATABASE notification_db;
```

---

## Step 2: Backend Services Setup

### 2.1 Auth Service

```bash
cd services/auth

# Create .env file
cp .env.example .env
# Edit .env with your database credentials:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/auth_db

# Install dependencies
poetry install

# Run migrations
poetry run alembic upgrade head

# Start the service
poetry run uvicorn app.main:app --reload --port 8001
```

**Test Auth Service:**
```bash
# Health check
curl http://localhost:8001/health

# API docs
# Open browser: http://localhost:8001/docs
```

### 2.2 Notification Service

```bash
cd services/notification

# Create .env file
cp .env.example .env
# Edit .env with your database credentials:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/notification_db

# Install dependencies
poetry install

# Run migrations (after creating notification_db)
poetry run alembic upgrade head

# Start the service
poetry run uvicorn app.main:app --reload --port 8002
```

**Test Notification Service:**
```bash
# Health check
curl http://localhost:8002/health

# API docs
# Open browser: http://localhost:8002/docs
```

---

## Step 3: Frontend Packages Setup

### 3.1 Install Root Dependencies

```bash
cd C:\Users\USER\Desktop\VSCODE-PROJECT\SAAS\Fec-SaaS

# Install all workspace dependencies
pnpm install
```

### 3.2 Build Shared Packages

Build packages in order (types → api-client → ui):

```bash
# Build types package
cd packages/types
pnpm build

# Build API client package
cd ../api-client
pnpm build

# Build UI package
cd ../ui
pnpm build
```

Or from root:
```bash
pnpm --filter @fec-saas/types build
pnpm --filter @fec-saas/api-client build
pnpm --filter @fec-saas/ui build
```

---

## Step 4: Admin Portal Testing

### 4.1 Start Development Server

```bash
cd apps/admin-portal

# Install dependencies (if not done via root pnpm install)
pnpm install

# Start dev server
pnpm dev
```

### 4.2 Access the Application

Open browser: **http://localhost:3001**

### 4.3 Manual Testing Checklist

#### Dashboard Page (`/dashboard`)
- [ ] Stats cards display correctly (Revenue, Venues, Bookings, Customers)
- [ ] Recent Party Bookings list shows mock data
- [ ] Top Performing Venues list shows mock data
- [ ] Quick Actions buttons are clickable
- [ ] Page is responsive on mobile

#### Venues Page (`/venues`)
- [ ] Page header with "Add Venue" button displays
- [ ] Search input filters venues by name/city
- [ ] Venue table displays all columns correctly
- [ ] Status badges show correct colors (active=green, maintenance=yellow, inactive=gray)
- [ ] Click on row opens detail panel
- [ ] Action buttons (view, edit, delete) are visible

#### Venue Detail Page (`/venues/[id]`)
- [ ] Back navigation works
- [ ] Stats cards display venue metrics
- [ ] Edit button toggles edit mode
- [ ] Form fields are editable in edit mode
- [ ] Operating hours display correctly

#### Party Bookings Page (`/parties`)
- [ ] Stats row displays correctly
- [ ] Search filters bookings
- [ ] Status dropdown filters by status
- [ ] Table displays all booking information
- [ ] Status badges show correct colors
- [ ] Confirm/Cancel buttons show for pending bookings
- [ ] Click on row opens detail panel

#### Party Detail Page (`/parties/[id]`)
- [ ] All customer information displays
- [ ] Event details show correctly
- [ ] Party timeline displays all activities
- [ ] Payment summary calculates correctly
- [ ] Notes section displays
- [ ] Quick actions buttons work

#### Customers Page (`/customers`)
- [ ] Customer list displays
- [ ] Search filters customers
- [ ] Membership tier badges show correct colors

#### Navigation
- [ ] Sidebar collapses/expands
- [ ] All navigation links work
- [ ] Active page is highlighted
- [ ] Header shows current page name
- [ ] Notification bell icon visible

---

## Step 5: Component Testing

### Test UI Components in Isolation

Create a simple test page to verify components:

```bash
# In apps/admin-portal/src/app/test/page.tsx
```

Test each component:
- Button (all variants: default, destructive, outline, secondary, ghost, link)
- Input (with placeholder, disabled state)
- Card (with header, content, footer)
- Badge (all variants)
- Alert (all variants)
- StatCard (with trend, with description)
- DataTable (with data, empty state, loading state)

---

## Step 6: API Integration Testing

Once backend services are running, update the API client configuration:

### 6.1 Configure API Base URL

```typescript
// In apps/admin-portal/src/lib/api-config.ts
import { setAuthToken, setBaseUrl } from '@fec-saas/api-client';

// Set base URL for API calls
setBaseUrl('http://localhost:8001'); // Auth service
```

### 6.2 Test API Calls

```typescript
import { authApi } from '@fec-saas/api-client';

// Test login
const response = await authApi.login({
  email: 'test@example.com',
  password: 'password123'
});
```

---

## Step 7: Build Verification

### Build All Packages

```bash
# From project root
pnpm build

# Or build specific apps
pnpm --filter @fec-saas/admin-portal build
```

### Check for TypeScript Errors

```bash
# Type check all packages
pnpm type-check

# Or specific package
cd apps/admin-portal
pnpm type-check
```

---

## Troubleshooting

### Database Connection Issues

1. Verify PostgreSQL is running:
   ```bash
   # Windows
   pg_isready -h localhost -p 5432
   ```

2. Check connection string in `.env`:
   ```
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/notification_db
   ```

3. Ensure database exists:
   ```sql
   SELECT datname FROM pg_database;
   ```

### Module Not Found Errors

1. Rebuild packages:
   ```bash
   pnpm --filter @fec-saas/types build
   pnpm --filter @fec-saas/api-client build
   pnpm --filter @fec-saas/ui build
   ```

2. Clear Next.js cache:
   ```bash
   cd apps/admin-portal
   rm -rf .next
   pnpm dev
   ```

### Port Already in Use

```bash
# Find process using port
netstat -ano | findstr :3001

# Kill process (Windows)
taskkill /PID <PID> /F
```

---

## Quick Start Commands

```bash
# Terminal 1: Start Auth Service
cd services/auth && poetry run uvicorn app.main:app --reload --port 8001

# Terminal 2: Start Notification Service
cd services/notification && poetry run uvicorn app.main:app --reload --port 8002

# Terminal 3: Start Admin Portal
cd apps/admin-portal && pnpm dev

# Access Points:
# - Admin Portal: http://localhost:3001
# - Auth API Docs: http://localhost:8001/docs
# - Notification API Docs: http://localhost:8002/docs
```
