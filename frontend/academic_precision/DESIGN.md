---
name: Academic Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#ccdbf3'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d5e3fc'
  on-surface: '#0d1c2e'
  on-surface-variant: '#47464f'
  inverse-surface: '#233144'
  inverse-on-surface: '#eaf1ff'
  outline: '#787680'
  outline-variant: '#c8c5d0'
  surface-tint: '#5b598c'
  primary: '#070235'
  on-primary: '#ffffff'
  primary-container: '#1e1b4b'
  on-primary-container: '#8683ba'
  inverse-primary: '#c4c1fb'
  secondary: '#006c4a'
  on-secondary: '#ffffff'
  secondary-container: '#82f5c1'
  on-secondary-container: '#00714e'
  tertiary: '#170700'
  on-tertiary: '#ffffff'
  tertiary-container: '#381a00'
  on-tertiary-container: '#cf7100'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3dfff'
  primary-fixed-dim: '#c4c1fb'
  on-primary-fixed: '#181445'
  on-primary-fixed-variant: '#444173'
  secondary-fixed: '#85f8c4'
  secondary-fixed-dim: '#68dba9'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#005137'
  tertiary-fixed: '#ffdcc3'
  tertiary-fixed-dim: '#ffb77d'
  on-tertiary-fixed: '#2f1500'
  on-tertiary-fixed-variant: '#6e3900'
  background: '#f8f9ff'
  on-background: '#0d1c2e'
  surface-variant: '#d5e3fc'
typography:
  display:
    fontFamily: Plus Jakarta Sans
    fontSize: 3.5rem
    fontWeight: '700'
    lineHeight: 4rem
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: 2rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  title-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: 1.75rem
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.375rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1.125rem
  label-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.25rem
  label-sm:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.025em
  data-metric:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2rem
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system embodies structured intellect, computational guidance, and scholarly clarity. Designed for adaptive learning analytics and personalized path progression, the aesthetic bridges institutional credibility with the velocity of modern SaaS.

The visual direction follows **Modern Minimalist with Tonal Data Density**:
- **Clarity over ornament:** Decoration is strictly functional. Visual weight is reserved for mastery signals, progress vectors, and decision pathways.
- **Academic rigor:** Dense, structured layouts that honor cognitive flow, reducing visual noise to maintain deep work states.
- **Subtle tactility:** Grounded surface differentiation using structural borders and low-contrast surface tints rather than heavy, distracting shadows.

## Colors

The palette establishes an intellectual, highly accessible workspace compliant with WCAG 2.1 AA across interactive states, with the exception of the decorative `on-tertiary-container` accent token which is reserved for large indicators and badges.

- **Primary (`#070235` - Deep Indigo):** The bedrock of the interface. Used for global navigation, dominant branding anchors, primary call-to-actions, and high-emphasis typographic headers.
- **Secondary (`#006c4a` - Vibrant Emerald):** Signifies mastery, achieved milestones, verified skill acquisition, and optimal learning velocities.
- **Tertiary (`#170700` - Warm Amber):** Denotes in-progress topics, spaced repetition reviews, and concepts requiring consolidation.
- **Status Coral (`#ba1a1a`):** Reserved strictly for skill gaps, decaying retention rates, at-risk prerequisites, and system warnings.
- **Neutral (`#47464f` - Slate Gray):** Balances data density through structured borders, secondary metadata, and supportive UI scaffolding.

### Surface System
- Canvas Background: `#F8FAFC` (Slate 50)
- Surface Card: `#FFFFFF`
- Surface Elevated: `#F1F5F9` (Slate 100)
- Border Subtle: `#E2E8F0` (Slate 200)
- Border Strong: `#CBD5E1` (Slate 300)

## Typography

The typographic hierarchy couples **Plus Jakarta Sans** for structure, headers, and major metrics with **Inter** for dense, computational body text and analytical readouts.

- Use `Plus Jakarta Sans` with tight negative tracking (`-0.01em` to `-0.025em`) for all headline tiers and numerical dashboard telemetry to impart a sharp, modern personality.
- Use `Inter` for micro-copy, tabular data, continuous prose, and interactive form elements to leverage its unmatched neutral legibility at small scale.
- Quantitative data points, completion ratios, and mastery percentages must utilize tabular figures (`font-variant-numeric: tabular-nums`) to prevent layout shifts during live analytical re-indexing.

## Layout & Spacing

The layout is built upon an 8pt modular rhythm (base unit: `0.5rem` / `8px`) set within a responsive 12-column fluid grid.

### Grid Breakpoints
- **Desktop (1280px+):** 12 columns, 24px gutters (`gutter`), 32px canvas margins (`margin`). Max layout container constraint of `1440px`.
- **Tablet (768px - 1279px):** 8 columns, 20px gutters, 24px canvas margins.
- **Mobile (< 768px):** 4 columns, 16px gutters (`gutter-mobile`), 16px canvas margins (`margin-mobile`).

### Layout Mechanics
- Data-heavy screens utilize a persistent 260px left-hand utility rail for pathway hierarchies, collapsing into an overlay drawer below 1024px.
- Analytical cards sit in multi-column clusters (spans of 3, 4, 6, or 12).
- Micro-spacing (`space-xs`, `space-sm`) separates paired labels and metrics; macro-spacing (`space-lg`, `space-xl`) isolates conceptual subject clusters.

## Elevation & Depth

Visual separation relies primarily on **tonal containment and crisp micro-borders**, using elevation sparingly to indicate transient actions or active spatial focus.

- **Level 0 (Base Canvas):** `#F8FAFC`. Completely flat.
- **Level 1 (Cards & Data Panels):** Solid `#FFFFFF` fill with a `1px` structural border of `#E2E8F0`. Shadow: `0 1px 2px 0 rgba(15, 23, 42, 0.04)`.
- **Level 2 (Hovered Cards & Action Modules):** Solid `#FFFFFF` fill, border shifts to `#CBD5E1`. Shadow: `0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05)`.
- **Level 3 (Dropdowns, Popovers & Contextual Insights):** Solid `#FFFFFF` fill, border `#CBD5E1`. Shadow: `0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.03)`.
- **Level 4 (Modal Dialogs & Path Overlays):** Solid `#FFFFFF` fill with an indigo-tinted shadow: `0 20px 25px -5px rgba(30, 27, 75, 0.12), 0 8px 10px -6px rgba(30, 27, 75, 0.06)`. Background scrim utilizes `rgba(15, 23, 42, 0.45)` with `backdrop-filter: blur(4px)`.

## Shapes

The design system employs a **Soft (`1`)** shape language to reinforce structural balance, precision, and tool-like ergonomics without feeling sterile or overly playful.

- **Base Corner Radius (0.25rem / 4px):** Checkboxes, radio indicators, code blocks, tabular cells, and status dots.
- **Container Radius (`rounded-lg` - 0.5rem / 8px):** Standard cards, buttons, text inputs, badges, and dropdown menus.
- **Structural Radius (`rounded-xl` - 0.75rem / 12px):** Top-level learning module containers, modal dialogs, and diagnostic overview sections.
- Pill forms (`rounded-full`) are strictly confined to user avatars and circular milestone progress beads.

## Components

### Buttons
- **Primary:** Background `#1E1B4B`, label text `#FFFFFF`, radius `rounded-lg` (8px), height `40px` (desktop), padding `0 16px`. Active press invokes `scale(0.99)`.
- **Secondary / Subdued:** Background `#FFFFFF`, border `1px solid #CBD5E1`, text `#334155`. Hover shifts background to `#F8FAFC`.
- **State Actions (Start Path / Review):**
  - Mastery/Success: Background `#059669`, text `#FFFFFF`.
  - At-Risk/Remediation: Background `#FFF1F2`, text `#E11D48`, border `1px solid #FECDD3`.

### Badges & Status Chips
- Height `24px`, padding `0 8px`, typography `label-sm`.
- **Mastered:** Background `#ECFDF5`, text `#065F46`, border `1px solid #A7F3D0`.
- **Developing:** Background `#FFFBEB`, text `#92400E`, border `1px solid #FDE68A`.
- **Critical / Skill Gap:** Background `#FFF1F2`, text `#9F1239`, border `1px solid #FECDD3`.

### Input Fields
- Height `40px`, border `1px solid #CBD5E1`, background `#FFFFFF`, text `#0F172A`, placeholder `#94A3B8`.
- Focus state: Outline `2px solid #1E1B4B` with an offset of `1px`.
- Error state: Border `#E11D48`, outline `2px solid #E11D48`.

### Checkboxes & Radios
- Size `16px x 16px`, border `1.5px solid #94A3B8`, radius `4px` (checkbox) or `50%` (radio).
- Checked: Background `#1E1B4B`, border `#1E1B4B`, check icon `#FFFFFF`.

### Cards & Metric Nodes
- Minimum padding `space-md` (16px), default background `#FFFFFF`, border `1px solid #E2E8F0`, corner radius `8px`.
- Layout: Top-row label (`label-sm`), middle-row quantified score (`data-metric`), bottom-row delta indicator with directional arrow and color-coded status indicator.

### Specialized EdTech Components
- **Progress Spine:** A continuous 2px vertical guide in `#E2E8F0` linking sequential milestone nodes. Completed nodes present a filled emerald ring, current nodes pulse an indigo core, and locked nodes display muted slate outlines.
- **Mastery Heatbar:** A 6px high segmented meter visualizing topic mastery ratios (Emerald for >85%, Amber for 60-84%, Coral for <60%).