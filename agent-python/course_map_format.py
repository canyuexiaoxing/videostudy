"""Serialization instructions only; no node construction or content selection."""
import json

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
JSON_OUTPUT_FORMAT_V1: The following rules govern serialization ONLY.
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
Valid JSON serialization example (not a required node count or course outline):
'''


def format_instructions(base, hierarchy):
    # Replace only informal grammar sketches; preserve the teaching requirements.
    start=base.index('Return JSON {topic, children:')
    end=base.index('Use [] for absent',start)
    base=base[:start]+'Return the fields illustrated by the valid JSON example below. '+base[end:]
    marker='递归结构示意（不是课程内容）：'
    semantic=hierarchy[:hierarchy.index(marker)]
    return (base+semantic+marker+json.dumps(HIERARCHY_EXAMPLE,ensure_ascii=False)+'。\n'
            +FORMAT_RULES+json.dumps(FORMAT_EXAMPLE,ensure_ascii=False))
