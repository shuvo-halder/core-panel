# Frontend Architecture (Next.js / React / TypeScript)

## 1. Overview

The UI layer is built with **Next.js (App Router)**, **React**, **TypeScript**, **Tailwind CSS**, and **shadcn/ui**. It provides a compact, responsive, high-density server control interface with real-time feedback.

---

## 2. Key Technology Choices

- **Next.js App Router:** Hybrid rendering using Server Components for static/fast layouts and Client Components for interactive controls.
- **TanStack Query (React Query v5):** Server state caching, optimistic updates, automatic refetching, and polling intervals for system metrics.
- **Zod & React Hook Form:** Client-side type validation matching backend Pydantic schemas.
- **shadcn/ui & Lucide Icons:** Accessible, clean component primitives styled with Tailwind CSS.
- **xterm.js:** Lightweight terminal emulator loaded on-demand for WebSSH sessions.
- **Recharts / Canvas:** Lightweight, code-split monitoring visualization.

---

## 3. UI Directory Structure

```
apps/web/
├── app/
│   ├── (auth)/
│   │   └── login/page.tsx
│   ├── (dashboard)/
│   │   ├── page.tsx                  # Server Metrics & Overview
│   │   ├── websites/
│   │   ├── databases/
│   │   ├── files/
│   │   ├── terminal/
│   │   ├── tasks/
│   │   └── settings/
│   └── layout.tsx
├── components/
│   ├── ui/                           # shadcn base primitives
│   ├── dashboard/                    # Overview widgets & resource gauges
│   ├── terminal/                     # Lazy-loaded xterm.js wrapper
│   ├── files/                        # File Manager explorer & editor
│   └── common/                       # Navigation, drawers, task progress banner
├── lib/
│   ├── api.ts                        # Axios/Fetch client with CSRF & auth handling
│   ├── query-client.ts               # TanStack query client configuration
│   └── sse.ts                        # SSE connection hooks
└── store/                            # Minimal Zustand stores (e.g. sidebar toggle)
```

---

## 4. Performance & Load Minimization

1. **Lazy Loading Heavy Modules:** `xterm.js`, code editor, and chart libraries are dynamically imported (`next/dynamic` / React `lazy`) and only loaded when navigating to those respective views.
2. **Paginated & Virtualized Tables:** File lists, audit logs, and process tables render with virtual scrolling for large file or process sets.
3. **Payload Optimization:** System metrics APIs return lightweight JSON schemas with compact floats and arrays.
