# Agentic Exception Platform UI - Phase 4

Frontend UI for the Agentic Exception Processing Platform.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling and dev server
- **Material UI (MUI)** v5+ for components
- **TanStack Query (React Query)** for data fetching
- **react-router-dom** for routing
- **axios** for HTTP requests

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file in `ui/` directory:
```env
VITE_API_BASE_URL=http://localhost:8000
```

3. Run development server:
```bash
npm run dev
```

4. Build for production:
```bash
npm run build
```

5. Preview production build:
```bash
npm run preview
```

## Project Structure

```
ui/
├── src/
│   ├── api/              # REST API client functions
│   ├── components/       # Reusable UI components
│   ├── hooks/           # Custom React hooks
│   ├── layouts/         # Layout components
│   ├── routes/          # Route definitions and page components
│   ├── theme/           # MUI theme configuration
│   ├── types/           # TypeScript type definitions
│   ├── utils/           # Utility functions
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Environment Variables

- `VITE_API_BASE_URL` - Backend API base URL (required)

## Development

The dev server runs on `http://localhost:3000` by default.

## References

- [UI Guidelines](../docs/10-ui-guidelines.md)
- [Phase 4 MVP Plan](../docs/11-ui-phase4-mvp-plan.md)
- [Phase 4 Issues](../.github/ISSUE_TEMPLATE/phase4-ui-issues.md)


