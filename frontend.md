# DEO RAG — Frontend Design Guide

> Single source of truth for the DEO RAG frontend UI. All future agents must read this before making any frontend changes.

---

## 1. Overview

**Product:** DEO RAG — Defence Estates Office AI Document Assistant  
**Stack:** React 18 + Vite, Vanilla CSS (App.css), ReactMarkdown  
**Source:** `deo-rag/frontend/src/App.jsx` + `deo-rag/frontend/src/App.css`  
**Build:** `cd deo-rag/frontend && npm run build`

---

## 2. Design Language

The DEO RAG frontend is part of a **3-app family** (GovOCR, DEM Portal, DEO RAG). All three share:
- **Indian government identity** — tricolor strip, India Emblem, saffron accent
- **Inter font** from Google Fonts
- **Glassmorphism dark panels** — `backdrop-filter: blur()`, semi-transparent backgrounds
- **Deep navy dark background** — `#060c18` for dark, `#edf3f8` for light
- **Shared vocabulary** — same border radii range (11–22px), same spacing rhythm

---

## 3. Indian Government Identity

### 3.1 Tricolor Strip
A **3px fixed banner at the very top** of the viewport showing the Indian flag tricolor:
```css
.tricolor-strip {
  height: 3px;
  background: linear-gradient(90deg,
    #FF9933 0%, #FF9933 33.33%,
    #ffffff 33.33%, #ffffff 66.66%,
    #138808 66.66%, #138808 100%
  );
  position: fixed; top: 0; left: 0; right: 0; z-index: 2000;
}
```
Body has `padding-top: 3px` to compensate. Sidebar has `top: 3px` sticky positioning.

### 3.2 India Emblem
The **Government of India Emblem** (Ashoka Lions) is displayed in the sidebar brand block:
```jsx
<img
  src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg"
  alt="Emblem of India"
  className="brand-logo-img india-emblem-img"
/>
```
In dark mode, the emblem is white (via CSS filter):
```css
[data-theme='dark'] .india-emblem-img {
  filter: brightness(0) invert(1) opacity(0.88);
}
```

### 3.3 Saffron Primary Color
- **Dark mode primary:** `#FF9933` (Indian saffron — flag color)
- **Light mode primary:** `#b35900` (darker saffron for readable contrast on light bg)
- Used for: active nav border, primary buttons, focus rings, heading gradient, scrollbar
- Brand kicker text (`DEO RAG Console`) is saffron in dark mode

### 3.4 Indian Flag Green (Success/Progress)
- `--flag-green: #138808` (Indian flag green)
- Used for: success states, "current file" progress bar gradient

---

## 4. Layout Structure

```
[3px tricolor strip — fixed at top]
┌─────────────────────────────────────────────────┐
│ SIDEBAR (300px sticky)  │  WORKSPACE (flex-grow) │
│                         │                        │
│  [India Emblem] DEO     │  TOPBAR                │
│  RAG Console            │  (eyebrow + h2 + btns) │
│                         │                        │
│  System Status cards    │  OVERVIEW GRID (4-up)  │
│                         │                        │
│  NAV LINKS              │  PANELS:               │
│  (with saffron border   │  - Data Libraries      │
│   on active item)       │  - Documents           │
│                         │  - Ingest              │
│  Sidebar Footer         │  - Chat                │
│                         │  - Settings            │
│                         │  - Hardware            │
└─────────────────────────┴────────────────────────┘
```

**CSS class:** `.app-shell { display: grid; grid-template-columns: 300px minmax(0, 1fr); }`

---

## 5. CSS Variable System

All colors MUST use CSS variables. Never hardcode colors outside the variable declarations at top.

### Dark Theme (`[data-theme='dark']` — default)

| Variable | Value | Usage |
|---|---|---|
| `--bg` | `#060c18` | Page background |
| `--surface` | `rgba(8, 14, 28, 0.82)` | Card backgrounds |
| `--surface-strong` | `#0d1827` | Input backgrounds, strong cards |
| `--surface-muted` | `#111f33` | Subtle backgrounds |
| `--surface-subtle` | `#162438` | Progress track bg |
| `--border` | `rgba(148, 163, 184, 0.1)` | All borders |
| `--text` | `#e2eaf5` | Primary text |
| `--muted` | `#7a95b5` | Secondary/muted text |
| `--primary` | `#FF9933` | Saffron — buttons, active states |
| `--primary-strong` | `#e67e00` | Darker saffron for gradients |
| `--primary-glow` | `rgba(255, 153, 51, 0.22)` | Button glow shadows |
| `--success` | `#4ade80` | Success states |
| `--success-soft` | `rgba(22, 163, 74, 0.16)` | Success badge bg |
| `--danger` | `#fb7185` | Error/danger |
| `--danger-soft` | `rgba(190, 24, 93, 0.16)` | Danger badge bg |
| `--shadow` | `0 24px 60px rgba(0,0,0,0.35)` | Panel shadows |
| `--shadow-soft` | `0 12px 36px rgba(0,0,0,0.22)` | Card shadows |

### Light Theme (`:root`)

| Variable | Value |
|---|---|
| `--bg` | `#edf3f8` |
| `--surface` | `rgba(255, 255, 255, 0.88)` |
| `--surface-strong` | `#ffffff` |
| `--primary` | `#b35900` (darker saffron) |
| `--text` | `#0f172a` |
| `--muted` | `#667085` |

---

## 6. Component Classes

### Panels
```css
.panel { border-radius: 20px; backdrop-filter: blur(18px); }
/* dark mode adds: border-top: 1px solid rgba(255,153,51,0.1) */
```

### Buttons
- `.primary-button` — saffron gradient, white text, glow shadow
- `.secondary-button` / `.ghost-button` — surface bg, border, hover turns saffron
- `.danger-button` — red gradient

### Navigation
- `.nav-link.active` — saffron left border (`border-left: 3px solid var(--saffron)`)
- Dark mode active nav has `background: rgba(255, 153, 51, 0.07)`

### Health Pills
- `.health-online` — uses `--success-soft` / `--success` (NO hardcoded green)
- `.health-degraded` — uses `--warning-soft` / `--warning`
- `.health-offline` / `.health-unknown` — uses `--danger-soft` / `--danger`

### Progress Bars
- Overall progress: saffron gradient (`var(--primary)` → `var(--primary-strong)`)
- Current file: flag green gradient (`var(--flag-green)` → `#22c55e`)

---

## 7. Typography

- **Font:** Inter (loaded from Google Fonts in `index.html`)
- **Heading gradient (dark mode):** `linear-gradient(135deg, var(--text) 50%, var(--saffron) 100%)`
- Brand kicker uppercase, `letter-spacing: 0.11em`, saffron in dark

---

## 8. Theming

Theme is stored in `localStorage` as `'deo-rag-theme'` (`'dark'` or `'light'`).  
Default: `'dark'`. Toggle button is in the topbar.  
The `index.html` inline script applies the theme class before React loads to prevent FOUC.

---

## 9. Known Fixed Issues (May 2026)

- **White backgrounds in dark mode** — Fixed by removing all hardcoded light colors. All backgrounds now use CSS variables.
- **Status box blue bg** — Was `#eef2ff` hardcoded. Now `var(--surface)`.
- **Settings grid white** — Was `background: #fff`. Now `var(--surface-strong)`.
- **File progress items white** — Was `background: #fff`. Now `var(--surface-strong)`.
- **Health pills** — Were hardcoded light green/yellow/red. Now use CSS variables.
- **Warning box** — Was hardcoded `#fee2e2`. Now `var(--danger-soft)`.
- **Markdown text colors** — Were hardcoded `#374151`. Now `var(--text)`.
- **Overflow in ingest panel** — Resolved by `panel-grid.two-up` using `minmax(0, 1fr)`.
- **Document list overflow** — Added `max-height: 260px; overflow-y: auto`.

---

## 10. Sibling Apps (Reference Design)

| App | Accent | Background | Special |
|---|---|---|---|
| **GovOCR** | Violet `#8b5cf6` + Cyan `#06b6d4` | `#0f0f1a → #16213e` | DaisyUI/Tailwind, Vue |
| **DEM Portal** | Blue `#3b82f6` + Green `#10b981` | `#0a0e1a` | Vanilla CSS, tricolor strip, India Emblem |
| **DEO RAG** | Saffron `#FF9933` (dark) / `#b35900` (light) | `#060c18` | React/Vite, tricolor strip, India Emblem |

All three use:
- Inter font
- `backdrop-filter: blur()` glassmorphism
- 3px Indian tricolor strip at top
- India Emblem (Ashoka Lions) SVG from Wikimedia

---

## 11. Adding New Sections / Features

1. Add nav item to `NAV_ITEMS` array in `App.jsx`
2. Add `<section id="your-id" className="panel panel-wide">` in workspace
3. Use `.panel-header`, `.panel-grid.two-up`, `.stack-form` for layout
4. Use `.primary-button` / `.secondary-button` / `.danger-button` for actions
5. Use CSS variables for ALL colors — never hardcode
6. Test in both dark and light mode

---

## 12. Build & Dev

```bash
cd deo-rag/frontend
npm install        # first time
npm run dev        # dev server
npm run build      # production build to dist/
```

The built `dist/` is served by the Flask backend in production.
