"""Shared, evidence-preserving hierarchy contract for both course map modes."""
from copy import deepcopy
from pathlib import Path
import re

STRUCTURE_INSTRUCTIONS = '''
topic 使用整课主题，不要把某张课件的编号标题误当整课标题。
最终导图必须采用同一层级规则：整课主题→知识模块→分类/方法→独立公式或法则。
children 是递归的知识树，不是只允许两层的列表。课件括号、编号、标题表达的
分类和从属关系应保留。每个完整概念、独立方法、公式有入口；不要逐句拆点。
条件、符号含义、操作步骤、易错说明放 details。details.kind 使用 condition、
step、symbol、pitfall、explanation；独立公式/方法请直接放 children，并注明
kind=formula/method/rule/concept/category。每个节点及详情保留真实 sourceIds/imageIds。
例题及其计算全部放 examples，一道题一个入口，不因用到核心知识又建立知识节点。
outlineHints 只是原图 OCR 分类线索，可能有错，必须对照对应原图核实，不可照抄猜测。
返回前逐模块检查：空分类是否遗漏子方法；独立公式是否被错误埋入详情；是否漏掉
课件清楚列出的编号分类；是否将相同概念重复列出。内容不足时标记 uncertainties。
递归结构示意（不是课程内容）：children:[{title:模块,kind:category,sourceIds:[],
imageIds:[],details:[],children:[{title:分类方法,kind:method,sourceIds:[],imageIds:[],
details:[{title:条件,kind:condition,sourceIds:[],imageIds:[]}],children:[{title:独立公式,
kind:formula,sourceIds:[],imageIds:[],details:[],children:[]}]}]}]。
'''
_NUMBER = re.compile(r'^\s*(?:\d+[.．、)）]|[一二三四五六七八九十]+[、.．])\s*')
_EXAMPLE = re.compile(r'例题|本题|这道题|题目分析|题干|代入结果|第[一二三四五六七八九十\d]+题')

def _key(text):
    text = _NUMBER.sub('', str(text))
    text = re.sub(r'给定|已知|给|与|和|及', '', text)
    return re.sub(r'[\W_]+', '', text)

def normalize_reply(raw):
    value = deepcopy(raw)
    def visit(node, depth=0):
        if not isinstance(node, dict) or depth > 12:return
        children = node.get('children', [])
        details = node.get('details', [])
        if not isinstance(children, list) or not isinstance(details, list):return
        kept=[]
        for detail in details:
            if not isinstance(detail,dict):kept.append(detail);continue
            title=detail.get('title','');kind=detail.get('kind')
            independent=kind in ('formula','method','rule','concept','category','classification')
            if kind is None and isinstance(title,str):
                independent=bool(re.match(r'^公式[一二三四五六七八九十\d]+[：:]',title) and '=' in title)
            if independent and not _EXAMPLE.search(str(node.get('title',''))+' '+str(title)):
                child=deepcopy(detail)
                child['title']=re.split(r'[（(](?=已知|适用|条件|其中|当|要求)',title,maxsplit=1)[0].strip()
                child['children']=detail.get('children',[])
                child['details']=[{**deepcopy(detail),'kind':'explanation','children':[]}]
                if not any(isinstance(c,dict) and _key(c.get('title'))==_key(child['title']) for c in children):
                    children.append(child)
                else:kept.append(detail)
            else:kept.append(detail)
        node['children']=children;node['details']=kept
        for child in children:visit(child,depth+1)
    for node in value.get('children',[]):visit(node)
    return value

def outline_hints(visuals,root,regions):
    from ignored_region import filter_frame
    import cv2
    hints=[]
    for frame in visuals:
        ms=frame.get('frameTimeMs');path=Path(root)/f'{ms}.jpg'
        if type(ms) is not int or not path.is_file():continue
        image=cv2.imread(str(path))
        if image is None:continue
        setting=regions.get(str(ms))
        visible=filter_frame(frame,setting,ms,image.shape[1],image.shape[0]) if setting else frame
        texts=[b.get('text','').strip() for b in visible.get('ocrBlocks',[]) if isinstance(b.get('text'),str)]
        headings=list(dict.fromkeys(t for t in texts if _NUMBER.match(t) and len(t)<=60 and not _EXAMPLE.search(t) and not re.search(r'步骤|第一步|第二步|答案|解：|解:',t)))
        parents=list(dict.fromkeys(t for t in texts if not _NUMBER.match(t) and len(t)<=32 and re.search(r'计算|分类|类型|题型|结构|知识体系|方法',t) and not re.search(r'[=：:]|步骤|例题|题干|答案|第.+步',t)))
        if len(headings)>=2 and parents:hints.append(dict(imageId=f'frame_{ms}',parentLabels=parents,headings=headings))
    return hints

# Audit rules only: OCR hints sent to the model and node normalization above are
# deliberately unchanged. A slide-level OCR co-occurrence is not a proven edge.
_AUDIT_NUMBER = re.compile(r'^\s*(?:(\d{1,2})[.．、](?!\d)|(\d{1,2})[)）]|[（(](\d{1,2})[)）])\s*')
_AUDIT_CHINESE = re.compile(r'^\s*([一二三四五六七八九十]+)[、.．]\s*')
_CHINESE_ORDINALS = {word:index for index,word in enumerate(('一','二','三','四','五','六','七','八','九','十'),1)}
_CALCULATION = re.compile(r'[=＝→⇒×÷^{}]|\\(?:frac|times|begin)|\d+\.\d+')
_UNCLEAR = re.compile(r'[?？�□]|\.{3,}|…')
_EXPLICIT_CLASSIFICATION = re.compile(r'分类|类型|种类|类别|分为|classification|types|kinds',re.I)

def _audit_label(text):
    if not isinstance(text,str):return None
    match=_AUDIT_NUMBER.match(text)
    number=next((int(v) for v in match.groups() if v),None) if match else None
    if match:body=text[match.end():].strip()
    else:
        chinese=_AUDIT_CHINESE.match(text)
        number=_CHINESE_ORDINALS.get(chinese.group(1)) if chinese else None
        body=text[chinese.end():].strip() if chinese else text.strip()
    if (not body or _EXAMPLE.search(body) or _CALCULATION.search(body)
        or re.search(r'步骤|第.+步|答案|^解[：:]',body)
        or not re.search(r'[\u4e00-\u9fff]{2}|[A-Za-z]{2}',body)):
        return None
    return number,body

def audit_outline_report(raw,hints):
    """Return clear omissions separately from uncertain OCR review notes.

    Only a clean consecutive numbered list under an explicit classification
    label is strong enough to fail validation. Missing/OCR-corrupt numbering or
    a generic method/calculation heading remains a visible review note. This is
    a conservative textual audit, never a claim of visual relationship proof.
    """
    errors=[];warnings=[];ignored=0
    def nodes(node,depth=0):
        if not isinstance(node,dict) or depth>12:return
        yield node
        children=node.get('children',[])
        if isinstance(children,list):
            for child in children:yield from nodes(child,depth+1)
    def bound_to_branch(branch,hint):
        return any(hint.get('imageId') in node.get('imageIds',[]) and
                   any(_key(label)==_key(node.get('title','')) for label in hint.get('parentLabels',[]))
                   for node in nodes(branch))
    def covered(label,visible):
        # Descriptive labels such as category: member A, member B may already
        # appear as the category heading or the enumerated members in this same
        # knowledge branch. Details/examples/other branches are not substitutes.
        head,*tail=re.split(r'[：:]',label,maxsplit=1)
        key=_key(head).lower()
        def matches(value):
            candidate=_key(value).lower()
            return bool(key) and (candidate==key or (key in candidate and not re.search(r'非|不是|不属于',value)))
        if any(matches(value) for value in visible):return True
        if not tail:return False
        members=[p.strip() for p in re.split(r'[、，,；;]|以及|和|与|及',tail[0]) if p.strip()]
        if len(members)<2:return False
        return all(any(_key(member).lower()==_key(value).lower() for value in visible) for member in members)
    branches=raw.get('children',[]) if isinstance(raw,dict) else []
    for branch in branches:
        if not isinstance(branch,dict):continue
        visible=[str(node.get('title','')) for node in nodes(branch) if node is not branch]
        for hint in hints:
            if not isinstance(hint,dict) or not bound_to_branch(branch,hint):continue
            headings=hint.get('headings',[])
            if not isinstance(headings,list):continue
            labels=[]
            for heading in headings:
                label=_audit_label(heading)
                if label is None:ignored+=1
                else:labels.append((heading,*label))
            if not labels:continue
            missing=[original for original,_,label in labels if not covered(label,visible)]
            if not missing:continue
            numbering=[number for _,number,_ in labels]
            clean_sequence=(len(labels)>=2 and len(labels)==len(headings) and numbering==list(range(1,len(labels)+1)))
            explicit=any(_EXPLICIT_CLASSIFICATION.search(str(label)) for label in hint.get('parentLabels',[]))
            clear=clean_sequence and explicit and not any(_UNCLEAR.search(label) for _,_,label in labels)
            message='课件分类待核对：'+str(branch.get('title'))+' 缺少子节点 '+'、'.join(missing)+'；依据 '+str(hint.get('imageId',''))
            (errors if clear else warnings).append(message if clear else message+'（OCR分类关系不确定，仅供核对）')
    return {'errors':list(dict.fromkeys(errors)),'warnings':list(dict.fromkeys(warnings)),'ignored':ignored}

def audit_outline(raw,hints):
    """Compatibility view for callers displaying all classification findings."""
    report=audit_outline_report(raw,hints)
    return report['errors']+report['warnings']
