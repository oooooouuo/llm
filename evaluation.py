"""Strict final JSON sense-ID evaluation; no substring or digit matching."""
import json
import re

ID_PATTERN = re.compile(r'(?:bn:\d+[a-z]|[^\s,%]+%\d+:\d+:\d+::)\Z')


def gold_ids(value):
    """Accept comma/whitespace-separated full identifiers, preserving case."""
    if not isinstance(value, str):
        return set()
    return {part for part in re.split(r'[,\s]+', value.strip()) if ID_PATTERN.fullmatch(part)}


def parse_final_id(response):
    if not isinstance(response, str) or not response.strip():
        return None
    text = response.strip()
    if text.endswith('```'):
        text = text[:-3].rstrip()
    decoder = json.JSONDecoder()
    for position in reversed([m.start() for m in re.finditer(r'\{', text)]):
        try:
            result, length = decoder.raw_decode(text[position:])
        except ValueError:
            continue
        if text[position + length:].strip():
            continue
        if isinstance(result, dict) and set(result) == {'sense_id'}:
            prediction = result['sense_id']
            if isinstance(prediction, str) and ID_PATTERN.fullmatch(prediction):
                return prediction
        return None
    return None


def exact_match(response, truth):
    prediction = parse_final_id(response)
    return prediction is not None and prediction in gold_ids(truth)
