"""Lossless, request-only encoding of repetitive timestamped evidence."""


def _table(items):
    if not isinstance(items, list) or len(items) < 2 or not all(isinstance(i, dict) for i in items):
        return items
    columns = list(items[0])
    if not all(set(i) == set(columns) for i in items):
        return items  # Preserve heterogeneous/optional fields exactly.
    return {"columns": columns, "rows": [[item[key] for key in columns] for item in items]}


def compact_payload(payload: dict) -> dict:
    """Keep every text, timestamp, duplicate occurrence and non-evidence field.

    Internal processing and saved results keep their existing dictionaries.
    Only the model request receives column/row tables and shared OCR strings.
    """
    result = dict(payload)
    changed = False
    for key in ("transcript", "ocrLines"):
        if key in payload:
            table = _table(payload[key])
            result[key] = table
            changed |= table is not payload[key]
    frames = payload.get("ocrFrames")
    if (isinstance(frames, list) and len(frames) > 1 and
            all(isinstance(f, dict) and set(f) == {"frameTimeMs", "texts"} and
                isinstance(f["texts"], list) and all(isinstance(t, str) for t in f["texts"])
                for f in frames)):
        dictionary = []
        indices = {}
        rows = []
        for frame in frames:
            text_ids = []
            for text in frame["texts"]:
                if text not in indices:
                    indices[text] = len(dictionary)
                    dictionary.append(text)
                text_ids.append(indices[text])
            rows.append([frame["frameTimeMs"], text_ids])
        result["ocrTextDictionary"] = dictionary
        result["ocrFrames"] = {"columns": ["frameTimeMs", "textIds"], "rows": rows}
        changed = True
    if changed:
        result["evidenceEncoding"] = "tables-v1"
    return result
