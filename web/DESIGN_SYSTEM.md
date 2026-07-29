# PSOS local UI design system

## Primary task flow

`request → run → read → inspect evidence → check system status`

The request field is the first and widest interaction. The result stays in the same reading column.
System integrity, lifecycle counts, next action, and recent runs remain in a subordinate status rail.

## Content roles

- Navigation: product identity and global health only.
- Controls: one request field, one optional search toggle, one primary action.
- Primary content: the generated result, capped at 780px for readable line length.
- Context: selected route and immutable run ID.
- Evaluation: evidence and artifacts in an opt-in disclosure.
- Status: integrity summary, lifecycle counts, next safe action, and recent runs.

## Visual rules

- Font: one interface family (`Inter`, Korean/system fallbacks); monospace only for immutable IDs.
- Type scale: 11, 12, 13, 14, 15, 16, 20, 22, and 24px by repeated semantic role.
- Spacing: 4, 8, 12, 16, 24, and 32px. A 48px separation marks the transition from request to result.
- Widths: 1504px shell, 340px status rail, 780px maximum result measure.
- Borders: one-pixel neutral borders; three-pixel left status accents.
- Radius: 8px controls and nested groups; 12px major regions.
- Color: green for action/healthy/verified, amber for next attention, red for failure, neutral elsewhere.
- Shadows: none. Grouping comes from borders, alignment, and background contrast.

## Target viewports

- Desktop: 1440×900 and 1920×1080.
- Narrow fallback: one column below 960px; controls stack below 640px.
