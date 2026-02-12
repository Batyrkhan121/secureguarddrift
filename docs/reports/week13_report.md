# Week 13 QA Report — React + TypeScript Frontend

**Date:** 2026-02-12
**Engineer:** QA Review
**Python Tests:** 372 passed, 0 failed
**TypeScript:** 0 errors (`tsc --noEmit`)
**Vite Build:** Success (709KB JS, 12KB CSS)

---

## 1. Build

| Check | Status | Comment |
|-------|--------|---------|
| `npm install` → 0 errors | OK | All dependencies install cleanly |
| `npm run build` → dist/ created | OK | `dist/index.html`, `dist/assets/index-*.js` (709KB), `dist/assets/index-*.css` (12KB) |
| TypeScript: 0 errors | OK | `tsc --noEmit` passes with strict mode |
| Vite dev server starts | OK | Port 3000, API proxy to localhost:8000 |

## 2. Types

| Check | Status | Comment |
|-------|--------|---------|
| All API entities have interfaces | OK | Node, Edge, Snapshot, SnapshotSummary, DriftEvent, DriftSummary, PolicySuggestion, FeedbackStats, WhitelistEntry, Baseline, User, AuthResponse, HealthResponse — 13 interfaces |
| Types match API responses | OK | Fields match backend JSON output (verified against api/routes/*.py) |
| No `any` types | OK | Zero usage of `any` across all source files |
| Strict mode enabled | OK | `tsconfig.json` has `"strict": true` |

## 3. API Client

| Check | Status | Comment |
|-------|--------|---------|
| Auth interceptor adds token | OK | Reads `sg_token` from localStorage, adds `Authorization: Bearer` header |
| 401 → redirect to login | OK | Response interceptor removes token + redirects to `/login` |
| React Query hooks defined | OK | `useHealth`, `useSnapshots`, `useGraph`, `useDrift`, `useDriftSummary`, `usePolicies`, `useWhitelist`, `useFeedbackStats` |
| Stale times configured | OK | Graph: 30s, Drift: 10s, Policies: 60s, Health: 30s |
| Loading states handled | OK | React Query provides `isLoading`/`isError` used in components |
| API URLs match backend routes | OK | **FIXED** — 9 URL mismatches corrected (see Fixes section) |

## 4. Components

| Check | Status | Comment |
|-------|--------|---------|
| Header.tsx | OK | Logo, snapshot selectors, analyze/export buttons, user menu with logout |
| SummaryBar.tsx | OK | Fixed bottom bar with severity counts (critical/high/medium/low) + policy count |
| ServiceGraph.tsx | OK | Cytoscape wrapper with cose layout, severity highlighting, node/edge click handlers |
| NodePopup.tsx | OK | Positioned popup with node details, incoming/outgoing edges, related drift events, Esc to close |
| EdgePopup.tsx | OK | Edge metrics display with severity badges, static class mapping for Tailwind |
| DriftCard.tsx | OK | Severity-colored left border, expandable body, feedback buttons (👍👎⏭), risk score badge |
| DriftFeed.tsx | OK | List of DriftCards, accordion behavior, "No drift events" empty state |
| LoginPage.tsx | OK | Email + password form, error display, dark theme, submit calls authStore.login() |
| ProtectedRoute.tsx | OK | Redirects to `/login` if not authenticated, shows "Access Denied" for wrong role |

## 5. Pages

| Check | Status | Comment |
|-------|--------|---------|
| DashboardPage | OK | Layout: Header + Graph (2/3) + Sidebar (1/3) + SummaryBar. Tabs: Drift Feed / Policies |
| SettingsPage | OK | Integration settings (Slack/Jira/SIEM/GitOps) + whitelist management, admin/operator only |
| LoginPage | OK | Form with email/password, error handling, navigate to `/` on success |
| Protected routes | OK | Settings requires `operator` role, Dashboard requires any auth, login is public |

## 6. Interactions

| Check | Status | Comment |
|-------|--------|---------|
| Click card → highlight edge | OK | `DriftCard` `onMouseEnter`/click triggers `highlightEdge` in DashboardPage |
| Hover on card → highlight edge | OK | `onMouseEnter` on DriftCard calls `setHighlightedEdge` state |
| Click node → popup | OK | `onNodeClick` in ServiceGraph sets `selectedNode` state, shows NodePopup |
| Click edge → popup | OK | `onEdgeClick` sets `selectedEdge`, shows EdgePopup |
| Esc → close popups | OK | `useEffect` with `keydown` listener for Escape key |
| Analyze → reload drift | OK | Calls `queryClient.invalidateQueries({ queryKey: ["drift"] })` with error handling |

## 7. Styles

| Check | Status | Comment |
|-------|--------|---------|
| Dark theme | OK | `bg-gray-900`, `text-white` defaults, dark card/header backgrounds |
| Severity colors | OK | Critical: red-500, High: orange-500, Medium: yellow-500, Low: blue-500 — matches backend |
| Custom entity colors | OK | Tailwind config defines `svc`, `db`, `gw` colors for graph nodes |
| Custom scrollbar | OK | `index.css` defines thin dark scrollbar styling |
| Responsive layout | OK | Flexbox layout with grid, works desktop + tablet |

## 8. Backend Compatibility

| Check | Status | Comment |
|-------|--------|---------|
| API URLs match endpoints | OK | All 14 API functions use correct backend URLs (after fixes) |
| JSON format compatible | OK | TypeScript interfaces match backend response structures |
| Auth flow end-to-end | OK | `POST /api/auth/login` → JWT token → stored in localStorage → sent in headers |
| Static serving | OK | `api/server.py` mounts `frontend/dist` at `/app` when directory exists |
| WebSocket URL | OK | Vite proxy routes `/ws` → `ws://localhost:8000` |

---

## Fixes Applied

### Critical: 9 API URL Mismatches Fixed in `client.ts`

| Function | Before (Wrong) | After (Correct) | Backend Route |
|----------|---------------|-----------------|---------------|
| `getSnapshots` | `/graph/snapshots` | `/snapshots` | `GET /api/snapshots` (server.py) |
| `getPolicies` | `/policy/` | `/policies/` | `GET /api/policies/` |
| `approvePolicy` | `/policy/{id}/approve` | `/policies/{id}/approve` | `POST /api/policies/{id}/approve` |
| `rejectPolicy` | `/policy/{id}/reject` | `/policies/{id}/reject` | `POST /api/policies/{id}/reject` |
| `postFeedback` | `/ml/feedback` | `/feedback` | `POST /api/feedback` |
| `getFeedbackStats` | `/ml/feedback/stats` | `/feedback/stats/async` | `GET /api/feedback/stats/async` |
| `getWhitelist` | `/ml/whitelist` | `/whitelist` | `GET /api/whitelist` |
| `addWhitelist` | `/ml/whitelist` | `/whitelist` | `POST /api/whitelist` |
| `removeWhitelist` | `DELETE /ml/whitelist` (body) | `DELETE /whitelist/{src}/{dst}` (path params) | `DELETE /api/whitelist/{source}/{destination}` |
| `getBaseline` | `/ml/baseline/{s}/{d}` | `/baseline/{s}/{d}` | `GET /api/baseline/{source}/{destination}` |

---

## Summary

| Section | Checks | Passed | Failed |
|---------|--------|--------|--------|
| Build | 4 | 4 | 0 |
| Types | 4 | 4 | 0 |
| API Client | 6 | 6 | 0 |
| Components | 9 | 9 | 0 |
| Pages | 4 | 4 | 0 |
| Interactions | 6 | 6 | 0 |
| Styles | 5 | 5 | 0 |
| Backend Compat | 5 | 5 | 0 |
| **Total** | **43** | **43** | **0** |

**Verdict: PASS** — All 43 QA checks passed. 9 critical API URL mismatches were fixed.
