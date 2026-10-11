from pathlib import Path
p=Path(r'E:\workp\videostudy\desktop\src\study-design.css')
p.write_text(p.read_text(encoding='utf-8')+'''
/* Separate the three task settings sections without changing their controls. */
.study-app .analysis-settings-content { gap:20px; padding:12px 18px 22px; }
.study-app .analysis-settings-content > .mode-picker,
.study-app .analysis-settings-content > .advanced-options,
.study-app .analysis-settings-content > .restore {
  padding:16px; border:1px solid #e2e8f4; border-radius:10px; background:#f9fbff;
}
.study-app .analysis-settings-content > .mode-picker { flex-wrap:wrap; gap:12px 18px; }
.study-app .analysis-settings-content > .mode-picker select { max-width:100%; }
.study-app .analysis-settings-content > .restore { gap:10px; }
.study-app .analysis-settings-content > .restore > label { font-weight:600; }
.study-app .analysis-settings-content > .advanced-options .advanced-fields { margin-top:12px; padding-top:12px; border-top:1px solid #e2e8f4; }
@media (max-width:600px) {
 .study-app .analysis-settings-content { gap:16px; padding:10px 12px 18px; }
 .study-app .analysis-settings-content > .mode-picker,
 .study-app .analysis-settings-content > .advanced-options,
 .study-app .analysis-settings-content > .restore { padding:12px; }
}
''',encoding='utf-8')
