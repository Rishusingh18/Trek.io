"""
Generates and appends custom Academic Precision design system utilities to tailwind.min.css.
"""
import os

THEME_COLORS = {
    "on-secondary-container": "#00714e",
    "on-tertiary-fixed": "#2f1500",
    "on-tertiary-fixed-variant": "#6e3900",
    "surface-tint": "#5b598c",
    "on-secondary": "#ffffff",
    "surface-container-low": "#eff4ff",
    "on-background": "#0d1c2e",
    "error-container": "#ffdad6",
    "tertiary-fixed-dim": "#ffb77d",
    "on-tertiary-container": "#cf7100",
    "secondary-fixed-dim": "#68dba9",
    "error": "#ba1a1a",
    "primary-fixed-dim": "#c4c1fb",
    "secondary-container": "#82f5c1",
    "on-tertiary": "#ffffff",
    "tertiary-container": "#381a00",
    "primary-fixed": "#e3dfff",
    "surface-container-high": "#dce9ff",
    "on-secondary-fixed": "#002114",
    "outline": "#787680",
    "tertiary-fixed": "#ffdcc3",
    "inverse-surface": "#233144",
    "inverse-primary": "#c4c1fb",
    "surface-dim": "#ccdbf3",
    "on-secondary-fixed-variant": "#005137",
    "surface-bright": "#f8f9ff",
    "tertiary": "#170700",
    "on-primary-fixed": "#181445",
    "surface-variant": "#d5e3fc",
    "secondary": "#006c4a",
    "on-surface": "#0d1c2e",
    "secondary-fixed": "#85f8c4",
    "on-primary": "#ffffff",
    "on-primary-container": "#8683ba",
    "primary": "#070235",
    "surface-container": "#e6eeff",
    "surface-container-highest": "#d5e3fc",
    "surface-container-lowest": "#ffffff",
    "on-error-container": "#93000a",
    "primary-container": "#1e1b4b",
    "inverse-on-surface": "#eaf1ff",
    "on-primary-fixed-variant": "#444173",
    "outline-variant": "#c8c5d0",
    "surface": "#f8f9ff",
    "on-error": "#ffffff",
    "background": "#f8f9ff",
    "on-surface-variant": "#47464f"
}

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def generate_css():
    lines = []
    lines.append("\n/* ======================================================== */")
    lines.append("/* ACADEMIC PRECISION THEME UTILITIES (OFFLINE PREBUILT)   */")
    lines.append("/* ======================================================== */")
    
    # CSS Variables on :root
    lines.append(":root {")
    for name, hex_val in THEME_COLORS.items():
        r, g, b = hex_to_rgb(hex_val)
        lines.append(f"  --color-{name}: {hex_val};")
        lines.append(f"  --color-{name}-rgb: {r}, {g}, {b};")
    lines.append("}")

    # Color classes
    for name, hex_val in THEME_COLORS.items():
        escaped = name.replace("-", "\\-")
        r, g, b = hex_to_rgb(hex_val)
        
        # Backgrounds
        lines.append(f".bg-{escaped} {{ background-color: {hex_val} !important; }}")
        lines.append(f".hover\\:bg-{escaped}:hover {{ background-color: {hex_val} !important; }}")
        
        # Opacity variants
        for op in [10, 20, 30, 40, 50, 60, 70, 80, 90, 95]:
            lines.append(f".bg-{escaped}\\/{op} {{ background-color: rgba({r}, {g}, {b}, {op/100}) !important; }}")
            lines.append(f".hover\\:bg-{escaped}\\/{op}:hover {{ background-color: rgba({r}, {g}, {b}, {op/100}) !important; }}")

        # Text colors
        lines.append(f".text-{escaped} {{ color: {hex_val} !important; }}")
        lines.append(f".hover\\:text-{escaped}:hover {{ color: {hex_val} !important; }}")

        # Borders
        lines.append(f".border-{escaped} {{ border-color: {hex_val} !important; }}")
        lines.append(f".hover\\:border-{escaped}:hover {{ border-color: {hex_val} !important; }}")
        for op in [40, 60, 80]:
            lines.append(f".border-{escaped}\\/{op} {{ border-color: rgba({r}, {g}, {b}, {op/100}) !important; }}")

        # Rings
        lines.append(f".ring-{escaped} {{ --tw-ring-color: {hex_val} !important; }}")
        for op in [20, 40]:
            lines.append(f".ring-{escaped}\\/{op} {{ --tw-ring-color: rgba({r}, {g}, {b}, {op/100}) !important; }}")

        # Fills
        lines.append(f".fill-{escaped} {{ fill: {hex_val} !important; }}")

    # Typography classes
    lines.append("""
.font-headline-lg, .font-headline-md, .font-headline-sm, .font-display, .font-data-metric, .font-headline {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
}
.font-body-lg, .font-body-md, .font-body-sm, .font-label-md, .font-label-sm, .font-title-md, .font-body {
  font-family: 'Inter', sans-serif !important;
}
.text-headline-lg { font-size: 2.25rem !important; line-height: 2.75rem !important; font-weight: 700 !important; }
.text-headline-md { font-size: 1.5rem !important; line-height: 2rem !important; font-weight: 600 !important; }
.text-headline-sm { font-size: 1.25rem !important; line-height: 1.75rem !important; font-weight: 600 !important; }
.text-title-md { font-size: 1rem !important; line-height: 1.5rem !important; font-weight: 600 !important; }
.text-body-lg { font-size: 1.125rem !important; line-height: 1.75rem !important; font-weight: 400 !important; }
.text-body-md { font-size: 0.875rem !important; line-height: 1.375rem !important; font-weight: 400 !important; }
.text-body-sm { font-size: 0.75rem !important; line-height: 1.125rem !important; font-weight: 400 !important; }
.text-label-md { font-size: 0.875rem !important; line-height: 1.25rem !important; font-weight: 500 !important; }
.text-label-sm { font-size: 0.75rem !important; line-height: 1rem !important; font-weight: 600 !important; }
.text-data-metric { font-size: 1.75rem !important; line-height: 2rem !important; font-weight: 700 !important; }

/* Custom Spacing tokens */
.p-space-xl { padding: 2.5rem !important; }
.px-space-xl { padding-left: 2.5rem !important; padding-right: 2.5rem !important; }
.py-space-xl { padding-top: 2.5rem !important; padding-bottom: 2.5rem !important; }

.p-space-lg { padding: 1.5rem !important; }
.px-space-lg { padding-left: 1.5rem !important; padding-right: 1.5rem !important; }
.py-space-lg { padding-top: 1.5rem !important; padding-bottom: 1.5rem !important; }

.p-space-md { padding: 1rem !important; }
.px-space-md { padding-left: 1rem !important; padding-right: 1rem !important; }
.py-space-md { padding-top: 1rem !important; padding-bottom: 1rem !important; }

.p-space-sm { padding: 0.5rem !important; }
.px-space-sm { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
.py-space-sm { padding-top: 0.5rem !important; padding-bottom: 0.5rem !important; }

.p-space-xs { padding: 0.25rem !important; }
.px-space-xs { padding-left: 0.25rem !important; padding-right: 0.25rem !important; }
.py-space-xs { padding-top: 0.25rem !important; padding-bottom: 0.25rem !important; }

.m-space-sm { margin: 0.5rem !important; }
.gap-space-xl { gap: 2.5rem !important; }
.gap-space-lg { gap: 1.5rem !important; }
.gap-space-md { gap: 1rem !important; }
.gap-space-sm { gap: 0.5rem !important; }
.gap-space-xs { gap: 0.25rem !important; }
""")

    return "\n".join(lines)

def main():
    css_path = os.path.abspath("frontend/assets/css/tailwind.min.css")
    with open(css_path, "r", encoding="utf-8", errors="ignore") as f:
        existing = f.read()

    if "ACADEMIC PRECISION THEME UTILITIES" in existing:
        print("Theme utilities already present in tailwind.min.css")
        return

    addon = generate_css()
    with open(css_path, "a", encoding="utf-8") as f:
        f.write(addon)
    print(f"Appended {len(addon)} bytes of custom theme utilities to {css_path}")

if __name__ == "__main__":
    main()

