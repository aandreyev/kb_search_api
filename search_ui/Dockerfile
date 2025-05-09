# Stage 1: Build the SvelteKit app
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package.json and lock file
COPY package.json package-lock.json* npm-shrinkwrap.json* ./ 
# Make sure to include pnpm-lock.yaml if you use pnpm, or yarn.lock for yarn

# Install dependencies
RUN npm ci

# Copy the rest of the application source code
COPY . .

# Build the SvelteKit app for static deployment
# Pass public API URL at build time if needed by the app for static generation
# ARG VITE_RAG_API_URL=/api # Example, will be overridden by docker-compose env
# ENV VITE_RAG_API_URL=${VITE_RAG_API_URL}
RUN npm run build

# Stage 2: Serve the static assets with Nginx
FROM nginx:stable-alpine

# Copy the built SvelteKit app from the builder stage to Nginx html directory
COPY --from=builder /app/build /usr/share/nginx/html

# Copy a custom Nginx configuration file (optional, but good for SPAs)
# Create search_ui/nginx.conf if you need custom routing for SPA
COPY nginx.conf /etc/nginx/conf.d/default.conf 

# Expose port 80 (Nginx default)
EXPOSE 80

# Nginx will be started by default when the container runs
CMD ["nginx", "-g", "daemon off;"] 