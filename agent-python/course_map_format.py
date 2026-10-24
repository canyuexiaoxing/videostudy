"""Serialization instructions only; no node construction or content selection."""
import json
from copy import deepcopy

FORMAT_EXAMPLE = {
    'topic': '<whole-course title>',
    'children': [{
        'title': '<existing knowledge heading>', 'kind': 'method',
        'candidateIds': ['<supplied knowledge candidate ID>'],
        'sourceIds': ['<supplied speech evidence ID>'], 'imageIds': [],
        'details': [{'title': r'<condition and formula, for example \(x^2\)>',
                     'kind': 'condition', 'sourceIds': ['<supplied speech evidence ID>'], 'imageIds': []}],
        'children': []
    }],
    'examples': [{'title': '<existing worked-example heading>',
                  'candidateIds': ['<supplied example candidate ID>'],
                  'sourceIds': ['<supplied speech evidence ID>'], 'imageIds': []}],
    'uncertainties': []
}
# The pre-existing hierarchy illustration, serialized with the same nodes,
# kinds, details and parent-child order instead of pseudo-JSON.
HIERARCHY_EXAMPLE = {'children': [{
    'title':'模块','kind':'category','sourceIds':[],'imageIds':[],'details':[],
    'children':[{'title':'分类方法','kind':'method','sourceIds':[],'imageIds':[],
                 'details':[{'title':'条件','kind':'condition','sourceIds':[],'imageIds':[]}],
                 'children':[{'title':'独立公式','kind':'formula','sourceIds':[],
                              'imageIds':[],'details':[],'children':[]}]}]
}]}
FORMAT_RULES = r'''
JSON_OUTPUT_FORMAT_V2: The following rules govern serialization ONLY.
All existing evidence, content, hierarchy, classification and coverage requirements remain unchanged.
Return exactly one complete JSON object, with no text before or after it.
Use double quotes for every key and string. Separate object members and array
items with commas; do not leave trailing commas. Close each string, array and
object in nesting order. Never repeat a key within the same object. Put all
children of a node inside its one children array, retaining their intended order.
Types: topic/title/reason/kind are strings; children/examples/details are arrays
of objects; sourceIds/imageIds/candidateIds/uncertainties are arrays of strings;
mergeEvidence is an object when present; candidateDecisions is an array of objects
when present. Keep optional fields optional; do not invent content to fill them.
children is recursive; preserve every supported level. These type rules and the
example do not determine the number, depth or placement of knowledge nodes,
details or worked examples. Do not omit, merge, shorten or reclassify course
content merely to simplify JSON. Retain the existing node and depth budgets.
Inside a JSON string, encode each literal backslash as two backslashes, each
literal quote as an escaped quote, and each literal newline as \n. In particular,
LaTeX backslashes must be JSON-escaped: the actual mathematical string
\(\frac{a}{b}\) is serialized as "\\(\\frac{a}{b}\\)".
Do not turn LaTeX \frac, \theta or \begin into JSON control characters.
Every angle-bracket placeholder in the example is illustrative, never an ID or
course claim to copy. Use actual supplied evidence IDs and actual course content.
The recursive JSON Schema below is the single field/type contract for serialization.
It does not select course content or change the existing teaching hierarchy.
The complete JSON example is illustrative, not a required node count or outline.
Do not interpret other human-readable field sketches as output examples.
Write arrays and objects in nesting order, preferably with one member per line.
At the root, write topic, then the complete children array, then examples, then
uncertainties and optional root fields. Close the root only after every field.
Do not append a sibling node after its parent array or root has been closed.
'''


COMPLETION_CHECK = r"""
JSON_COMPLETION_CHECK_V2 (serialization only, not course organization):
Before sending, check that the entire response is exactly one JSON document.
Do not close the root object until topic, children, examples, uncertainties and
any optional root fields are fully written INSIDE that same root object.
Finish each nested node inside its existing children/details/examples array;
closing a child object must not close its parent array or the course root.
After an array, separate the next field in the SAME object with a comma.
After the final root closing brace, write whitespace only, never another field,
comma, bracket, object, Markdown fence or explanation. Balance delimiters outside
JSON strings; braces in quoted LaTeX are string content, not object boundaries.
Keep all nodes, formulas, examples, references and their original hierarchy.
Do not truncate, summarize or drop any content to make the document end early.
Do this check internally; do not print a checklist or regenerate an outline.
"""


# Describes existing wire fields only. No node quotas, title limits, kind
# restrictions or required optional metadata are introduced by this contract.
_STRING_LIST={'type':'array','items':{'type':'string'}}
_NODE={'$ref':'#/$defs/node'}
OUTPUT_SCHEMA={
 'type':'object','required':['topic','children','examples','uncertainties'],
 'properties':{'topic':{'type':'string'},'children':{'type':'array','items':_NODE},
  'examples':{'type':'array','items':_NODE},'uncertainties':deepcopy(_STRING_LIST),
  'candidateDecisions':{'type':'array','items':{'type':'object','properties':{
   'candidateIds':deepcopy(_STRING_LIST),'target':{'type':'string'},'reason':{'type':'string'},
   'sourceIds':deepcopy(_STRING_LIST),'imageIds':deepcopy(_STRING_LIST)},'additionalProperties':True}}},
 'additionalProperties':True,
 '$defs':{'node':{'type':'object','required':['title'],'properties':{
  'title':{'type':'string'},'kind':{'type':'string'},
  'candidateIds':deepcopy(_STRING_LIST),'sourceIds':deepcopy(_STRING_LIST),'imageIds':deepcopy(_STRING_LIST),
  'details':{'type':'array','items':_NODE},'children':{'type':'array','items':_NODE},
  'mergeEvidence':{'type':'object','properties':{'reason':{'type':'string'},
   'sourceIds':deepcopy(_STRING_LIST),'imageIds':deepcopy(_STRING_LIST)},'additionalProperties':True}},
  'additionalProperties':True}}
}
UNIFIED_EXAMPLE=deepcopy(FORMAT_EXAMPLE)
UNIFIED_EXAMPLE['children']=deepcopy(HIERARCHY_EXAMPLE['children'])

def format_instructions(base, hierarchy):
    # Keep teaching requirements verbatim; only replace grammar sketches.
    start=base.index('Return JSON {topic, children:')
    end=base.index('Use [] for absent',start)
    base=base[:start]+'Return the fields defined by the serialization contract below. '+base[end:]
    marker='递归结构示意（不是课程内容）：'
    semantic=hierarchy[:hierarchy.index(marker)]
    return (base+semantic+FORMAT_RULES+'\nBEGIN_JSON_FIELD_SCHEMA\n'
            +json.dumps(OUTPUT_SCHEMA,ensure_ascii=False)+'\nEND_JSON_FIELD_SCHEMA\n'
            +'BEGIN_COMPLETE_JSON_EXAMPLE\n'+json.dumps(UNIFIED_EXAMPLE,ensure_ascii=False,indent=2)
            +'\nEND_COMPLETE_JSON_EXAMPLE\n'+COMPLETION_CHECK)
