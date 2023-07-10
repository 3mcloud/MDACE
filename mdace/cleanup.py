import dataclasses
import logging
import string
from pathlib import Path
from typing import List, Callable

from mdace.data import Annotation, Note, Admission, MDACEData, Span

_logger = logging.getLogger(Path(__file__).name)

_NON_BREAKING_CHARS = set(string.punctuation) | set(string.whitespace)


def _is_non_breaking(connecting: str) -> bool:
    return all((c in _NON_BREAKING_CHARS for c in connecting))


def _merge(left: Annotation, right: Annotation, note_text: str) -> Annotation:
    """merge left and right annotations"""
    new_begin = left.span.begin
    new_end = right.span.end

    if left.span.covered_text:
        covered_text = note_text[new_begin:new_end]
    else:
        covered_text = None

    new_span = Span(begin=new_begin, end=new_end, covered_text=covered_text)

    return dataclasses.replace(left, span=new_span)


def _merge_adjacent(annotations: List[Annotation], note_text: str) -> List[Annotation]:
    if len(annotations) < 2:
        return annotations

    order_ensured = sorted(annotations, key=lambda a: a.span.begin)

    merged = [order_ensured.pop(0)]

    for current in order_ensured:
        previous = merged[-1]
        if previous.billing_code == current.billing_code and _is_non_breaking(
            note_text[previous.span.end : current.span.begin]
        ):
            merged[-1] = _merge(previous, current, note_text)
        else:
            merged.append(current)

    return merged


def merge_adjacent_in_note(note: Note) -> Note:
    if len(note.annotations) < 2:
        return note

    new_annos = _merge_adjacent(note.annotations, note.text)

    if len(new_annos) < len(note.annotations):
        return dataclasses.replace(note, annotations=new_annos)
    else:
        return note


TRIM_CHARS = set("-.,/ \n\t")
TRIM_L_CHARS = set(")") | TRIM_CHARS
TRIM_R_CHARS = set("(") | TRIM_CHARS


def _do_trim(text: str, span: Span) -> Span:
    new_begin = span.begin
    while new_begin < span.end:
        char = text[new_begin]
        if char in TRIM_L_CHARS:
            new_begin += 1
        else:
            break

    new_end = span.end
    while new_end > new_begin:
        char = text[new_end - 1]
        if char in TRIM_R_CHARS:
            new_end -= 1
        else:
            break

    new_covered_text = None
    if span.covered_text:
        new_covered_text = text[new_begin:new_end]

    return Span(begin=new_begin, end=new_end, covered_text=new_covered_text)


def trim_annotations_in_note(note: Note) -> Note:
    new_annos = list()
    for current in note.annotations:
        new_span = _do_trim(note.text, current.span)
        if new_span != current.span:
            if len(new_span) == 0:
                _logger.error(
                    "All characters stripped from %s in note_id=%d",
                    current,
                    note.note_id,
                )
            trimmed = dataclasses.replace(current, span=new_span)
            new_annos.append(trimmed)
        else:
            new_annos.append(current)
    return dataclasses.replace(note, annotations=new_annos)


def _map_notes(mdace: MDACEData, map_fn: Callable[[Note], Note]):
    def map_adm(adm: Admission) -> Admission:
        return dataclasses.replace(
            adm,
            notes=[map_fn(note) for note in adm.notes],
        )

    return MDACEData(admissions=[map_adm(admission) for admission in mdace.admissions])


def merge_adjacent_annotations(mdace: MDACEData) -> MDACEData:
    return _map_notes(mdace, merge_adjacent_in_note)


def trim_annotations(mdace: MDACEData) -> MDACEData:
    return _map_notes(mdace, trim_annotations_in_note)
