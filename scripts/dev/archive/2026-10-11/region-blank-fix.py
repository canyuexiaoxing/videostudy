from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/slide_grouping.py')
s=p.read_text(encoding='utf-8')
old='''        if _blank(current, current_image, mask):
            transitions.append(time_ms)'''
new='''        blank = _blank(current, current_image, mask)
        if blank and members and masks is not None:
            # A moved mask may hide every visible lesson line. Confirm that
            # the page anchor had content in the shared visible area before
            # calling this a genuine blank transition; include repeated blanks.
            anchor_frame, previous_frame = members[0], members[-1]
            shared = mask & masks[anchor_frame["frameTimeMs"]] & masks[previous_frame["frameTimeMs"]]
            common_anchor = anchor_frame
            for item in (anchor_frame,previous_frame,current):
                common_anchor = grouping_frame(common_anchor,region_at(ignore_region,item["frameTimeMs"]),*dimensions[anchor_frame["frameTimeMs"]])
            if not shared.any() or _blank(common_anchor,images[anchor_frame["frameTimeMs"]],shared):
                blank = False
        if blank:
            transitions.append(time_ms)'''
assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
t=Path('E:/workp/videostudy/agent-python/test_region_timeline.py')
s=t.read_text(encoding='utf-8').replace('for t in [0,6000,12000]', 'for t in [0,6000,8000,12000]').replace("[0,6000,12000])", "[0,6000,8000,12000])")
s+='''
 def test_real_blank_transition_survives_mask_move(self):
  import tempfile,cv2,numpy as np
  from pathlib import Path
  from slide_grouping import group_pages
  with tempfile.TemporaryDirectory() as directory:
   frames=[]
   for t in [0,6000,12000]:
    image=np.full((180,320),255,dtype=np.uint8)
    if t!=6000:image[80:100,135:180]=0
    cv2.imwrite(str(Path(directory)/f'{t}.jpg'),image)
    frames.append({'frameTimeMs':t,'ocrBlocks':[] if t==6000 else [{'text':'central lesson content','polygon':[[135,80],[180,80],[180,100],[135,100]]}]})
   right=dict(x=.6,y=0,width=.4,height=.8);left=dict(x=0,y=0,width=.4,height=.8)
   pages,transitions=group_pages(frames,Path(directory),[],ask_json=lambda _: {'samePage':True},ignore_region={'nodes':[{'timeMs':0,'region':right},{'timeMs':6000,'region':left}]})
   self.assertEqual(transitions,[6000])
   self.assertEqual(len(pages),2)
'''
t.write_text(s,encoding='utf-8')
