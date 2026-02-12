# AgentChains Frontend Developer Guide

> React 19 + TypeScript 5.9 + Tailwind CSS 4 + Vite 7 + Recharts 3 + TanStack React Query v5

---

## 1. Quick Start

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (port 3000)
npm run dev

# Type-check + production build
npm run build

# Run tests
npm run test            # single run
npm run test:watch      # watch mode
npm run test:coverage   # with coverage report

# Preview production build
npm run preview

# Lint
npm run lint
```

### Vite Dev Proxy

The Vite dev server proxies API and WebSocket requests to the backend:

| Path   | Target                    | Notes              |
| ------ | ------------------------- | ------------------ |
| `/api` | `http://localhost:8000`   | REST API proxy     |
| `/ws`  | `ws://localhost:8000`     | WebSocket proxy    |

This means you never hard-code `localhost:8000` in frontend code -- all API calls go through `/api/v1/...` and Vite forwards them.

### Build Configuration

```ts
// vite.config.ts
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    target: "esnext",
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ["recharts"], // separate chunk for chart library
        },
      },
    },
  },
});
```

### Key Dependencies

| Package                  | Version    | Purpose                        |
| ------------------------ | ---------- | ------------------------------ |
| `react`                  | ^19.2.0    | UI framework                   |
| `@tanstack/react-query`  | ^5.90.20   | Server state management        |
| `tailwindcss`            | ^4.1.18    | Utility-first CSS              |
| `recharts`               | ^3.7.0     | Chart components               |
| `lucide-react`           | ^0.563.0   | Icon library                   |
| `vitest`                 | ^4.0.18    | Test runner                    |
| `@testing-library/react` | ^16.3.2    | Component testing utilities    |

---

## 2. Architecture Overview

### SPA with State-Driven Navigation (No Router)

The app uses **`useState<TabId>`** instead of a router library. The `TabId` union type defines all navigable pages:

```ts
export type TabId =
  | "dashboard" | "agents" | "listings" | "catalog"
  | "transactions" | "wallet" | "redeem"
  | "analytics" | "reputation"
  | "integrations" | "creator";
```

Navigation works by setting `activeTab` state. The `App.tsx` component conditionally renders the matching page component.

### Component Tree

```
App
 +-- QueryClientProvider
      +-- ToastProvider
           +-- Sidebar (fixed left, collapsible)
           +-- Shell (sticky header)
                +-- <main> (dot-grid background, page content)
                     +-- [Active Page Component]
```

### React Query Configuration

```ts
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,   // 30 seconds before refetch
      retry: 2,            // retry failed requests twice
      refetchOnWindowFocus: false,
    },
  },
});
```

### Lazy Loading

Non-critical pages use `React.lazy()` with `<Suspense>` to code-split:

```tsx
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));

// In render:
{activeTab === "analytics" && (
  <Suspense fallback={loading}>
    <AnalyticsPage />
  </Suspense>
)}
```

Eagerly loaded pages: `DashboardPage`, `AgentsPage`, `ListingsPage`, `TransactionsPage`, `ReputationPage`.

Lazy loaded pages: `AnalyticsPage`, `CatalogPage`, `WalletPage`, `IntegrationsPage`, `CreatorLoginPage`, `CreatorDashboardPage`, `RedemptionPage`.

---

## 3. Design System

All design tokens are defined in `frontend/src/index.css` using Tailwind CSS 4's `@theme` directive. This makes them available as Tailwind utility classes (e.g., `bg-surface`, `text-primary`, `border-border-glow`).

### 3.1 Color Palette

#### Surface (Background) Colors

| Token              | Value       | Tailwind Class           | Usage                    |
| ------------------ | ----------- | ------------------------ | ------------------------ |
| `surface`          | `#0a0a0f`   | `bg-surface`             | Page background          |
| `surface-raised`   | `#0d1117`   | `bg-surface-raised`      | Card backgrounds, inputs |
| `surface-overlay`  | `#151921`   | `bg-surface-overlay`     | Overlays, hover states   |
| `surface-hover`    | `#1a2030`   | `bg-surface-hover`       | Hover backgrounds        |
| `surface-active`   | `#1e2740`   | `bg-surface-active`      | Active/pressed states    |

#### Border Colors

| Token           | Value                       | Tailwind Class        | Usage              |
| --------------- | --------------------------- | --------------------- | ------------------ |
| `border-subtle` | `#1e293b`                   | `border-border-subtle`| Default borders    |
| `border-glow`   | `#1e3a5f`                   | `border-border-glow`  | Emphasized borders |
| `border-focus`  | `rgba(0, 212, 255, 0.4)`    | `border-border-focus` | Focus ring color   |

#### Text Colors

| Token            | Value      | Tailwind Class        | Usage          |
| ---------------- | ---------- | --------------------- | -------------- |
| `text-primary`   | `#e2e8f0`  | `text-text-primary`   | Body text      |
| `text-secondary` | `#94a3b8`  | `text-text-secondary` | Secondary text |
| `text-muted`     | `#475569`  | `text-text-muted`     | Labels, hints  |

#### Accent Colors

| Name          | Base       | Hover      | Glow (15% opacity)         |
| ------------- | ---------- | ---------- | -------------------------- |
| **Primary**   | `#00d4ff`  | `#38bdf8`  | `rgba(0, 212, 255, 0.15)`  |
| **Secondary** | `#8b5cf6`  | `#a78bfa`  | `rgba(139, 92, 246, 0.15)` |
| **Success**   | `#10b981`  | `#34d399`  | `rgba(16, 185, 129, 0.15)` |
| **Warning**   | `#f59e0b`  | --         | `rgba(245, 158, 11, 0.15)` |
| **Danger**    | `#ef4444`  | --         | `rgba(239, 68, 68, 0.15)`  |

### 3.2 Typography

| Role      | Font Family                                | Tailwind Usage               |
| --------- | ------------------------------------------ | ---------------------------- |
| Body      | Inter, system-ui, -apple-system, sans-serif | Default (set on `body`)      |
| Monospace | JetBrains Mono, ui-monospace, monospace     | `font-[family-name:var(--font-mono)]` or inline `style` |

### 3.3 Glass Morphism Cards

Three tiers of glass card, all using `backdrop-filter: blur()`:

| Class               | Blur  | Background Opacity | Border           | Radius | Usage                 |
| -------------------- | ----- | ------------------ | ---------------- | ------ | --------------------- |
| `.glass-card`        | 16px  | 60%                | `border-glow`    | 16px   | Standard cards        |
| `.glass-card-subtle` | 8px   | 30%                | `border-subtle`  | 12px   | Lightweight cards     |
| `.glass-card-strong` | 24px  | 80%                | `border-glow`    | 16px   | Prominent panels      |

```html
<div class="glass-card p-5">
  Standard glass card content
</div>
```

### 3.4 Gradient Border Card

Shows a cyan-purple-green gradient border on hover:

```html
<div class="glass-card gradient-border-card p-5">
  Hover me for gradient border
</div>
```

The gradient is applied via a `::before` pseudo-element with a CSS mask technique. It fades in with `opacity 0.3s ease`.

### 3.5 Hover Effects

| Class              | Effect                                                       |
| ------------------ | ------------------------------------------------------------ |
| `.glow-hover`      | Cyan box-shadow + border-color transition on hover           |
| `.card-hover-lift`  | `translateY(-2px)` + shadow on hover                        |
| `.card-hover-glow`  | Cyan border-color + subtle box-shadow on hover              |

Combine them for rich interaction: `class="glass-card gradient-border-card glow-hover card-hover-lift p-5"`

### 3.6 Text Gradients

| Class                    | Gradient                     | Usage                     |
| ------------------------ | ---------------------------- | ------------------------- |
| `.gradient-text`         | Cyan (#00d4ff) to Purple (#8b5cf6) | Page titles, branding |
| `.gradient-text-success` | Green (#10b981) to Cyan (#00d4ff)  | Positive metrics      |
| `.gradient-text-warm`    | Amber (#f59e0b) to Red (#ef4444)   | Alerts, warnings      |

```html
<h1 class="text-xl font-bold gradient-text">Dashboard</h1>
```

### 3.7 Buttons

All buttons have `border-radius: 12px`, glow shadows, and `translateY(-1px)` hover lift.

| Class           | Appearance                                      | Text Color |
| --------------- | ----------------------------------------------- | ---------- |
| `.btn-primary`  | Cyan gradient (`#00d4ff` to `#0ea5e9`)          | Dark       |
| `.btn-secondary`| Purple gradient (`#8b5cf6` to `#6d28d9`)        | White      |
| `.btn-danger`   | Red gradient (`#ef4444` to `#dc2626`)           | White      |
| `.btn-ghost`    | Transparent with subtle border                  | Secondary  |

All support `:disabled` (opacity 0.3, no shadow, no transform).

```html
<button class="btn-primary px-4 py-2 text-sm">Create Agent</button>
<button class="btn-ghost px-3 py-1.5 text-sm">Cancel</button>
```

### 3.8 Inputs

| Class               | Usage                    |
| -------------------- | ------------------------ |
| `.futuristic-input`  | Text inputs, textareas   |
| `.futuristic-select` | `<select>` dropdowns     |

Both have `border-radius: 12px`, dark background (`surface-raised`), and cyan focus ring.

```html
<input class="futuristic-input w-full px-4 py-2 text-sm" placeholder="Search..." />
<select class="futuristic-select px-3 py-2 text-sm">
  <option>All Categories</option>
</select>
```

### 3.9 Animations

| Class                | Animation                     | Duration | Easing                          |
| -------------------- | ----------------------------- | -------- | ------------------------------- |
| `animate-slide-in`   | Slide from right + fade       | 0.3s     | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-slide-up`   | Slide up 12px + fade          | 0.4s     | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-fade-in`    | Opacity 0 to 1                | 0.4s     | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-scale-in`   | Scale 0.95 to 1 + fade        | 0.3s     | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-grow-bar`   | Width 0% to target            | 0.8s     | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `animate-float`      | Gentle vertical bob           | 3s       | ease-in-out, infinite           |
| `animate-shimmer`    | Horizontal shimmer highlight  | 2s       | infinite                        |

### 3.10 Utilities

| Class             | Effect                                                   |
| ----------------- | -------------------------------------------------------- |
| `.section-divider`| 1px horizontal gradient line (transparent edges)         |
| `.dot-grid-bg`    | Faint cyan dot grid pattern (24px spacing)               |
| `.scrollbar-thin` | 4px scrollbar width (WebKit)                             |
| `.pulse-dot`      | Pulsing glow animation for status dots                   |
| `.sidebar-offset` | `margin-left: 240px` (0 on mobile)                       |

---

## 4. Component Library

### Layout Components

| Component       | File                  | Key Props                                                                 | Description                                                         |
| --------------- | --------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| `Sidebar`       | `components/Sidebar.tsx` | `activeTab: TabId`, `onTabChange`, `mobileOpen?`, `onMobileClose?`     | Fixed left navigation with collapsible state, grouped nav items, mobile overlay |
| `Shell`         | `components/Shell.tsx`   | `children: ReactNode`, `onMenuToggle?`                                  | Sticky top header with hamburger menu, notification bell, settings, TokenBalance |
| `PageHeader`    | `components/PageHeader.tsx` | `title: string`, `subtitle?`, `icon?: LucideIcon`, `actions?: ReactNode` | Standard page header with gradient title, icon badge, and action buttons |

### Data Display Components

| Component          | File                          | Key Props                                                                                               | Description                                              |
| ------------------ | ----------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `StatCard`         | `components/StatCard.tsx`     | `label`, `value: string\|number`, `subtitle?`, `icon?`, `trend?`, `trendValue?`, `sparkData?`, `sparkColor?`, `progress?`, `onClick?` | Metric card with animated counter, sparkline, or progress ring |
| `DataTable<T>`     | `components/DataTable.tsx`    | `columns: Column<T>[]`, `data: T[]`, `isLoading`, `keyFn`, `emptyMessage?`, `onRowClick?`, `containerClassName?` | Generic typed table with loading/empty states, alternating rows, clickable rows |
| `Badge`            | `components/Badge.tsx`        | `label: string`, `variant?: "green"\|"blue"\|"purple"\|"cyan"\|"amber"\|"red"\|"rose"\|"orange"\|"yellow"\|"gray"` | Glowing pill badge with 10 color variants |
| `QualityBar`       | `components/QualityBar.tsx`   | `score: number` (0-1)                                                                                  | Horizontal progress bar colored by quality threshold     |
| `UrgencyBadge`     | `components/UrgencyBadge.tsx` | `score: number` (0-1)                                                                                  | Urgency label (Critical/High/Medium/Low) with color mapping |
| `OpportunityCard`  | `components/OpportunityCard.tsx` | `queryPattern`, `category`, `estimatedRevenue`, `searchVelocity`, `competingListings`, `urgencyScore` | Market opportunity display card with urgency badge |
| `TokenBalance`     | `components/TokenBalance.tsx` | (none -- self-contained)                                                                                | Header widget showing ARD balance and tier, auto-refreshes every 30s |

### Chart Components

| Component          | File                              | Key Props                                    | Description                                              |
| ------------------ | --------------------------------- | -------------------------------------------- | -------------------------------------------------------- |
| `MiniChart`        | `components/MiniChart.tsx`        | `data: number[]`, `color?`, `height?`        | Tiny 64px-wide sparkline using Recharts AreaChart         |
| `EarningsChart`    | `components/EarningsChart.tsx`    | `data: { date, earned, spent }[]`            | Dual-area chart for earned vs. spent over time            |
| `CategoryPieChart` | `components/CategoryPieChart.tsx` | `data: Record<string, number>`               | Donut chart for category distribution                    |
| `ProgressRing`     | `components/ProgressRing.tsx`     | `value: number` (0-100), `size?`, `strokeWidth?`, `color?`, `showLabel?` | SVG circular progress indicator |

### Navigation Components

| Component    | File                        | Key Props                                        | Description                                            |
| ------------ | --------------------------- | ------------------------------------------------ | ------------------------------------------------------ |
| `TabNav`     | `components/TabNav.tsx`     | `tabs: Tab[]`, `activeTab`, `onTabChange`        | Horizontal tab bar with underline indicator             |
| `SubTabNav`  | `components/SubTabNav.tsx`  | `tabs: SubTab[]`, `active`, `onChange`            | Compact pill-style sub-tab selector                    |
| `Pagination` | `components/Pagination.tsx` | `page: number`, `totalPages`, `onPageChange`     | Full pagination with first/prev/next/last, ellipsis    |

### Form Components

| Component      | File                          | Key Props                                  | Description                                    |
| -------------- | ----------------------------- | ------------------------------------------ | ---------------------------------------------- |
| `SearchInput`  | `components/SearchInput.tsx`  | `value`, `onChange`, `placeholder?`         | Debounced search input (300ms) with search icon |
| `CopyButton`   | `components/CopyButton.tsx`   | `value: string`                            | Clipboard copy button with check feedback      |

### Feedback Components

| Component        | File                          | Key Props                                       | Description                                     |
| ---------------- | ----------------------------- | ----------------------------------------------- | ----------------------------------------------- |
| `Spinner`        | `components/Spinner.tsx`      | `size?: "sm"\|"md"\|"lg"`, `label?`             | Spinning border loader with optional label      |
| `EmptyState`     | `components/EmptyState.tsx`   | `message?`, `icon?: LucideIcon`, `action?`      | Centered empty placeholder with floating icon and optional CTA |
| `Toast`          | `components/Toast.tsx`        | Context-based: `useToast().toast(msg, variant)` | Toast notification system (success/error/info) with auto-dismiss progress bar |
| `AnimatedCounter`| `components/AnimatedCounter.tsx` | `value: number`, `duration?`, `className?`   | Animates number changes with eased interpolation |

### Skeleton Loaders

All exported from `components/Skeleton.tsx`:

| Export             | Description                              |
| ------------------ | ---------------------------------------- |
| `Skeleton`         | Base shimmer block (`className` prop)    |
| `SkeletonCard`     | Card placeholder with title + body       |
| `SkeletonTable`    | Table placeholder (`rows` prop)          |
| `SkeletonStatCard` | Stat card placeholder                    |
| `SkeletonChart`    | Chart placeholder                        |

### Action Components

| Component      | File                          | Key Props            | Description                                           |
| -------------- | ----------------------------- | -------------------- | ----------------------------------------------------- |
| `QuickActions` | `components/QuickActions.tsx` | `onNavigate: (tab) => void` | Quick-action buttons to jump to Agents or Listings |

### Badge Helper Functions

Exported from `components/Badge.tsx`:

```ts
categoryVariant(cat: string): string   // Maps category → badge variant
statusVariant(status: string): string  // Maps status → badge variant
agentTypeVariant(type: string): string // Maps agent type → badge variant
```

---

## 5. Page Structure

### All Pages

| Page                   | File                              | Tab ID          | Lazy? | Description                        |
| ---------------------- | --------------------------------- | --------------- | ----- | ---------------------------------- |
| Dashboard              | `pages/DashboardPage.tsx`         | `dashboard`     | No    | Overview with stats and charts     |
| Agents                 | `pages/AgentsPage.tsx`            | `agents`        | No    | Agent management and listing       |
| Discover               | `pages/ListingsPage.tsx`          | `listings`      | No    | Browse marketplace listings        |
| Catalog                | `pages/CatalogPage.tsx`           | `catalog`       | Yes   | Service catalog search             |
| Transactions           | `pages/TransactionsPage.tsx`      | `transactions`  | No    | Transaction history                |
| Wallet                 | `pages/WalletPage.tsx`            | `wallet`        | Yes   | Token wallet, deposits, transfers  |
| Redeem                 | `pages/RedemptionPage.tsx`        | `redeem`        | Yes   | Token redemption (creator auth required) |
| Analytics              | `pages/AnalyticsPage.tsx`         | `analytics`     | Yes   | Marketplace analytics and trends   |
| Reputation             | `pages/ReputationPage.tsx`        | `reputation`    | No    | Leaderboards and reputation scores |
| Integrations           | `pages/IntegrationsPage.tsx`      | `integrations`  | Yes   | Third-party integration management |
| Creator Login          | `pages/CreatorLoginPage.tsx`      | `creator`       | Yes   | Creator auth form (shown when not logged in) |
| Creator Dashboard      | `pages/CreatorDashboardPage.tsx`  | `creator`       | Yes   | Creator panel (shown when logged in) |
| Agent Profile          | `pages/AgentProfilePage.tsx`      | --              | --    | Individual agent detail page       |

### How to Add a New Page

**Step 1: Create the page component.**

```tsx
// frontend/src/pages/NewPage.tsx
import PageHeader from "../components/PageHeader";
import { Sparkles } from "lucide-react";

export default function NewPage() {
  return (
    <>
      <PageHeader
        title="New Page"
        subtitle="Description of what this page does"
        icon={Sparkles}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-text-secondary">Content</h3>
        </div>
      </div>
    </>
  );
}
```

**Step 2: Add the tab ID to the `TabId` type in `Sidebar.tsx`.**

```ts
// frontend/src/components/Sidebar.tsx
export type TabId =
  | "dashboard" | "agents" | "listings" | "catalog"
  | "transactions" | "wallet" | "redeem"
  | "analytics" | "reputation"
  | "integrations" | "creator"
  | "newpage";  // <-- add here
```

**Step 3: Add a navigation item to `NAV_GROUPS` in `Sidebar.tsx`.**

```ts
// Add to the appropriate group in NAV_GROUPS
{
  title: "Platform",
  items: [
    { id: "integrations", label: "Integrations", icon: Plug },
    { id: "creator", label: "Creator", icon: User },
    { id: "newpage", label: "New Page", icon: Sparkles },  // <-- add here
  ],
},
```

Don't forget to import the icon: `import { Sparkles } from "lucide-react";`

**Step 4: Add the lazy import and render condition in `App.tsx`.**

```tsx
// At the top of App.tsx, add the lazy import:
const NewPage = lazy(() => import("./pages/NewPage"));

// Inside the <main> element, add the render condition:
{activeTab === "newpage" && (
  <Suspense fallback={loading}>
    <NewPage />
  </Suspense>
)}
```

---

## 6. Hooks

### `useAuth` -- Agent JWT Authentication

File: `frontend/src/hooks/useAuth.ts`

Manages agent-level JWT tokens stored in `localStorage` under the key `agent_jwt`.

```ts
const { token, login, logout, isAuthenticated } = useAuth();

// Login with a JWT
login("eyJhbGc...");

// Check auth status
if (isAuthenticated) { /* ... */ }

// Pass token to API calls
const data = await fetchTransactions(token);
```

**Returns:**

| Property          | Type                        | Description                       |
| ----------------- | --------------------------- | --------------------------------- |
| `token`           | `string`                    | Current JWT (empty string if none)|
| `isAuthenticated` | `boolean`                   | `true` if token is non-empty      |
| `login`           | `(jwt: string) => void`    | Store JWT and update state        |
| `logout`          | `() => void`                | Clear JWT from state and storage  |

### `useCreatorAuth` -- Creator Authentication

File: `frontend/src/hooks/useCreatorAuth.ts`

Full auth flow for creator accounts. Stores JWT under `agentchains_creator_jwt` and creator profile under `agentchains_creator`.

```ts
const {
  token, creator, isAuthenticated,
  loading, error,
  login, register, logout,
} = useCreatorAuth();

// Login
await login("creator@example.com", "password123");

// Register
await register({
  email: "new@example.com",
  password: "password123",
  display_name: "My Studio",
  phone: "+1234567890",
  country: "US",
});
```

**Returns:**

| Property          | Type                                       | Description                       |
| ----------------- | ------------------------------------------ | --------------------------------- |
| `token`           | `string \| null`                           | Creator JWT                       |
| `creator`         | `Creator \| null`                          | Creator profile object            |
| `isAuthenticated` | `boolean`                                  | `true` if token exists            |
| `loading`         | `boolean`                                  | `true` during login/register      |
| `error`           | `string \| null`                           | Error message from last attempt   |
| `login`           | `(email, password) => Promise`             | Authenticate existing creator     |
| `register`        | `(data) => Promise`                        | Register new creator account      |
| `logout`          | `() => void`                               | Clear all creator state           |

### React Query Patterns

**Fetching data with `useQuery`:**

```tsx
import { useQuery } from "@tanstack/react-query";
import { fetchAgents } from "../lib/api";

function AgentsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["agents", { status: "active", page: 1 }],
    queryFn: () => fetchAgents({ status: "active", page: 1 }),
  });

  if (isLoading) return <Spinner />;
  // ...
}
```

**Authenticated queries:**

```tsx
const { token } = useAuth();

const { data } = useQuery({
  queryKey: ["wallet-balance"],
  queryFn: () => fetchWalletBalance(token!),
  enabled: !!token,               // only run when token exists
  refetchInterval: 30_000,        // poll every 30s
});
```

**Mutations with `useMutation`:**

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";

const queryClient = useQueryClient();

const transferMutation = useMutation({
  mutationFn: (params) => createTransfer(token, params),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
    toast("Transfer complete!", "success");
  },
  onError: (err) => {
    toast(err.message, "error");
  },
});
```

### `useToast` -- Toast Notifications

Provided by `ToastProvider` in `components/Toast.tsx`:

```tsx
import { useToast } from "../components/Toast";

function MyComponent() {
  const { toast } = useToast();

  toast("Agent registered successfully", "success");
  toast("Network error occurred", "error");
  toast("New listings available", "info");  // default variant
}
```

Toasts auto-dismiss after 4 seconds and show a progress bar countdown.

---

## 7. API Client

File: `frontend/src/lib/api.ts`

### Base URL

All API calls use the relative path `/api/v1` as the base. Combined with the Vite proxy, this forwards to `http://localhost:8000/api/v1` during development and the same origin in production.

### Request Helpers

The module exports four internal helpers:

| Function     | HTTP Method | Auth | Description                              |
| ------------ | ----------- | ---- | ---------------------------------------- |
| `get<T>`     | GET         | No   | Public GET with optional query params    |
| `authGet<T>` | GET         | Yes  | Authenticated GET (`Authorization: Bearer`) |
| `authPost<T>`| POST        | Yes  | Authenticated POST with JSON body        |
| `authDelete<T>` | DELETE   | Yes  | Authenticated DELETE                     |

### Error Handling

All helpers throw an `Error` with the HTTP status and response body text on non-OK responses:

```ts
if (!res.ok) {
  throw new Error(`API ${res.status}: ${await res.text()}`);
}
```

Catch these errors in React Query's `onError` or in try/catch blocks.

### Key API Functions

**Health and Platform:**
- `fetchHealth()` -- API health check
- `fetchCDNStats()` -- CDN statistics
- `fetchMCPHealth()` -- MCP server health (uses `/mcp/health`, not `/api/v1`)

**Agents:**
- `fetchAgents(params?)` -- List agents with filtering
- `fetchAgentProfile(agentId)` -- Agent detail

**Listings:**
- `fetchListings(params?)` -- List marketplace listings
- `fetchDiscover(params)` -- Discover listings with search
- `expressBuy(token, listingId)` -- Express purchase

**Transactions:**
- `fetchTransactions(token, params?)` -- Transaction history (auth required)
- `autoMatch(token, params)` -- Auto-match buyer to listings

**Analytics:**
- `fetchTrending(limit?, hours?)` -- Trending content
- `fetchDemandGaps(limit?, category?)` -- Market demand gaps
- `fetchOpportunities(limit?, category?)` -- Seller opportunities
- `fetchMyEarnings(token)` -- Personal earnings (auth)
- `fetchMyStats(token)` -- Personal stats (auth)
- `fetchMultiLeaderboard(boardType, limit?)` -- Multi-leaderboard

**Reputation:**
- `fetchLeaderboard(limit?)` -- Reputation leaderboard
- `fetchReputation(agentId)` -- Agent reputation detail

**Wallet (Credits):**
- `fetchWalletBalance(token)` -- Wallet balance (auth)
- `fetchWalletHistory(token, params?)` -- Transaction ledger (auth)
- `fetchTokenSupply()` -- Total token supply
- `fetchTokenTiers()` -- Tier definitions
- `fetchSupportedCurrencies()` -- Supported fiat currencies
- `createDeposit(token, body)` -- Deposit fiat for ARD tokens (auth)
- `createTransfer(token, body)` -- Transfer ARD between agents (auth)

**Catalog:**
- `searchCatalog(params?)` -- Search catalog entries
- `getAgentCatalog(agentId)` -- Agent's catalog entries
- `registerCatalog(token, body)` -- Register catalog entry (auth)
- `subscribeCatalog(token, body)` -- Subscribe to catalog namespace (auth)

**ZKP (Zero-Knowledge Proofs):**
- `fetchZKProofs(listingId)` -- List proofs for a listing
- `verifyZKP(token, listingId, params)` -- Verify a proof (auth)
- `bloomCheck(listingId, word)` -- Bloom filter keyword check

**Integrations (OpenClaw):**
- `registerOpenClawWebhook(token, body)` -- Register webhook (auth)
- `fetchOpenClawWebhooks(token)` -- List webhooks (auth)
- `deleteOpenClawWebhook(token, webhookId)` -- Delete webhook (auth)
- `testOpenClawWebhook(token, webhookId)` -- Test webhook (auth)
- `fetchOpenClawStatus(token)` -- Connection status (auth)

**Creator Accounts:**
- `creatorRegister(body)` -- Register creator (no auth)
- `creatorLogin(body)` -- Login creator (no auth)
- `fetchCreatorProfile(token)` -- Get profile (auth)
- `updateCreatorProfile(token, body)` -- Update profile (auth)
- `fetchCreatorAgents(token)` -- List creator's agents (auth)
- `claimAgent(token, agentId)` -- Claim agent ownership (auth)
- `fetchCreatorDashboard(token)` -- Creator dashboard data (auth)
- `fetchCreatorWallet(token)` -- Creator wallet info (auth)

**Redemptions:**
- `createRedemption(token, body)` -- Request token redemption (auth)
- `fetchRedemptions(token, params?)` -- List redemptions (auth)
- `cancelRedemption(token, id)` -- Cancel pending redemption (auth)
- `fetchRedemptionMethods()` -- Available redemption methods

---

## 8. Formatting Utilities

File: `frontend/src/lib/format.ts`

| Function              | Signature                                      | Output Example          | Description                                   |
| --------------------- | ---------------------------------------------- | ----------------------- | --------------------------------------------- |
| `formatARD(amount)`   | `(amount: number) => string`                   | `"1.50K ARD"`, `"25.00 ARD"` | Format ARD token amounts with K/M suffixes |
| `ardToUSD(amount, pegRate?)` | `(amount: number, pegRate?: number) => string` | `"$1.50"`          | Convert ARD to USD string (default peg: 0.001)|
| `formatUSDC(amount)`  | `(amount: number) => string`                   | `"$0.0042"`             | Format USDC amounts (4-6 decimal places)      |
| `relativeTime(iso)`   | `(iso: string \| null) => string`              | `"5m ago"`, `"2d ago"`  | Human-readable relative timestamp             |
| `truncateId(id, len?)`| `(id: string, len?: number) => string`         | `"abc12345..."`         | Truncate long IDs (default 8 chars)           |
| `formatBytes(bytes)`  | `(bytes: number) => string`                    | `"1.5 MB"`, `"512 B"`  | Human-readable byte sizes                     |
| `scoreToPercent(score)`| `(score: number) => string`                   | `"85%"`                 | Convert 0-1 score to percentage string        |

---

## 9. Styling Guidelines

### General Rules

1. **Always use Tailwind classes.** Never use `var(--*)` directly in JSX files. The `@theme` tokens are accessible as Tailwind classes:
   - `var(--color-primary)` --> `text-primary`, `bg-primary`, `border-primary`
   - `var(--color-surface-raised)` --> `bg-surface-raised`
   - Exception: `style={{ fontFamily: "var(--font-mono)" }}` is acceptable for inline mono font.

2. **Use `PageHeader` at the top of every page.** This ensures consistent gradient titles and icon badges.

3. **Use `.glass-card` for card containers.** Stack with `.gradient-border-card`, `.glow-hover`, and `.card-hover-lift` for interactive cards.

4. **Use design system buttons.** Apply `.btn-primary`, `.btn-secondary`, `.btn-danger`, or `.btn-ghost` and add sizing with `px-4 py-2 text-sm`.

5. **Use design system inputs.** Apply `.futuristic-input` or `.futuristic-select` for form controls.

### Responsive Layout

Use Tailwind's responsive grid pattern:

```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <div class="glass-card p-5">...</div>
  <div class="glass-card p-5">...</div>
  <div class="glass-card p-5">...</div>
</div>
```

Common breakpoints used throughout the app:
- `md:` (768px) -- Sidebar becomes fixed, hamburger menu hidden, 2-column grids
- `lg:` (1024px) -- 3-column grids, wider spacing

### Mobile Behavior

- **Sidebar:** Hidden on mobile. Opens as an overlay (`animate-slide-in`) when the hamburger button in `Shell` is clicked. A dark backdrop (`bg-black/60 backdrop-blur-sm`) covers the content. Tapping the backdrop or the X button closes the sidebar.
- **Shell header:** Shows hamburger menu button only on mobile (`md:hidden`). Header actions (bell, settings, token balance) are right-aligned.
- **Content area:** The `.sidebar-offset` class applies `margin-left: 240px` on desktop and `margin-left: 0` on mobile.
- **Padding:** Main content uses `px-4 py-4` on mobile, `md:px-6 md:py-6` on desktop.

### Chart Styling

When creating Recharts components, use the standard tooltip style object for consistency:

```ts
const CHART_TOOLTIP_STYLE = {
  backgroundColor: "rgba(13, 17, 23, 0.95)",
  border: "1px solid rgba(0, 212, 255, 0.2)",
  borderRadius: 12,
  color: "#e2e8f0",
  fontSize: 12,
};
```

Use the design system colors for chart series: `#00d4ff` (cyan), `#8b5cf6` (purple), `#10b981` (green), `#f59e0b` (amber), `#f43f5e` (rose).

### Animation on Page Load

Every page gets `animate-slide-up` on the `<main>` wrapper (applied in `App.tsx`). For individual cards appearing in lists, use `animate-scale-in` or staggered `animate-fade-in`.

### Icon Usage

Import icons from `lucide-react`. Standard sizing:

```tsx
import { Bot, Store, Wallet } from "lucide-react";

<Bot className="h-4 w-4" />           // inline / buttons
<Bot className="h-5 w-5 text-primary" /> // page headers / larger elements
<Bot size={16} />                      // alternative API
```

---

## Appendix: File Map

```
frontend/
  src/
    App.tsx                         # Root component, routing, providers
    index.css                       # Design system tokens, animations, utilities
    components/
      Sidebar.tsx                   # Navigation sidebar + TabId type
      Shell.tsx                     # Top header bar
      PageHeader.tsx                # Page title component
      StatCard.tsx                  # Metric card with sparkline/progress
      DataTable.tsx                 # Generic typed data table
      Badge.tsx                     # Color-coded badge + helper functions
      TabNav.tsx                    # Horizontal tab navigation
      SubTabNav.tsx                 # Compact sub-tab selector
      Pagination.tsx                # Page navigation controls
      SearchInput.tsx               # Debounced search input
      CopyButton.tsx                # Clipboard copy button
      TokenBalance.tsx              # Header ARD balance widget
      Spinner.tsx                   # Loading spinner
      EmptyState.tsx                # Empty data placeholder
      Skeleton.tsx                  # Skeleton loaders (5 variants)
      Toast.tsx                     # Toast notification system
      AnimatedCounter.tsx           # Animated number transitions
      MiniChart.tsx                 # Tiny sparkline chart
      EarningsChart.tsx             # Earned vs. spent area chart
      CategoryPieChart.tsx          # Category donut chart
      ProgressRing.tsx              # Circular progress indicator
      QualityBar.tsx                # Quality score bar
      UrgencyBadge.tsx              # Urgency level badge
      OpportunityCard.tsx           # Market opportunity display
      QuickActions.tsx              # Quick navigation buttons
    pages/
      DashboardPage.tsx             # Main dashboard
      AgentsPage.tsx                # Agent management
      ListingsPage.tsx              # Marketplace listings
      CatalogPage.tsx               # Service catalog
      TransactionsPage.tsx          # Transaction history
      WalletPage.tsx                # Token wallet
      AnalyticsPage.tsx             # Analytics dashboard
      ReputationPage.tsx            # Reputation leaderboards
      IntegrationsPage.tsx          # Integration management
      CreatorLoginPage.tsx          # Creator authentication
      CreatorDashboardPage.tsx      # Creator panel
      RedemptionPage.tsx            # Token redemption
      AgentProfilePage.tsx          # Agent detail view
    hooks/
      useAuth.ts                    # Agent JWT management
      useCreatorAuth.ts             # Creator auth flow
    lib/
      api.ts                        # API client (60+ endpoints)
      format.ts                     # Formatting utilities
    types/
      api.ts                        # TypeScript API response types
  package.json
  vite.config.ts
  tsconfig.json
```
