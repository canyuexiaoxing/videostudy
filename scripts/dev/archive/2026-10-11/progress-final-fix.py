from pathlib import Path
r=Path('E:/workp/videostudy')
p=r/'desktop/src/analysisProgress.ts';s=p.read_text();s=s.replace("const ratio=p?(p.completedStages+", "const ratio=p?.stage==='saving'?.95:p?(p.completedStages+");p.write_text(s)
p=r/'desktop/src/analysisProgress.test.mjs';s=p.read_text().replace("completedUnits:0,totalUnits:0}).ratio,.8)","completedUnits:0,totalUnits:0}).ratio,.95)");p.write_text(s)
p=r/'desktop/src/App.vue';s=p.read_text();s=s.replace("    if (existingJobId.value === entry.id) {\n      clearSubtitleJob()", "    if (existingJobId.value === entry.id) {\n      analysisState.value = ''\n      analysisProgress.value = null\n      clearSubtitleJob()");p.write_text(s,encoding='utf-8')
p=r/'desktop/src/study-design.css';s=p.read_text();s=s.replace('flex-wrap: wrap; row-gap: 0; align-items: center; gap: 22px;', 'flex-wrap: wrap; align-items: center; gap: 22px; row-gap: 10px;');p.write_text(s)
stage=Path(__file__).parent
deploy=(stage/'region-deploy.py').read_text().replace("'region-images'","'progress-images'").replace("'ignored_region.py')","'ignored_region.py','analysis_progress.py')").replace('slide_grouping.py ignored_region.py /app/','slide_grouping.py ignored_region.py analysis_progress.py /app/')
(stage/'progress-deploy.py').write_text(deploy)
