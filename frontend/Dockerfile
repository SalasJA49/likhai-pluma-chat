# Frontend multi-stage Dockerfile: build with node, serve static assets with nginx
FROM node:20-alpine AS build

WORKDIR /app

# Install deps and build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent

# Copy source and build
COPY frontend/ .
RUN npm run build

# Production image: use nginx to serve static files
FROM nginx:alpine

# Remove default nginx content
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Expose standard HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
