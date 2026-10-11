---
name: Logistics & Operations System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#44474c'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#74777d'
  outline-variant: '#c4c6cd'
  surface-tint: '#4f6073'
  primary: '#041627'
  on-primary: '#ffffff'
  primary-container: '#1a2b3c'
  on-primary-container: '#8192a7'
  inverse-primary: '#b7c8de'
  secondary: '#0058be'
  on-secondary: '#ffffff'
  secondary-container: '#2170e4'
  on-secondary-container: '#fefcff'
  tertiary: '#211200'
  on-tertiary: '#ffffff'
  tertiary-container: '#38260b'
  on-tertiary-container: '#a88c69'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d2e4fb'
  primary-fixed-dim: '#b7c8de'
  on-primary-fixed: '#0b1d2d'
  on-primary-fixed-variant: '#38485a'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#adc6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004395'
  tertiary-fixed: '#feddb5'
  tertiary-fixed-dim: '#e1c29b'
  on-tertiary-fixed: '#281802'
  on-tertiary-fixed-variant: '#584326'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  gutter: 16px
  margin: 24px
  container-max: 1440px
  table-row-height: 48px
---

## Brand & Style
The design system is engineered for high-stakes operational environments where speed of comprehension and data integrity are paramount. The brand personality is authoritative, reliable, and precise, catering to logistics managers and floor supervisors who require a "heads-up display" of complex warehouse metrics.

The visual style follows a **Modern Corporate** aesthetic with a heavy emphasis on **Information Density**. It prioritizes utility over decoration, utilizing generous horizontal space and disciplined vertical rhythms to ensure that vast amounts of inventory and shipping data remain legible. The interface feels like a high-performance tool—utilitarian and unobtrusive, yet polished through subtle refinements in spacing and alignment.

## Colors
This design system utilizes a high-contrast palette to distinguish between structural navigation, interactive elements, and critical data states. 

- **Primary (Deep Navy):** Reserved for persistent structural elements like sidebars and headers to provide a grounded, professional frame.
- **Action (Blue):** Used exclusively for primary interactive calls-to-action (CTAs) and focus states to ensure they are immediately identifiable.
- **Neutral Scale:** A sophisticated range of cool grays handles the "workhorse" tasks of the UI—borders, secondary text, and table backgrounds.
- **Semantic Palette:** A strict color-coding system is used for stock levels and system health. These colors must always be accompanied by labels or icons to ensure accessibility for color-blind users.

## Typography
The system uses **Inter** for its exceptional legibility at small sizes and high x-height, which is critical for dense data tables. A secondary monospaced font is introduced for SKU numbers, tracking IDs, and quantities to prevent "character jumping" and improve scannability across columns.

Hierarchy is established primarily through weight and case rather than dramatic size shifts. This maintains a compact vertical footprint. Labels for table headers and metadata use uppercase styling with increased letter spacing to distinguish them from actionable data.

## Layout & Spacing
The layout follows a **Fixed-Fluid Hybrid** model. The sidebar remains fixed at 240px, while the main content area utilizes a 12-column fluid grid. To maintain information density, the spacing system is built on a 4px base unit.

- **Desktop:** 24px outer margins with 16px gutters between cards/modules.
- **Data Tables:** Rows are set to a compact 48px height to maximize the number of visible items above the fold. 
- **Modules:** Use a "tight-fit" philosophy where related information groups (e.g., Warehouse Zone and Capacity) are separated by only 8px-12px, while distinct modules are separated by 24px.

## Elevation & Depth
To keep the UI feeling "enterprise-grade" and fast, elevation is used sparingly. This design system avoids heavy shadows and deep blurs.

- **Surface Layers:** The background uses a very light gray (#F8FAFC), while dashboard cards and table containers use pure white (#FFFFFF). 
- **Outlines:** All containers use a 1px solid border (#E2E8F0) to define boundaries clearly without relying on shadow-heavy depth.
- **Subtle Shadows:** Only primary cards and modals receive a shadow. Use a "soft-drop" shadow: `0px 1px 3px rgba(0, 0, 0, 0.05), 0px 4px 6px rgba(0, 0, 0, 0.02)`. This creates a subtle lift that suggests interaction without cluttering the visual field.

## Shapes
The shape language is **Soft (0.25rem / 4px)**. This slight rounding takes the edge off the industrial nature of the data while maintaining a professional, rigid structure that aligns well with grid-heavy layouts. 

- **Input Fields/Buttons:** 4px radius.
- **Data Tags/Badges:** Fully rounded (pill) to distinguish them from interactive buttons.
- **Large Containers:** 8px radius (rounded-lg) to provide a clear container hierarchy.

## Components
- **Data Tables:** The core of the system. Feature sticky headers, zebra-striping on hover, and inline status badges. Text is aligned left; numerical values (SKUs, counts) are aligned right.
- **Action Buttons:** Primary actions use the Action Blue with white text. Secondary actions use a white background with a Navy border and text. 
- **Status Badges:** Use a "tint-on-tone" approach—light background of the semantic color (e.g., 10% opacity Green) with a dark version of the same color for the text and a 2px leading dot.
- **Input Fields:** Use a 1px #CBD5E1 border, turning Action Blue on focus. Labels are always persistent above the field in `label-md` style.
- **Stock Indicators:** Small progress bars within table cells or cards. Use a three-step color logic: Green (60-100%), Amber (20-59%), Red (<20%).
- **KPI Cards:** Large numeric displays with a simplified trend line (sparkline) to show 24-hour throughput or inventory fluctuations.