# AgentChains Frontend

React 19 + TypeScript 5.9 + Tailwind CSS 4 + Vite 7.

## Quick Start

```bash
npm install
npm run dev      # http://localhost:3000
npm run dev:host # bind to 127.0.0.1:3000 (local parity)
npm run build
npm run test
npm run lint
```

## Structure

```text
src/
  pages/        # Role and workflow pages
  components/   # Reusable UI components
  hooks/        # Auth and React Query hooks
  lib/          # API client and websocket helpers
  types/        # API and domain types
  test/         # Shared test helpers
```

## Role Dashboard Surface

Primary role flows:
- `src/pages/RoleLandingPage.tsx`
- `src/pages/AgentDashboardPage.tsx`
- `src/pages/CreatorDashboardPage.tsx`
- `src/pages/AdminDashboardPage.tsx`

Wiring points:
- `src/App.tsx`
- `src/components/Sidebar.tsx`
- `src/lib/api.ts`
- `src/types/api.ts`

## API and WebSocket

- REST proxy: `/api` -> `http://localhost:8000`
- WebSocket proxy: `/ws` -> `ws://localhost:8000`
- Canonical realtime endpoint: `/ws/v2/events`

## Quality Gates

```bash
npm run test
npm run lint
npm run build
```

## Related Docs

- `../README.md`
- `../docs/API.md`
- `../docs/SECURITY_NO_LEAK_WEBSOCKET_MIGRATION.md`
- `../docs/ADMIN_DASHBOARD_RUNBOOK.md`
