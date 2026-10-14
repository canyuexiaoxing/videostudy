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

def audit_outline(raw,hints):
    errors=[]
    def titles(node):
        result=[]
        for child in node.get('children',[]):
            if isinstance(child,dict):result.append(_key(child.get('title','')));result.extend(titles(child))
        return result
    def visit(node,depth=0):
        if not isinstance(node,dict) or depth>12:return
        for hint in hints:
            if hint['imageId'] not in node.get('imageIds',[]):continue
            if not any(_key(label)==_key(node.get('title','')) for label in hint['parentLabels']):continue
            visible=titles(node)
            missing=[h for h in hint['headings'] if not any(_key(h)==t or (_key(h) and _key(h) in t) for t in visible)]
            if missing:errors.append('课件分类待核对：'+str(node.get('title'))+' 缺少子节点 '+ '、'.join(missing)+'；依据 '+hint['imageId'])
        for child in node.get('children',[]):visit(child,depth+1)
    for node in raw.get('children',[]):visit(node)
    return list(dict.fromkeys(errors))
