# AgentChains Frontend

React 19 + TypeScript 5.9 + Tailwind CSS 4 + Vite 7

## Quick Start

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # Production build
npm run test     # Run 391 tests
npm run lint     # ESLint check
```

## Tech Stack

- **React 19** -- UI framework
- **TypeScript 5.9** -- Type safety
- **Tailwind CSS 4** -- Styling (dark futuristic theme)
- **Vite 7** -- Build tool (dev server on port 3000)
- **TanStack React Query v5** -- Server state management
- **Recharts 3** -- Charts and visualizations
- **Lucide React** -- Icon library

## Project Structure

```
src/
├── pages/          # 13 page components
├── components/     # 25 reusable UI components
├── hooks/          # Auth + React Query hooks
├── lib/            # API client, WebSocket, formatters
├── types/          # TypeScript type definitions
└── index.css       # Design system (@theme tokens)
```

## Key Components

- **Shell** -- App layout with sidebar and top bar
- **Sidebar** -- Navigation with collapsible sections
- **PageHeader** -- Consistent page titles with actions
- **StatCard** -- Metric display with trend indicators
- **DataTable** -- Sortable, filterable data tables
- **Pagination** -- Page navigation for lists
- **Badge** -- Status and category labels
- **MiniChart** -- Inline sparkline charts
- **ProgressRing** -- Circular progress indicators
- **AnimatedCounter** -- Smooth number transitions

## Design System

Dark theme with glass morphism. See [Frontend Guide](../docs/frontend-guide.md) for full details.

Key classes:

| Class | Purpose |
|-------|---------|
| `.glass-card` | Translucent card with backdrop blur |
| `.btn-primary` | Primary action button |
| `.btn-secondary` | Secondary action button |
| `.futuristic-input` | Styled form input |
| `.gradient-text` | Gradient text effect |

## API Proxy

Vite proxies `/api` to `http://localhost:8000` and `/ws` to `ws://localhost:8000`.

The backend must be running for API calls and WebSocket connections to work. See the root README for backend setup.

## Documentation

- [Frontend Guide](../docs/frontend-guide.md) -- Full component library + design system
- [Architecture](../docs/architecture.md) -- System overview
