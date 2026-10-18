# Framewise approved ambient background QA — 2026-10-18

Scope: exterior background only; retain existing application layout and functionality.

Source: selected generated image exec-996cb081-8125-4b9f-96e3-9e98cdcbab21.png (1505×1045).
Implementation: .local/qa/ambient-motion/start.png (1440×1000); same empty-course state and near-identical aspect ratio. Both images inspected together, accounting for source scaling.

- Typography: existing native fonts, weights and content retained. Header helper text darkened to #304466 for readability on blue.
- Layout: original columns, spacing, cards, radii and tabs retained. No layout motion; verified player bounding box stable between animation positions.
- Colors: clearly visible cornflower blue upper left, lavender right/lower edges, pale diagonal light match the selected direction. Opaque white cards retain readable foreground contrast.
- Asset fidelity: generated standalone background in desktop/public/framewise-ambient.png, applied directly as an image; no UI baked into asset. Existing logo and player preserved.
- Copy: existing copy retained without generated text artifacts.
- Interaction: tabs clickable; no page errors; hidden pauses; reduced-motion static; 390px no overflow.
- Expected difference: moving background cloud positions vary by keyframe; original application typography/layout intentionally retained instead of reproducing raster mockup distortions.

No outstanding P0/P1/P2 findings in scoped change.

final result: passed


## Three appearance switch — 2026-10-18

References: selected acrylic mockup exec-8860196c-05b2-4f44-a1fa-bbdaaa1a05f0.png; blue screenshot codex-clipboard-522dbcf4-4118-4252-8b45-f99f4bbcd8bd.png; original pale screenshot codex-clipboard-71c297a2-a099-49e3-97d2-903a3927062d.png. Viewports normalized by aspect ratio; preserve existing responsive layout rather than reference window size.
Rendered comparison: .local/qa/appearance-switch/{acrylic,blue,classic}.png. All three opened and inspected.
- Typography/copy: existing foreground remains opaque; header control follows existing sizes, no content changes.
- Layout: appearance control at top beside upload; original columns and cards retained, bounding box unchanged during switching.
- Colors/material: acrylic large surfaces rgba white .44 with 20px backdrop blur, translucent inner surfaces and white edge. Blue retains opaque white cards over approved generated background. Classic hides colored artwork over pale base.
- Assets: original logo and player retained, approved background image reused; no text rendered as images.
- Behavior: clean profile blue by default; three options, remembered across reload, intermediate color checked during 450ms transition, system reduced motion disables transition, mobile390 no horizontal overflow, tab interactions pass, no page errors.
- Minor intentional variation: native app controls/text are preserved instead of raster mockup artifacts; selected style persists after first use.

final result: passed
