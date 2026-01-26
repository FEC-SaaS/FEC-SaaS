# =============================================================================
# FEC SaaS Admin Portal - Production Multi-Stage Dockerfile
# =============================================================================
# This Dockerfile follows best practices for production Next.js applications:
# - Multi-stage build to minimize final image size
# - Non-root user for security
# - Standalone output mode for optimal containerization
# - Health checks for container orchestration
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies - Install only production dependencies
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps

# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy workspace configuration
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
COPY apps/admin-portal/package.json ./apps/admin-portal/
COPY packages/types/package.json ./packages/types/
COPY packages/ui/package.json ./packages/ui/
COPY packages/api-client/package.json ./packages/api-client/

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Install dependencies
RUN pnpm install --frozen-lockfile

# -----------------------------------------------------------------------------
# Stage 2: Builder - Build the application
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/admin-portal/node_modules ./apps/admin-portal/node_modules
COPY --from=deps /app/packages ./packages

# Copy source files
COPY . .

# Build shared packages first
RUN pnpm --filter @fec-saas/types build || true
RUN pnpm --filter @fec-saas/ui build || true
RUN pnpm --filter @fec-saas/api-client build || true

# Set environment variables for build
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Build the admin portal
RUN pnpm --filter @fec-saas/admin-portal build

# -----------------------------------------------------------------------------
# Stage 3: Runner - Production image
# -----------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

# Labels for container metadata
LABEL maintainer="FEC SaaS Team" \
      version="0.1.0" \
      description="Admin Portal for FEC SaaS Platform" \
      org.opencontainers.image.source="https://github.com/fec-saas/admin-portal"

# Set environment variables
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3001

# Create non-root user
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Copy the standalone build and static files
COPY --from=builder /app/apps/admin-portal/.next/standalone ./
COPY --from=builder /app/apps/admin-portal/.next/static ./apps/admin-portal/.next/static
COPY --from=builder /app/apps/admin-portal/public ./apps/admin-portal/public

# Set proper ownership
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT}/api/health || exit 1

# Start the application
CMD ["node", "apps/admin-portal/server.js"]
