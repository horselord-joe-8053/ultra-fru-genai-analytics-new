# Documentation table style (reference)

Use this style for comparison/option tables in this repo so they stay consistent and easy to scan.

## Visual and layout

- **Header row:** Dark blue background, white text (`background:#1565c0;color:white`).
- **Column headers:** Clear labels; add a small subtitle in `<small>` where helpful (e.g. "where code lives", "where it deploys").
- **Body rows:** Alternating or strategy-specific background colors (e.g. green `#e8f5e9`, amber `#fff3e0`, red tint `#ffebee`).
- **Aspect / left column:** Light blue `#e3f2fd` for the "Aspect" or "Strategy" column so it stands out.

## Text and structure

- **Numeration:** Use ① ② ③ (or 1. 2. 3.) for strategies, options, or aspects.
- **Bullets:** Use `•` and `<br>` to break multi-item content into short lines.
- **Badges:**
  - <span style="background:#c8e6c9;padding:2px 4px">✓</span> (green) for pros / advantages / "yes".
  - <span style="background:#ffcdd2;padding:2px 4px">⚠</span> (red) for cons / risks / warnings.
  - <span style="background:#fff9c4;padding:2px 4px">manual</span> (yellow) for manual steps.
  - <span style="background:#c8e6c9;padding:2px 4px">auto</span> (green) for automatic.
- **Inline labels:** Use short colored spans to distinguish concepts (e.g. <span style="background:#e3f2fd;padding:1px 3px">branch</span> vs <span style="background:#fff3e0;padding:1px 3px">env</span> for source branch vs target environment).
- **Recommendation:** Use a small badge like <span style="background:#2e7d32;color:white;padding:1px 4px">recommended</span> for the preferred option.

## Distinguishing concepts

- When the table mixes **source** (e.g. Git branch, config file) and **target** (e.g. deployment environment):
  - Add a **legend** above the table: e.g. "**Source branch** = Git branch (where code lives). **Target env** = deployment environment (dev, staging, prod)."
  - Use **column headers** that say "Source branch(es)" and "Target env (deploy trigger)" (or similar).
  - In cells, use inline labels (e.g. "branch <code>main</code> → env dev") so branch vs env are visually distinct.

## Reference example

See **§ 3.4.1. Branch strategy (recommended: trunk-based)** in `docs/TODO_CICD_ORCHESTRATOR_ENV.md` for the canonical example (colors, numeration, bullets, badges, source vs target distinction).

