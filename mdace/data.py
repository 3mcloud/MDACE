import dataclasses
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Dict, Tuple, Optional

_logger = logging.getLogger(Path(__file__).name)


@dataclass(frozen=True)
class Span:
    begin: int
    end: int

    covered_text: Optional[str] = dataclasses.field(compare=False, default=None)

    def __len__(self) -> int:
        return self.end - self.begin

    @staticmethod
    def from_note_text(begin: int, end: int, note_text: str):
        return Span(begin, end, note_text[begin:end])


@dataclass(frozen=True)
class BillingCode:
    code: str
    code_system: str
    code_description: Optional[str] = dataclasses.field(compare=False, default=None)


@dataclass(frozen=True)
class Annotation:
    span: Span
    billing_code: BillingCode
    type: Optional[str] = dataclasses.field(compare=False, default=None)

    @staticmethod
    def from_json_dict(data: Dict) -> "Annotation":
        return Annotation(
            span=Span(
                begin=data.pop("begin"),
                end=data.pop("end"),
                covered_text=data.pop("covered_text", None),
            ),
            billing_code=BillingCode(
                data.pop("code"), data.pop("code_system"), data.pop("description", None)
            ),
            **data,
        )


@dataclass(frozen=True)
class Note:
    note_id: int
    category: str
    description: str
    annotations: List[Annotation] = dataclasses.field(repr=False)

    text: Optional[str] = dataclasses.field(repr=False, default=None)

    @staticmethod
    def from_json_dict(data: Dict) -> "Note":
        return Note(
            text=data.pop("text", None),
            annotations=[Annotation.from_json_dict(a) for a in data.pop("annotations")],
            **data,
        )


@dataclass(frozen=True)
class Admission:
    hadm_id: int
    notes: List[Note]

    comment: str = None

    def _has_text(self):
        """Check that all notes have text"""
        return not any(note.text is None for note in self.notes)

    @staticmethod
    def from_json_dict(data: Dict) -> "Admission":
        return Admission(
            notes=[Note.from_json_dict(note) for note in data.pop("notes")],
            **data,
        )

    @staticmethod
    def from_json_file(file_path: Path) -> "Admission":
        with open(file_path, "r", encoding="utf8") as ifp:
            return Admission.from_json_dict(json.load(ifp))


@dataclass(frozen=True)
class MDACEData:
    admissions: List[Admission]

    @property
    def __len__(self) -> int:
        return sum((1 for _ in iter(self)))

    @staticmethod
    def from_dir(dataset_dir: Path, require_text: bool = True) -> "MDACEData":
        try:
            next(dataset_dir.glob("*.json"))
        except StopIteration:
            raise ValueError(f"No JSON files found in path {dataset_dir.absolute()}")

        admissions = list()
        for json_file in dataset_dir.glob("*.json"):
            with open(json_file, "r", encoding="utf8") as ifp:
                adm = Admission.from_json_dict(json.load(ifp))
                if require_text and not adm._has_text():
                    raise ValueError(
                        f"Admission {adm.hadm_id} is missing note text. "
                        f"Please run: python inject-note-text.py --noteevents NOTEEVENTS.csv --data-dir {dataset_dir}"
                    )
                admissions.append(adm)

        return MDACEData(admissions)

    def __iter__(self) -> Iterator[Tuple[Admission, Note, Annotation]]:
        """Iterate over Annotations; include information from Admission and Note"""
        for admission in self.admissions:
            for note in admission.notes:
                for annotation in note.annotations:
                    # set annotation.span.covered_text if we have note.text
                    if note.text and not annotation.span.covered_text:
                        annotation = dataclasses.replace(
                            annotation,
                            span=dataclasses.replace(
                                annotation.span,
                                covered_text=note.text[
                                    annotation.span.begin : annotation.span.end
                                ],
                            ),
                        )
                    yield admission, note, annotation
