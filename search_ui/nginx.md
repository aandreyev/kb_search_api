# The Role of Nginx in the Application

Nginx plays a crucial and dual role within this project. It is configured to be both a high-performance static file server for our SvelteKit frontend and a powerful reverse proxy to route API traffic. This document breaks down its responsibilities.

The configuration driving this behavior is found in `search_ui/nginx.conf`.

---

## Role 1: Serving the SvelteKit Frontend (as a Static Site Server)

This is the primary and most fundamental role of Nginx in our stack.

1.  **The Problem:** The `search_ui` is a SvelteKit application. When the project is built via `npm run build`, SvelteKit compiles all the `.svelte` and `.ts` source files into a set of highly optimized, static assets: HTML, CSS, and JavaScript. These files are the "production version" of the app, ready to be served to users.

2.  **Nginx's Solution:** Nginx acts as the web server for these static files. It's extremely lightweight and efficient at this task, making it an ideal choice for serving a compiled frontend application.

3.  **The Build & Serve Process (in `search_ui/Dockerfile`):**
    The `Dockerfile` for the `search_ui` service uses a multi-stage build to keep the final image small and secure.
    *   **Stage 1 (The "Builder"):** A Node.js environment is created, `npm` dependencies are installed, and the `npm run build` command is executed. The output—the complete static site—is placed in an `/app/build` folder inside this temporary build environment.
    *   **Stage 2 (The "Final Image"):** A clean, minimal `nginx:stable-alpine` image is used as a base. This image does **not** contain Node.js, your application's source code, or any development dependencies. The *only* thing copied from the "Builder" stage is the `/app/build` folder, which is placed into `/usr/share/nginx/html`, the default directory where Nginx looks for files to serve.

4.  **Handling Single-Page Application (SPA) Routing:**
    A critical piece of the configuration for any SPA is handling client-side routing. The `location /` block in `nginx.conf` solves this:
    ```nginx
    location / {
        try_files $uri $uri/ /index.html;
    }
    ```
    This directive tells Nginx how to handle incoming requests:
    - First, `try_files` looks for a file that exactly matches the request URI (e.g., `/favicon.png`).
    - If it doesn't find a file, it looks for a directory with that name (e.g., `/assets/`).
    - If neither of those exist, it **falls back to serving `/index.html`**.

    This is essential because it allows the SvelteKit router (which runs in the browser) to manage the application's routes. If a user directly navigates to a "deep link" like `http://localhost:5173/some/page`, Nginx won't find a file named `some/page` on the server and would normally return a 404 error. Instead, this rule ensures `index.html` is served, the Svelte app loads, and its internal router displays the correct component for the `/some/page` route.

---

## Role 2: Acting as a Reverse Proxy

The `nginx.conf` file is also prepared for a more advanced, production-like role as a reverse proxy, even though it is not used in the default local `docker-compose` setup.

1.  **The Problem:** In a production environment, it is insecure and inconvenient to expose multiple service ports (e.g., `5173` for the frontend, `8002` for the API) to the internet. The standard practice is to have a single entry point, like `https://your-domain.com`.

2.  **Nginx's Solution (The Reverse Proxy):** The `location /api/` block configures Nginx to intelligently forward traffic.
    ```nginx
    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://rag_api_service:8002;
        # ... other proxy headers ...
    }
    ```
    This block instructs Nginx:
    - "If you receive a request where the path starts with `/api/`..."
    - "...don't look for a local file to serve."
    - "...instead, forward this request to the `rag_api_service` at its internal Docker network address (`http://rag_api_service:8002`)."
    - The `rewrite` rule is a clever addition that strips the `/api/` prefix from the request path before forwarding it, so the backend service receives a clean request (e.g., `/chat` instead of `/api/chat`).

---

### How the Local Setup Differs from Production

It is important to understand why the `VITE_RAG_API_URL` environment variable is different between the local and production environments.

-   **Production (`VITE_RAG_API_URL="/api"`):**
    - The frontend code is built to make API calls to a relative path, like `/api/chat`.
    - The browser sends this request to the same domain where the UI is hosted (e.g., `https://kb.adlvlaw.au/api/chat`).
    - The main Nginx server receives this request, and its `location /api/` block proxies the request to the backend container. The browser only ever communicates with one server.

-   **Local `docker-compose` (`VITE_RAG_API_URL="http://localhost:8002"`):**
    - The frontend code is built to make API calls to an absolute URL.
    - The browser, viewing the UI from `http://localhost:5173`, makes a **direct, cross-origin request** to the backend service at `http://localhost:8002/chat`.
    - In this setup, the `location /api/` block in the `frontend_nginx` service's `nginx.conf` is **never actually used**. The browser itself is acting as the integrator, talking directly to two different `localhost` ports. 