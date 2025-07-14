# Search UI Overview

## Purpose
The Search UI is a SvelteKit-based frontend application that provides a user interface for searching a knowledge base, viewing results, previewing PDFs, and handling Microsoft authentication via Azure AD (Entra ID). It integrates with the RAG API backend for search functionality and activity logging, focusing on a modern, responsive design with best UX practices.

## Key Components
The app includes the following main files and directories:

- **src/lib/SearchInterface.svelte**: Core component for search input, results display, pagination, PDF previews in a modal, and activity logging.
- **src/lib/authStore.ts**: Svelte store managing authentication state, including user info, access tokens, and loading/error states.
- **src/lib/authService.ts**: Handles MSAL (Microsoft Authentication Library) configuration, instance initialization, token acquisition, and login/logout redirects.
- **src/lib/activityLogger.ts**: Utility for logging user activities (e.g., searches, previews) to the backend API.
- **src/lib/LoginButton.svelte**: Button component for login/logout with Microsoft.
- **src/routes/+page.svelte**: Main page rendering LoginButton or SearchInterface based on auth state.
- **src/routes/+layout.svelte**: Layout component initializing auth on mount and providing a container for pages.
- **src/routes/+layout.ts**: Likely handles server-side logic or data loading (not detailed in results).
- **src/app.html**: Base HTML template.
- **src/app.css**: Global styles.
- **vite.config.ts**: Vite configuration for building SvelteKit app.
- **svelte.config.js**: Svelte configuration.
- **package.json**: Dependencies including Svelte, SvelteKit, MSAL, Tailwind CSS, etc.
- **e2e/**: Playwright end-to-end tests.
- **nginx.conf**: NGINX config for serving the built app.

## Configuration
- **Environment Variables** (from .env or Vite):
  - `VITE_MSAL_CLIENT_ID`, `VITE_MSAL_TENANT_ID`, `VITE_MSAL_REDIRECT_URI`: For MSAL auth.
  - `VITE_API_SCOPE`: Scope for backend API access.
  - `VITE_RAG_API_URL`: Base URL for RAG API endpoints.
- Uses sessionStorage for MSAL cache.

## How It Works
1. **Authentication Flow**:
   - On app load (+layout.svelte onMount), initializes MSAL instance and checks for active account.
   - If authenticated, acquires token silently and updates authStore.
   - Login redirects to Microsoft login; post-login, handles redirect and sets active account.
   - Logout clears session and redirects.
   - authStore tracks state; components subscribe for reactivity.

2. **Search Functionality** (SearchInterface.svelte):
   - Input field for query; submits on Enter or button click.
   - Acquires token, calls /search API with query and limit.
   - Displays paginated results with details (title, summary, snippets) and actions (download, preview).
   - Client-side pagination on fetched results.
   - Logs searches and previews.

3. **Document Preview**:
   - PDFs: Fetches via /preview-pdf API with token, creates blob URL, displays in iframe modal.
   - MS Word documents: Rendered using a third-party Microsoft viewer for preview functionality.
   - Logs preview events.

4. **Activity Logging**:
   - Logs events like login, search, preview to /log-activity API.
   - Includes user info from MSAL account.

5. **UI/UX**:
   - Responsive design with Tailwind CSS.
   - Loading states, error messages, modal for previews.
   - Conditional rendering based on auth state.

6. **Building and Running**:
   - Dev: `npm run dev` (Vite server).
   - Build: `npm run build` for production.
   - Served via NGINX (nginx.conf) in Docker or deployment.
   - Tests: Playwright E2E in e2e/.

## Dependencies
- **Svelte/SvelteKit**: UI framework.
- **@azure/msal-browser**: Authentication.
- **Tailwind CSS**: Styling.
- **Playwright**: Testing.

## Potential Improvements
- Add infinite scrolling or server-side pagination.
- Support more file types in previews.
- Enhance error handling and UX feedback.
- Integrate real-time updates or advanced search filters.

This frontend provides a secure, user-friendly interface for interacting with the KB search backend. 