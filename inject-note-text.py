import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict

logger = logging.getLogger(Path(__file__).name)


def inject_note_text(notes_map: Dict[int, str], admission: Dict) -> Dict:
    """Inject text in-place"""
    for note in admission["notes"]:
        text = notes_map[note["note_id"]]
        note["text"] = text
        for annotation in note.get("annotations"):
            annotation["covered_text"] = text[annotation["begin"] : annotation["end"]]

    return admission


def _make_out_path(json_file: Path, input_dir: Path, out_dir: Path) -> Path:
    prefix_len = len(input_dir.parts)
    return out_dir.joinpath(*json_file.parts[prefix_len:])


def inject_and_persist(notes_map: Dict[int, str], data_dir: Path, out_dir: Path):
    """Inject text into admission and persist in ``out_dir``"""
    if out_dir:
        logger.info(f"Injecting text and persisting to {out_dir.absolute()}")
    else:
        logger.info("Injecting text in place")

    for json_file in data_dir.glob("**/*.json"):
        with open(json_file, "r", encoding="utf8") as ifp:
            admission = inject_note_text(notes_map, json.load(ifp))

        if out_dir:
            out_path = _make_out_path(json_file, data_dir, out_dir)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = json_file

        with open(out_path, "w", encoding="utf8") as ofp:
            json.dump(admission, ofp, indent=2)


def build_notes_map(noteevents: Path) -> Dict[int, str]:
    """Mapping from note_id to text constructed from NOTEEVENTS.csv"""
    logger.info(f"Loading {noteevents}")
    id_text_map = dict()
    csv.field_size_limit(sys.maxsize)
    with open(noteevents, "r", encoding="utf8") as ifp:
        reader = csv.reader(ifp)
        # skip header
        # "ROW_ID","SUBJECT_ID","HADM_ID","CHARTDATE","CHARTTIME","STORETIME","CATEGORY","DESCRIPTION","CGID","ISERROR","TEXT"
        next(reader)
        for row in reader:
            note_id, text = int(row[0]), row[10]
            id_text_map[note_id] = text
    return id_text_map


def main(args: argparse.Namespace):
    notes_map = build_notes_map(args.noteevents)
    inject_and_persist(notes_map, args.data_dir, args.out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--noteevents", help="Path to NOTEEVENTS.csv", type=Path, required=True
    )
    parser.add_argument(
        "--data-dir",
        help="Path to top level MDACE data directory",
        type=Path,
        default="data",
    )
    parser.add_argument(
        "--out-dir",
        help="Write JSON files with text injected into them",
        type=Path,
        default=None,
    )

    logging.basicConfig(level=logging.INFO)
    main(parser.parse_args())
