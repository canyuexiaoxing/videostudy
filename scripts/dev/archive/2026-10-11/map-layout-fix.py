from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'desktop/src/study-design.css'
with p.open('a',encoding='utf-8') as f:
 f.write('''
/* Keep the knowledge canvas drawable when a long example timeline is present. */
.study-app .study-sidebar .mind-map-panel:has(.example-timeline) { overflow: auto; }
.study-app .study-sidebar .mind-map-panel:has(.example-timeline) .mind-map-heading,
.study-app .study-sidebar .mind-map-panel:has(.example-timeline) .example-timeline { flex: none; }
.study-app .study-sidebar .mind-map-panel:has(.example-timeline) .map-canvas-shell { flex: 0 0 clamp(380px, 55vh, 620px); min-height: 380px; }
.study-app .study-sidebar .mind-map-panel:has(.example-timeline) .mind-map-canvas { min-height: 300px; }
''')
