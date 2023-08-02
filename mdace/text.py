import dataclasses
import re
from typing import List, Callable

from mdace.data import Span, Annotation, Admission

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE | re.MULTILINE | re.DOTALL)


def tokenize(text: str) -> List[Span]:
    """Tokenizer used in the paper"""

    # lowercase, drop punct and white space
    matches = TOKEN_PATTERN.finditer(text.lower())

    spans = [Span(*match.span(), covered_text=match.group()) for match in matches]

    # exclude numbers > 10, per mullenbach
    spans = [
        span
        for span in spans
        if not span.covered_text.isdigit() or int(span.covered_text) <= 10
    ]

    return spans


def tokenize_annotation(
    annotation: Annotation, tokenize_fn: Callable[[str], List[Span]]
) -> List[Annotation]:
    if annotation.span.covered_text is None:
        raise ValueError(
            "Cannot tokenize annotations without text -- run inject-note-text.py"
        )

    token_offset = annotation.span.begin

    return [
        dataclasses.replace(
            annotation,
            span=dataclasses.replace(
                span, begin=token_offset + span.begin, end=token_offset + span.begin
            ),
        )
        for span in tokenize_fn(annotation.span.covered_text)
    ]


def tokenize_annotations(
    annotations: List[Annotation], tokenize_fn: Callable[[str], List[Span]]
) -> List[Annotation]:
    flat = list()
    for a in annotations:
        flat.extend(tokenize_annotation(a, tokenize_fn))
    return flat


def tokenize_admission(
    admission: Admission, tokenize_fn: Callable[[str], List[Span]]
) -> Admission:
    return dataclasses.replace(
        admission,
        notes=[
            dataclasses.replace(
                note, annotations=tokenize_annotations(note.annotations, tokenize_fn)
            )
            for note in admission.notes
        ],
    )
