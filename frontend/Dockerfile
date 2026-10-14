# Multi-stage production build for Svelte Vite frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Cache dependencies
COPY package.json ./
RUN npm install

# Build production artifacts
COPY . .
RUN npm run build

# -------------------------------------------------------------
# Production runtime stage: Lightweight Nginx server
# -------------------------------------------------------------
FROM nginx:alpine AS runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built SPA assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
