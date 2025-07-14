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

# Declare ARGs that can be passed from docker-compose build
ARG VITE_MSAL_CLIENT_ID
ARG VITE_MSAL_TENANT_ID
ARG VITE_MSAL_REDIRECT_URI
ARG VITE_RAG_API_URL
ARG VITE_API_SCOPE

# Set ENVs for the build process from the ARGs
ENV VITE_MSAL_CLIENT_ID=${VITE_MSAL_CLIENT_ID}
ENV VITE_MSAL_TENANT_ID=${VITE_MSAL_TENANT_ID}
ENV VITE_MSAL_REDIRECT_URI=${VITE_MSAL_REDIRECT_URI}
ENV VITE_RAG_API_URL=${VITE_RAG_API_URL}
ENV VITE_API_SCOPE=${VITE_API_SCOPE}

# Build the SvelteKit app for static deployment
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