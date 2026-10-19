from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def edit(name,old,new):
 path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
 if text.count(old)!=1:raise RuntimeError(f'expected one edit target {name}: {old[:75]}')
 path.write_text(text.replace(old,new),encoding='utf-8')
edit('agent-python/slide_grouping.py','def _preview(path: Path) -> np.ndarray:','def _preview(path: Path, dimensions=None) -> np.ndarray:')
edit('agent-python/slide_grouping.py','    return cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)','    if dimensions is not None:dimensions[int(path.stem)]=(int(image.shape[1]),int(image.shape[0]))\n    return cv2.resize(image, (320, 180), interpolation=cv2.INTER_AREA)')
edit('agent-python/slide_grouping.py','                on_page: Callable[[dict], None] | None = None) -> tuple[list[dict], list[int]]:','                on_page: Callable[[dict], None] | None = None, person_selection_mode=None,\n                hold_occluded_tail=False) -> tuple[list[dict], list[int]]:')
edit('agent-python/slide_grouping.py','    images = {time: _preview(keyframe_dir / f"{time}.jpg") for time in times}\n    dimensions = {}','''    from person_visibility import enabled
    use_person=enabled(person_selection_mode)
    dimensions = {}
    images = {time: (_preview(keyframe_dir / f"{time}.jpg",dimensions) if use_person else _preview(keyframe_dir / f"{time}.jpg")) for time in times}
    person=None
    if use_person:
        from person_grouping import PersonGrouping
        person=PersonGrouping(Path(keyframe_dir),dimensions,masks)
''')
edit('agent-python/slide_grouping.py','            original=cv2.imread(str(keyframe_dir / f"{frame[\'frameTimeMs\']}.jpg"),cv2.IMREAD_GRAYSCALE)\n            height,width=original.shape','''            if frame['frameTimeMs'] in dimensions:
                width,height=dimensions[frame['frameTimeMs']]
            else:
                original=cv2.imread(str(keyframe_dir / f"{frame['frameTimeMs']}.jpg"),cv2.IMREAD_GRAYSCALE)
                height,width=original.shape''')
edit('agent-python/slide_grouping.py','    pages: list[dict] = []\n    def publish','    pages: list[dict] = []\n    protected_times=set()\n    pending=[]\n    def publish')
edit('agent-python/slide_grouping.py','        pages.append(page)\n        if on_page is not None:','''        protect=protected_times&set(page['memberFrameTimesMs'])
        if protect:page['representativeFrameTimesMs']=sorted(set(page['representativeFrameTimesMs'])|protect)
        pages.append(page)
        if on_page is not None:''')
edit('agent-python/slide_grouping.py','    pending_transition = False\n    for current in frames:','''    pending_transition = False
    def flush_pending(merge):
        nonlocal members,pending
        if not pending:return
        if merge:
            protected_times.update(_page(members,images,decision,reason,0,masks)['representativeFrameTimesMs'])
            protected_times.update(f['frameTimeMs'] for f in pending)
            members.extend(pending)
        else:
            if members:publish(members,decision,reason);members=[]
            for f in pending:publish([f],'auto_new_page','person occlusion unresolved; conservatively split')
        pending=[]
    for current in frames:''')
edit('agent-python/slide_grouping.py','        blank = _blank(current, current_image, mask)','        blank = _blank(current, current_image, mask)\n        if person is not None and person.has_person(time_ms):blank=False')
edit('agent-python/slide_grouping.py','        if blank:\n            transitions.append(time_ms)','        if blank:\n            flush_pending(False)\n            transitions.append(time_ms)')
edit('agent-python/slide_grouping.py','            boundary_reason = "local OCR and frame comparison"\n            if boundary == "uncertain":','''            boundary_reason = "local OCR and frame comparison"
            masked=None
            if person is not None:
                masked=person.decide(compare_anchor,compare_previous,compare_current,images,comparison_mask,boundary,_boundary,_texts,_retention,_normalized)
                if masked is not None:boundary=masked['boundary'];boundary_reason=masked['reason']
            if boundary=='defer':
                pending.append(current)
                from person_grouping import MAX_PENDING_FRAMES
                if len(pending)>MAX_PENDING_FRAMES:flush_pending(False)
                continue
            if boundary=='same' and pending:flush_pending(True)
            elif pending:
                flush_pending(False)
            if masked is not None and boundary=='same':
                if members:protected_times.update(_page(members,images,decision,reason,0,masks)['representativeFrameTimesMs'])
                protected_times.add(time_ms)
            if boundary == "uncertain":''')
# flush_pending(False) can already have published the active page.
edit('agent-python/slide_grouping.py','            if boundary == "new":\n                publish(members, decision, reason)','            if boundary == "new":\n                if members:publish(members, decision, reason)')
edit('agent-python/slide_grouping.py','    if members:\n        publish(members, decision, reason)\n    return pages, transitions','''    if pending:
        if hold_occluded_tail:
            publish([*members,*pending],decision,'person occlusion pending; provisional tail')
            members=[];pending=[]
        else:flush_pending(False)
    if members:
        publish(members, decision, reason)
    if person is not None:person.finish(pages)
    return pages, transitions''')
edit('agent-python/slide_grouping.py','    def __init__(self, keyframe_dir: Path, ignore_region=None):','    def __init__(self, keyframe_dir: Path, ignore_region=None, person_selection_mode=None):')
edit('agent-python/slide_grouping.py','        self.ignore_region = normalize_region(ignore_region)\n        self._pending','        self.ignore_region = normalize_region(ignore_region)\n        self.person_selection_mode=person_selection_mode\n        self._pending')
edit('agent-python/slide_grouping.py','    def _groups(self):\n        return group_pages','    def _groups(self,final=False):\n        from person_visibility import enabled\n        options={"person_selection_mode":self.person_selection_mode,"hold_occluded_tail":not final} if enabled(self.person_selection_mode) else ({"person_selection_mode":"off"} if self.person_selection_mode=="off" else {})\n        return group_pages')
edit('agent-python/slide_grouping.py','                           ignore_region=self.ignore_region)','                           ignore_region=self.ignore_region,**options)')
edit('agent-python/slide_grouping.py','        pages, _ = self._groups()\n        for page in pages:','        pages, _ = self._groups(final=True)\n        for page in pages:')
