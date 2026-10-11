from pathlib import Path
r=Path('E:/workp/videostudy')
p=r/'agent-python/analysis.py';s=p.read_text(encoding='utf-8')
start=s.index('                def understand(page):')
end=s.index('                page_groups = list(pool.map(understand, page_groups))',start)
s=s[:start]+'''                def understand(page):
                    result = cached(
                        f'page:{page["pageIndex"]}',
                        {'page': page, 'pages': page_groups, 'speech': transcript['segments']},
                        lambda: analyze_page(page, page_groups, by_time, keyframe_dir,
                                             transcript['segments'], visual_analysis_mode),
                        accept=lambda value: (value.get('imageAnalysis') or value.get('textAnalysis') or {}).get('status') != 'failed',
                    )
                    if (result.get('imageAnalysis') or result.get('textAnalysis') or {}).get('status') != 'failed':
                        progress.unit_done(str(page['pageIndex']), 'pages')
                    return result
'''+s[end:]
p.write_text(s,encoding='utf-8')
p=r/'desktop/src/analysisProgress.test.mjs';s=p.read_text().replace("assert.equal(view.ratio,.68)","assert.ok(Math.abs(view.ratio-.68)<1e-9)").replace("assert.equal(progressView('failed',{stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}).ratio,.68)","assert.ok(Math.abs(progressView('failed',{stage:'pages',completedStages:3,totalStages:5,completedUnits:8,totalUnits:20}).ratio-.68)<1e-9)");p.write_text(s)
