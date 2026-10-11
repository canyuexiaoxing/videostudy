from pathlib import Path
p=Path('E:/workp/videostudy/desktop/src/autoRegionScan.ts')
s=p.read_text(encoding='utf-8').replace("if(a.status!=='detected'||!retained||same({timeMs:left,status:'detected',region:retained},b))continue", "if(a.status!=='detected'||!retained||!same({timeMs:left,status:'detected',region:retained},a)||same({timeMs:left,status:'detected',region:retained},b))continue")
p.write_text(s,encoding='utf-8')
