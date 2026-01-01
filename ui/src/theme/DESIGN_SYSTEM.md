# SentinAI Design System

> Enterprise-grade design system for the SentinAI Exception Processing Platform.
> Inspired by Base44-quality SaaS platforms with a focus on clarity, calm, and professionalism.

---

## Quick Start

```tsx
// In main.tsx - import global CSS variables
import "@/theme/globalStyles.css";

// In components - import tokens
import { colors, typography, spacing, componentStyles } from "@/theme";
```

---

## Design Principles

1. **Clean & Professional** — No visual noise, deliberate whitespace
2. **Scannable** — Clear hierarchy, users find info instantly
3. **Calm & Confident** — Muted colors, no alarms unless critical
4. **Consistent** — Same patterns everywhere, zero surprises
5. **Accessible** — WCAG 2.1 AA compliant contrast ratios

---

## Typography System

### Font Family

**Primary:** Inter (with system fallbacks)

```css
--font-family-primary: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
  sans-serif;
```

**Monospace:** JetBrains Mono (for IDs, code)

```css
--font-family-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;
```

### Type Scale

| Token          | Size | Weight   | Use Case                   |
| -------------- | ---- | -------- | -------------------------- |
| `pageTitle`    | 28px | Bold     | Page headers               |
| `sectionTitle` | 18px | Semibold | Section dividers           |
| `cardTitle`    | 15px | Semibold | Card headers               |
| `tableHeader`  | 13px | Semibold | Table column labels        |
| `body`         | 14px | Regular  | Main content               |
| `bodySmall`    | 13px | Regular  | Dense content, table cells |
| `caption`      | 12px | Medium   | Labels, tags               |
| `metadata`     | 12px | Regular  | Timestamps, IDs            |
| `kpiLarge`     | 48px | Bold     | Hero metrics               |
| `kpiMedium`    | 36px | Bold     | Dashboard KPIs             |
| `kpiSmall`     | 24px | Bold     | Compact metrics            |

### Usage Examples

```tsx
// In MUI sx prop
<Typography sx={{ ...typography.pageTitle }}>
  Operations Center
</Typography>

// With CSS variables
<h1 className="text-page-title">Operations Center</h1>
```

---

## Spacing System

### Base Grid: 8px

All spacing is based on an 8px grid for visual harmony.

### Scale

| Token | Value   | Pixels | Use Case                 |
| ----- | ------- | ------ | ------------------------ |
| `1`   | 0.25rem | 4px    | Micro: icon-to-text      |
| `2`   | 0.5rem  | 8px    | Small: related elements  |
| `3`   | 0.75rem | 12px   | Compact: dense UI        |
| `4`   | 1rem    | 16px   | Medium: standard gaps    |
| `5`   | 1.25rem | 20px   | Card padding             |
| `6`   | 1.5rem  | 24px   | Page padding, large gaps |
| `8`   | 2rem    | 32px   | Section separators       |
| `10`  | 2.5rem  | 40px   | Major breaks             |

### Layout Spacing Presets

```tsx
import { layoutSpacing } from "@/theme";

// Page layout
const page = {
  maxWidth: layoutSpacing.pageMaxWidth, // 1280px
  paddingX: layoutSpacing.pagePaddingX, // 24px
  paddingY: layoutSpacing.pagePaddingY, // 24px
};

// Section spacing
const sections = {
  headerToContent: layoutSpacing.headerToContent, // 24px
  betweenSections: layoutSpacing.betweenSections, // 32px
};

// Card spacing
const card = {
  padding: layoutSpacing.cardPadding, // 20px
  titleGap: layoutSpacing.cardTitleToContent, // 16px
};

// Grid gaps
const grid = {
  statCards: layoutSpacing.gridGapMd, // 16px
  contentCards: layoutSpacing.gridGapLg, // 24px
};

// Table
const table = {
  rowHeight: layoutSpacing.tableRowHeight, // 44px
  cellPaddingX: layoutSpacing.tableCellPaddingX, // 16px
};
```

---

## Color System

### Philosophy

> 90% of the UI should be grayscale. Use semantic colors sparingly.
> Colors should inform, not alarm.

### Brand Colors

```css
--color-brand-primary: #2563eb; /* Main blue - buttons, links */
--color-brand-primary-hover: #1d4ed8; /* Darker on hover */
--color-brand-primary-light: #eff6ff; /* Backgrounds, selections */
```

**Use for:** Primary buttons, active nav items, links, focus rings, selected states

**Never use for:** Large backgrounds, decorative purposes

### Background Layers

| Layer        | Color       | Hex       | Use              |
| ------------ | ----------- | --------- | ---------------- |
| App          | Light gray  | `#f8fafc` | Page background  |
| Card         | White       | `#ffffff` | Cards, surfaces  |
| Table header | Subtle tint | `#f9fafb` | Table header row |
| Hover        | Gray 100    | `#f3f4f6` | Hover states     |
| Selected     | Blue tint   | `#eff6ff` | Selected rows    |

### Text Colors

| Token         | Hex       | Contrast | Use             |
| ------------- | --------- | -------- | --------------- |
| `primary`     | `#111827` | High     | Main text       |
| `secondary`   | `#4b5563` | Medium   | Secondary info  |
| `muted`       | `#6b7280` | Lower    | Metadata, hints |
| `placeholder` | `#9ca3af` | Low      | Placeholders    |
| `link`        | `#2563eb` | High     | Clickable text  |

### Semantic Colors (Badges Only!)

These are **muted** for enterprise calm. Use only in badges/indicators.

| Severity | Background | Border    | Text      |
| -------- | ---------- | --------- | --------- |
| Critical | `#fef2f2`  | `#fca5a5` | `#b91c1c` |
| High     | `#fffbeb`  | `#fcd34d` | `#b45309` |
| Medium   | `#eff6ff`  | `#93c5fd` | `#1d4ed8` |
| Low      | `#f9fafb`  | `#e5e7eb` | `#4b5563` |

```tsx
import { colors } from "@/theme";

// Severity badge
const criticalBadge = {
  backgroundColor: colors.severity.critical.bg,
  borderColor: colors.severity.critical.border,
  color: colors.severity.critical.text,
};
```

---

## Elevation & Radius

### Philosophy

> Use **borders** for cards, **shadows** for floating elements.

### When to Use Shadow

- Dropdowns/popovers (elevated above content)
- Modals (clearly above page)
- Tooltips
- Floating action buttons

### When to Use Border

- Cards on page (default)
- Tables
- Form inputs
- Most UI containers

### Border Radius Scale

| Token  | Value  | Use                     |
| ------ | ------ | ----------------------- |
| `sm`   | 4px    | Buttons, inputs, badges |
| `md`   | 6px    | Chips, small containers |
| `lg`   | 8px    | Cards, modals           |
| `xl`   | 12px   | Large cards, panels     |
| `full` | 9999px | Pills, avatars          |

### Pre-built Elevation Presets

```tsx
import { elevation } from "@/theme";

// Card (border, no shadow)
elevation.card = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  shadow: "none",
};

// Dropdown (border + shadow)
elevation.dropdown = {
  border: "1px solid #e5e7eb",
  borderRadius: "8px",
  shadow: "0 4px 6px -1px rgba(0,0,0,0.1)",
};
```

---

## CSS Variables

All tokens are available as CSS custom properties. Import in your app:

```tsx
// main.tsx
import "@/theme/globalStyles.css";
```

Then use anywhere:

```css
.my-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  padding: var(--layout-card-padding);
}

.my-title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}
```

---

## Pre-built Component Styles

Use these with MUI's `sx` prop:

```tsx
import { componentStyles } from '@/theme';

// Page container
<Box sx={componentStyles.pageContainer}>

// Card
<Paper sx={componentStyles.card}>

// Card with hover effect
<Paper sx={componentStyles.cardHoverable}>

// Table container
<TableContainer sx={componentStyles.tableContainer}>

// Table header cell
<TableCell sx={componentStyles.tableHeaderCell}>

// Primary button
<Button sx={componentStyles.buttonPrimary}>

// Secondary button
<Button sx={componentStyles.buttonSecondary}>

// Input field
<TextField sx={{ '& .MuiInputBase-root': componentStyles.input }}>

// Muted timestamp
<Typography sx={componentStyles.timestamp}>2 hours ago</Typography>

// Monospace ID
<Typography sx={componentStyles.monoId}>EXC-12345</Typography>
```

---

## Utility CSS Classes

Available in `globalStyles.css`:

### Text Colors

```html
<span class="text-primary">Primary text</span>
<span class="text-secondary">Secondary text</span>
<span class="text-muted">Muted text</span>
<span class="text-link">Link text</span>
```

### Text Sizes

```html
<span class="text-xs">12px</span>
<span class="text-sm">13px</span>
<span class="text-base">14px</span>
<span class="text-lg">16px</span>
<span class="text-xl">18px</span>
```

### Font Weights

```html
<span class="font-normal">Regular</span>
<span class="font-medium">Medium</span>
<span class="font-semibold">Semibold</span>
<span class="font-bold">Bold</span>
```

### Semantic Typography

```html
<h1 class="text-page-title">Page Title</h1>
<h2 class="text-section-title">Section Title</h2>
<h3 class="text-card-title">Card Title</h3>
<th class="text-table-header">Column</th>
<p class="text-body">Body text</p>
<p class="text-body-sm">Small body text</p>
<span class="text-caption">Caption</span>
<span class="text-metadata">Timestamp</span>
<span class="text-kpi-large">1,234</span>
<span class="text-kpi-label">TOTAL</span>
```

### Truncation

```html
<p class="truncate">Single line truncate...</p>
<p class="line-clamp-2">Multi-line clamp to 2 lines...</p>
<p class="line-clamp-3">Multi-line clamp to 3 lines...</p>
```

### Numbers

```html
<span class="tabular-nums">1,234,567</span>
```

---

## File Structure

```
ui/src/theme/
├── index.ts              # Unified exports
├── globalDesignSystem.ts # Complete design system (tokens)
├── globalStyles.css      # CSS variables & resets
├── tokens.ts             # Legacy tokens (for migration)
├── theme.ts              # MUI theme configuration
└── DESIGN_SYSTEM.md      # This documentation
```

---

## Migration Guide

### From tokens.ts to globalDesignSystem.ts

The old `tokens.ts` exports are still available for backward compatibility. For new components, prefer the new system:

```tsx
// Old (still works)
import { lightColors, typographyScale } from "@/theme";
const bg = lightColors.bg.page;
const title = typographyScale.pageTitle;

// New (preferred)
import { colors, typography } from "@/theme";
const bg = colors.bg.page;
const title = typography.pageTitle;
```

### Adding Inter Font

Add to your `index.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
  rel="stylesheet"
/>
```

Or via npm:

```bash
npm install @fontsource/inter
```

Then in `main.tsx`:

```tsx
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
```

---

## Best Practices

1. **Use semantic tokens** — `colors.text.primary` not `#111827`
2. **Use layout presets** — `layoutSpacing.cardPadding` not `20px`
3. **Prefer borders over shadows** — Cards use borders, dropdowns use shadows
4. **Keep colors muted** — Enterprise UIs should be calm, not alarming
5. **Respect the grid** — All spacing should align to the 8px grid
6. **Be consistent** — Same spacing, same typography everywhere
