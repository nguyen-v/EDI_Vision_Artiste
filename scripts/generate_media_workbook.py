#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate MediaMap_workbook.xlsx for Vision Artiste quiz (English UI).

Sheets:
  Guide       - how to use, limits, tie-break
  Questions   - quiz mapping (editable screen + profiles); drives CodeGen
  SD WIZ1     - files for portrait display (1080x1920)
  SD WIZ2     - files for landscape display (1920x1080)
  CodeGen     - paste block for QuestionnaireConfig.h

Usage:
    python scripts/generate_media_workbook.py
    python scripts/generate_media_workbook.py --emit-cpp
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NUM_LANGUAGES = 4
FILES_PER_LANGUAGE = 32
MEDEWIZ_MAX_FILES = 200
NUM_CHOICES = 4
# Initial quiz steps baked into a new workbook (edit or add rows on Questions sheet).
DEFAULT_NUM_QUESTIONS = 13
# Extra blank rows with formulas ready (fill the next row to add a step).
MAX_QUESTION_SLOTS = 24
LANG_CODES = ("EN", "FR", "DE", "IT")
CAT_NAMES = ("Emotions", "Realiste", "Matiere", "Conteur")
CAT_CPP = ("CAT_EMOTIONS", "CAT_REALISTE", "CAT_MATIERE", "CAT_CONTEUR")

QUESTION_FILE_FIRST_OFFSET = 1
# Artwork uses the same SD index as question text offset (separate cards, no collision).
QUESTION_IMAGE_OFFSET_DELTA = 0

QUESTION_SCREEN_ORDER = "lppllllpllplp"

PORTRAIT_ASPECT = "1080x1920"
LANDSCAPE_ASPECT = "1920x1080"

QUESTIONS_FIRST_ROW = 4
QUESTIONS_LAST_ROW = QUESTIONS_FIRST_ROW + MAX_QUESTION_SLOTS - 1

# Questions columns (1-based)
COL_QNUM = 1
COL_ARTWORK = 2
COL_QUESTION_ON = 3
COL_ARTWORK_ON = 4
COL_TEXT_OFFSET = 5
COL_IMAGE_INDEX = 6
COL_B1 = 7
COL_TEXT_PLAYER = 11
COL_ART_PLAYER = 12
COL_TEXT_ASPECT = 13
COL_ART_ASPECT = 14
COL_TEXT_FILE_FR = 15
COL_ART_FILE = 16

HIDDEN_CAT_COLS = ("R", "S", "T", "U")
HIDDEN_LINE_COL = "V"

CODEGEN_BEGIN_ROW = 4
CODEGEN_NUM_QUESTIONS_ROW = 5
CODEGEN_ARRAY_OPEN_ROW = 6
CODEGEN_FIRST_Q_ROW = 7
CODEGEN_LAST_Q_ROW = CODEGEN_FIRST_Q_ROW + MAX_QUESTION_SLOTS - 1
CODEGEN_CLOSE_ROW = CODEGEN_LAST_Q_ROW + 1
CODEGEN_END_MARKER_ROW = CODEGEN_CLOSE_ROW + 1
COPY_BLOCK_FIRST_ROW = 4
COPY_BLOCK_LAST_ROW = CODEGEN_END_MARKER_ROW

WIZ1_FIRST_ROW = 4
WIZ2_FIRST_ROW = 4

TITLE_FILL = PatternFill("solid", fgColor="2F5496")
TITLE_FONT = Font(bold=True, size=14, color="FFFFFF")
INSTRUCTION_FILL = PatternFill("solid", fgColor="F8F9FA")
INSTRUCTION_FONT = Font(size=10, color="404040")
EDIT_FILL = PatternFill("solid", fgColor="E2EFDA")
EDIT_HEADER_FILL = PatternFill("solid", fgColor="C6E0B4")
INPUT_FILL = PatternFill("solid", fgColor="F2F2F2")
INPUT_HEADER_FILL = PatternFill("solid", fgColor="D9D9D9")
CALC_FILL = PatternFill("solid", fgColor="DDEBF7")
FILE_HEADER_FILL = PatternFill("solid", fgColor="9BC2E6")
COPY_FILL = PatternFill("solid", fgColor="FFF2CC")
SECTION_FONT = Font(bold=True, size=11, color="2F5496")
HEADER_FONT = Font(bold=True, color="1F3864")
DATA_FONT = Font(size=11)
DATA_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
UNLOCKED = Protection(locked=False)
LOCKED = Protection(locked=True)

SCREEN_LIST = "Portrait,Landscape"
PROFILE_LIST = ",".join(CAT_NAMES)


def screen_from_order_char(ch: str) -> str:
    return "Landscape" if ch.lower() == "l" else "Portrait"


_SCREEN = [screen_from_order_char(c) for c in QUESTION_SCREEN_ORDER]
assert len(_SCREEN) == DEFAULT_NUM_QUESTIONS

# (categories, question_on_screen, artwork_title) ? SD file index = step number (hidden)
DEFAULT_QUESTIONS: Tuple[Tuple[Tuple[int, ...], str, str], ...] = (
    ((0, 1, 2, 3), _SCREEN[0], "Caravaggio - Supper at Emmaus"),
    ((3, 1, 2, 0), _SCREEN[1], "Monet - Rouen Cathedrals"),
    ((0, 1, 2, 3), _SCREEN[2], "Magritte - Empire of Light"),
    ((0, 1, 2, 3), _SCREEN[3], "Delaunay / Kirchner - night landscape"),
    ((0, 1, 2, 3), _SCREEN[4], "Van Gogh - Starry Night"),
    ((0, 3, 2, 1), _SCREEN[5], "Hopper - Nighthawks (Q6A)"),
    ((1, 2, 3, 0), _SCREEN[6], "Hopper - Night Windows (Q6B)"),
    ((2, 3, 1, 0), _SCREEN[7], "Photo - Sudek / Brassai (Q7)"),
    ((0, 3, 1, 2), _SCREEN[8], "Fuseli - The Nightmare"),
    ((2, 3, 1, 0), _SCREEN[9], "Soulages - Outrenoir"),
    ((0, 3, 1, 2), _SCREEN[10], "Vallotton - The Bibliophile"),
    ((1, 0, 2, 3), _SCREEN[11], "Grandville - Cast Shadows"),
    ((0, 3, 1, 2), _SCREEN[12], "Your work - final 4 motifs Q12"),
)

WIZ1_FIXED_ROWS = (
    ("Idle intro text", "-", 0, "Title + intro (all languages)", PORTRAIT_ASPECT),
    ("Profile Emotions", "-", 17, "Result text - poetic / emotions", PORTRAIT_ASPECT),
    ("Profile Realiste", "-", 18, "Result text - precision", PORTRAIT_ASPECT),
    ("Profile Matiere", "-", 19, "Result text - matter", PORTRAIT_ASPECT),
    ("Profile Conteur", "-", 20, "Result text - storyteller", PORTRAIT_ASPECT),
)

WIZ2_FIXED_ROWS = (
    ("Idle artwork", "-", 0, "Intro visual landscape (all languages)", LANDSCAPE_ASPECT),
    ("Profile art Emotions", "-", 17, "Result visual - emotions", LANDSCAPE_ASPECT),
    ("Profile art Realiste", "-", 18, "Result visual - precision", LANDSCAPE_ASPECT),
    ("Profile art Matiere", "-", 19, "Result visual - matter", LANDSCAPE_ASPECT),
    ("Profile art Conteur", "-", 20, "Result visual - storyteller", LANDSCAPE_ASPECT),
)


def role_has_language_files(role: str) -> bool:
    if role.startswith("Question text") or role.startswith("Idle intro"):
        return True
    return role.startswith("Profile") and not role.startswith("Profile art")


def placement(question_on: str) -> Tuple[str, str, str, str]:
    """Return text_wiz, art_wiz, text_aspect, art_aspect."""
    if question_on == "Portrait":
        return "WIZ1", "WIZ2", PORTRAIT_ASPECT, LANDSCAPE_ASPECT
    return "WIZ2", "WIZ1", LANDSCAPE_ASPECT, PORTRAIT_ASPECT


def build_sd_slot_rows() -> Tuple[List[Tuple], List[Tuple]]:
    """Build SD WIZ1 and WIZ2 row tuples from DEFAULT_QUESTIONS."""
    wiz1: List[Tuple] = list(WIZ1_FIXED_ROWS)
    wiz2: List[Tuple] = list(WIZ2_FIXED_ROWS)

    for i, (_cats, question_on, artwork) in enumerate(DEFAULT_QUESTIONS):
        qref = f"Q{i + 1}"
        offset = i + 1
        image_idx = offset + QUESTION_IMAGE_OFFSET_DELTA
        text_wiz, art_wiz, text_asp, art_asp = placement(question_on)

        if text_wiz == "WIZ1":
            wiz1.append((
                f"Question text {qref}",
                qref,
                offset,
                f"{artwork} (question on portrait screen)",
                text_asp,
            ))
        else:
            wiz2.append((
                f"Question text {qref}",
                qref,
                offset,
                f"{artwork} (question on landscape screen)",
                text_asp,
            ))

        if art_wiz == "WIZ1":
            wiz1.append((
                f"Artwork {qref}",
                qref,
                image_idx,
                f"{artwork} (art on portrait screen)",
                art_asp,
            ))
        else:
            wiz2.append((
                f"Artwork {qref}",
                qref,
                image_idx,
                f"{artwork} (art on landscape screen)",
                art_asp,
            ))

    wiz1.sort(key=lambda r: (r[2] if isinstance(r[2], int) else 999))
    wiz2.sort(key=lambda r: (r[2] if isinstance(r[2], int) else 999))
    return wiz1, wiz2


WIZ1_SD_ROWS, WIZ2_SD_ROWS = build_sd_slot_rows()
WIZ1_LAST_ROW = WIZ1_FIRST_ROW + len(WIZ1_SD_ROWS) - 1
WIZ2_LAST_ROW = WIZ2_FIRST_ROW + len(WIZ2_SD_ROWS) - 1


def set_col_widths(ws: Worksheet, widths: Sequence[float]) -> None:
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width


def apply_cell_style(cell, *, fill=None, font=None, alignment=None, border=None, locked=True):
    if fill is not None:
        cell.fill = fill
    if font is not None:
        cell.font = font
    if alignment is not None:
        cell.alignment = alignment
    if border is not None:
        cell.border = border
    cell.protection = LOCKED if locked else UNLOCKED


def enable_sheet_protection(ws: Worksheet) -> None:
    ws.protection.sheet = True
    ws.protection.selectLockedCells = False
    ws.protection.selectUnlockedCells = False


def style_merged_title(ws, cell_ref, merge_range):
    ws.merge_cells(merge_range)
    cell = ws[cell_ref]
    cell.font = TITLE_FONT
    cell.fill = TITLE_FILL
    cell.alignment = Alignment(vertical="center", wrap_text=True)


def style_instruction_row(ws, cell_ref, merge_range):
    ws.merge_cells(merge_range)
    cell = ws[cell_ref]
    cell.font = INSTRUCTION_FONT
    cell.fill = INSTRUCTION_FILL
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def add_list_validation(ws: Worksheet, cell_range: str, options: str) -> None:
    dv = DataValidation(
        type="list",
        formula1=f'"{options}"',
        allow_blank=False,
        showDropDown=False,  # False = show arrow in Excel / Calc
    )
    dv.error = "Choose a value from the list."
    dv.errorTitle = "Invalid value"
    dv.add(cell_range)
    ws.add_data_validation(dv)


def lang_filename_formula(row: int, lang_idx: int, index_col: str = "C") -> str:
    ref = f"{index_col}{row}"
    return (
        f'=IF({ref}="","",'
        f'TEXT({FILES_PER_LANGUAGE}*{lang_idx}+{ref},"000")&".mp4")'
    )


def file_index_formula(row: int, index_col: str = "C") -> str:
    ref = f"{index_col}{row}"
    return f'=IF({ref}="","",TEXT({ref},"000")&".mp4")'


def cat_token_formula(row: int, profile_col: str) -> str:
    ref = f"{profile_col}{row}"
    t0, t1, t2, t3 = (f'"{t}"' for t in CAT_CPP)
    return (
        f'=IF({ref}="","",'
        f'IF({ref}="Emotions",{t0},'
        f'IF({ref}="Realiste",{t1},'
        f'IF({ref}="Matiere",{t2},'
        f'IF({ref}="Conteur",{t3},{t0})))))'
    )


def question_line_formula(row: int) -> str:
    """Empty when Artwork (B) is blank ? same rule as CodeGen row filter."""
    art = f"{get_column_letter(COL_ARTWORK)}{row}"
    off = f"{get_column_letter(COL_TEXT_OFFSET)}{row}"
    scr = f"{get_column_letter(COL_QUESTION_ON)}{row}"
    n, o, p, q = (f"{c}{row}" for c in HIDDEN_CAT_COLS)
    return (
        f'=IF({art}="","",'
        f'"  {{ "&{off}&", {{ "&{n}&", "&{o}&", "&{p}&", "&{q}&" }}, "&{scr}&" }},")'
    )


def step_formula(row: int) -> str:
    art = f"{get_column_letter(COL_ARTWORK)}{row}"
    return f'=IF({art}="","",ROW()-{QUESTIONS_FIRST_ROW - 1})'


def text_offset_formula(row: int) -> str:
    """SD text file index (= step number); hidden from media team."""
    step_col = get_column_letter(COL_QNUM)
    art = f"{get_column_letter(COL_ARTWORK)}{row}"
    return f'=IF({art}="","",{step_col}{row})'


def count_questions_formula() -> str:
    art_col = get_column_letter(COL_ARTWORK)
    return (
        f"COUNTA(Questions!${art_col}${QUESTIONS_FIRST_ROW}:"
        f"${art_col}${QUESTIONS_LAST_ROW})"
    )


def num_questions_cpp_formula() -> str:
    return f'="static const uint8_t NUM_QUESTIONS = "&{count_questions_formula()}&";"'


def fill_question_row(
    ws: Worksheet,
    row: int,
    *,
    cats: Sequence[int] | None = None,
    question_on: str | None = None,
    artwork: str | None = None,
) -> None:
    """Write one Questions row (formulas + optional default values)."""
    q_col = get_column_letter(COL_QUESTION_ON)
    off_col = get_column_letter(COL_TEXT_OFFSET)
    img_col = get_column_letter(COL_IMAGE_INDEX)

    ws.cell(row=row, column=COL_QNUM, value=step_formula(row))
    if artwork is not None:
        ws.cell(row=row, column=COL_ARTWORK, value=artwork)
    if question_on is not None:
        ws.cell(row=row, column=COL_QUESTION_ON, value=question_on)
    ws.cell(
        row=row, column=COL_ARTWORK_ON,
        value=f'=IF({q_col}{row}="Portrait","Landscape","Portrait")',
    )
    ws.cell(row=row, column=COL_TEXT_OFFSET, value=text_offset_formula(row))
    ws.cell(
        row=row, column=COL_IMAGE_INDEX,
        value=f"={off_col}{row}+{QUESTION_IMAGE_OFFSET_DELTA}",
    )
    if cats is not None:
        for c in range(NUM_CHOICES):
            ws.cell(row=row, column=COL_B1 + c, value=CAT_NAMES[cats[c]])
    ws.cell(
        row=row, column=COL_TEXT_PLAYER,
        value=f'=IF({q_col}{row}="Portrait","WIZ1","WIZ2")',
    )
    ws.cell(
        row=row, column=COL_ART_PLAYER,
        value=f'=IF({q_col}{row}="Portrait","WIZ2","WIZ1")',
    )
    ws.cell(
        row=row, column=COL_TEXT_ASPECT,
        value=f'=IF({q_col}{row}="Portrait","{PORTRAIT_ASPECT}","{LANDSCAPE_ASPECT}")',
    )
    ws.cell(
        row=row, column=COL_ART_ASPECT,
        value=f'=IF({q_col}{row}="Portrait","{LANDSCAPE_ASPECT}","{PORTRAIT_ASPECT}")',
    )
    ws.cell(
        row=row, column=COL_TEXT_FILE_FR,
        value=f'=IF({get_column_letter(COL_ARTWORK)}{row}="","",TEXT(32+{off_col}{row},"000")&".mp4")',
    )
    ws.cell(
        row=row, column=COL_ART_FILE,
        value=f'=IF({get_column_letter(COL_ARTWORK)}{row}="","",TEXT({img_col}{row},"000")&".mp4")',
    )
    for cat_col, prof_col in zip(
        HIDDEN_CAT_COLS,
        (get_column_letter(COL_B1 + j) for j in range(NUM_CHOICES)),
    ):
        ws.cell(row=row, column=ord(cat_col) - 64, value=cat_token_formula(row, prof_col))
    ws.cell(row=row, column=ord(HIDDEN_LINE_COL) - 64, value=question_line_formula(row))


def codegen_question_ref(row: int) -> str:
    return f"='Questions'!${HIDDEN_LINE_COL}{row}"


def build_guide_sheet(ws: Worksheet) -> None:
    ws.title = "Guide"
    ws.sheet_properties.tabColor = "2F5496"
    style_merged_title(ws, "A1", "A1:D1")
    ws["A1"] = "Vision Artiste - MedeaWiz media map"
    lines = [
        "Two MedeaWiz Sprite players:",
        "  WIZ1 - portrait display (1080 x 1920)",
        "  WIZ2 - landscape display (1920 x 1080)",
        "",
        "For each quiz step (Questions sheet):",
        "  - Pick where the QUESTION TEXT plays: Portrait or Landscape (dropdown).",
        "  - The ARTWORK always plays on the other screen (complementary).",
        "  - Export video with the matching aspect ratio on each SD card.",
        "",
        "SD file names: 000.mp4, 001.mp4, ... (3 digits + .mp4).",
        "Index = file number sent to the Sprite.",
        "",
        "Flow: intro (text + art) -> quiz steps -> profile on WIZ1.",
        "Tie-break order: Emotions, Conteur, Matiere, Realiste.",
        "",
        "Add a question: on Questions sheet, fill the next empty row (Artwork column).",
        "  Step number updates automatically. Copy dropdowns from the row above if needed.",
        "  Then copy CodeGen column A into QuestionnaireConfig.h (NUM_QUESTIONS + QUESTIONS[]).",
        "  Skip blank lines at the bottom of the array. Re-run this script to refresh SD WIZ1/WIZ2.",
        "",
        "Sheets: Questions | SD WIZ1 | SD WIZ2 | CodeGen",
        "",
        "If CodeGen shows Err:508 in LibreOffice, run: python scripts/generate_media_workbook.py --emit-cpp",
    ]
    first_limit_row = 3 + len(lines) + 1
    for i, line in enumerate(lines, start=3):
        ws.cell(row=i, column=1, value=line)
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=4)
    ws.cell(row=first_limit_row, column=1, value="Firmware limits").font = SECTION_FONT
    for j, (lab, val) in enumerate([
        ("Files per language (question text)", str(FILES_PER_LANGUAGE)),
        ("Languages", str(NUM_LANGUAGES)),
        ("Max files per SD card", str(MEDEWIZ_MAX_FILES)),
        ("Question rows in workbook", str(MAX_QUESTION_SLOTS)),
        ("Quiz steps (initial)", str(DEFAULT_NUM_QUESTIONS)),
    ]):
        row = first_limit_row + 1 + j
        ws.cell(row=row, column=1, value=lab)
        ws.cell(row=row, column=2, value=val)
    set_col_widths(ws, (58, 18, 12, 12))
    for row in range(3, first_limit_row):
        apply_cell_style(ws.cell(row=row, column=1), fill=INSTRUCTION_FILL, locked=True)
    enable_sheet_protection(ws)


def build_wiz_sd_sheet(
    ws: Worksheet,
    *,
    title: str,
    wiz_name: str,
    default_aspect: str,
    rows: Sequence[Tuple],
    tab_color: str,
    first_row: int,
    last_row: int,
) -> None:
    ws.title = title
    ws.sheet_properties.tabColor = tab_color
    style_merged_title(ws, "A1", "A1:I1")
    ws["A1"] = f"SD card - {wiz_name}"
    ws["A2"] = (
        "Copy each file to this SD card using the exact name shown. "
        "Encode each row at the Aspect shown (portrait 1080x1920 or landscape 1920x1080). "
        "Text rows list all 4 languages."
    )
    style_instruction_row(ws, "A2", "A2:I2")
    headers = [
        "Role", "Quiz ref", "File index", "Content", "Aspect",
        "EN file", "FR file", "DE file", "IT file",
    ]
    for col, hdr in enumerate(headers, start=1):
        fill = EDIT_HEADER_FILL if col == 3 else (
            FILE_HEADER_FILL if col >= 6 else INPUT_HEADER_FILL
        )
        apply_cell_style(ws.cell(row=3, column=col, value=hdr), fill=fill, font=HEADER_FONT, locked=True)

    for i, row_data in enumerate(rows):
        row = first_row + i
        role, qref, file_idx, desc, row_aspect = row_data
        ws.cell(row=row, column=1, value=role)
        ws.cell(row=row, column=2, value=qref)
        ws.cell(row=row, column=3, value=file_idx)
        ws.cell(row=row, column=4, value=desc)
        ws.cell(row=row, column=5, value=row_aspect)
        if role_has_language_files(role):
            for lang_idx in range(NUM_LANGUAGES):
                ws.cell(row=row, column=6 + lang_idx, value=lang_filename_formula(row, lang_idx))
        else:
            ws.cell(row=row, column=6, value=file_index_formula(row))

    center = Alignment(horizontal="center", vertical="center")
    for row in range(first_row, last_row + 1):
        role = ws.cell(row=row, column=1).value or ""
        has_langs = role_has_language_files(role)
        for col in range(1, 10):
            if col >= 7 and not has_langs:
                continue
            editable = col == 3
            calc = col in (5, 6) or col >= 6
            apply_cell_style(
                ws.cell(row=row, column=col),
                fill=EDIT_FILL if editable else (CALC_FILL if calc else INPUT_FILL),
                font=DATA_FONT,
                alignment=center if col != 4 else Alignment(wrap_text=True, vertical="top"),
                border=DATA_BORDER,
                locked=not editable,
            )
    set_col_widths(ws, (22, 8, 10, 44, 12, 12, 12, 12, 12))
    ws.freeze_panes = "A4"
    enable_sheet_protection(ws)


def build_questions_sheet(ws: Worksheet) -> None:
    ws.title = "Questions"
    ws.sheet_properties.tabColor = "C55A11"
    style_merged_title(ws, "A1", "A1:P1")
    ws["A1"] = "Quiz steps - screens and profiles"
    ws["A2"] = (
        f"Add a step: fill the next empty row (column Artwork). "
        f"Rows {QUESTIONS_FIRST_ROW}-{QUESTIONS_LAST_ROW} are ready (max {MAX_QUESTION_SLOTS} steps). "
        "Question plays on = dropdown (Portrait / Landscape). Artwork plays on is automatic."
    )
    style_instruction_row(ws, "A2", "A2:P2")

    headers = {
        COL_QNUM: "Step",
        COL_ARTWORK: "Artwork",
        COL_QUESTION_ON: "Question plays on",
        COL_ARTWORK_ON: "Artwork plays on",
        COL_B1: "B1",
        COL_B1 + 1: "B2",
        COL_B1 + 2: "B3",
        COL_B1 + 3: "B4",
        COL_TEXT_PLAYER: "Text player",
        COL_ART_PLAYER: "Art player",
        COL_TEXT_ASPECT: "Text aspect",
        COL_ART_ASPECT: "Art aspect",
        COL_TEXT_FILE_FR: "Text file (FR)",
        COL_ART_FILE: "Art file",
    }
    for col, title in headers.items():
        apply_cell_style(
            ws.cell(row=3, column=col, value=title),
            fill=EDIT_HEADER_FILL if col in (
                COL_ARTWORK, COL_QUESTION_ON,
                COL_B1, COL_B1 + 1, COL_B1 + 2, COL_B1 + 3,
            ) else INPUT_HEADER_FILL,
            font=HEADER_FONT,
            locked=True,
        )

    defaults = list(DEFAULT_QUESTIONS)
    for slot in range(MAX_QUESTION_SLOTS):
        row = QUESTIONS_FIRST_ROW + slot
        if slot < len(defaults):
            cats, question_on, artwork = defaults[slot]
            fill_question_row(
                ws, row,
                cats=cats,
                question_on=question_on,
                artwork=artwork,
            )
        else:
            fill_question_row(ws, row, question_on="Portrait")

    ws.column_dimensions[get_column_letter(COL_TEXT_OFFSET)].hidden = True
    ws.column_dimensions[get_column_letter(COL_IMAGE_INDEX)].hidden = True

    for col_letter in (*HIDDEN_CAT_COLS, HIDDEN_LINE_COL):
        ws.column_dimensions[col_letter].hidden = True

    q_col = get_column_letter(COL_QUESTION_ON)
    screen_range = f"{q_col}{QUESTIONS_FIRST_ROW}:{q_col}{QUESTIONS_LAST_ROW}"
    add_list_validation(ws, screen_range, SCREEN_LIST)
    for j in range(NUM_CHOICES):
        prof_col = get_column_letter(COL_B1 + j)
        add_list_validation(
            ws,
            f"{prof_col}{QUESTIONS_FIRST_ROW}:{prof_col}{QUESTIONS_LAST_ROW}",
            PROFILE_LIST,
        )

    center = Alignment(horizontal="center", vertical="center")
    for row in range(QUESTIONS_FIRST_ROW, QUESTIONS_LAST_ROW + 1):
        for col in range(1, COL_ART_FILE + 1):
            editable = col in (
                COL_ARTWORK, COL_QUESTION_ON,
                COL_B1, COL_B1 + 1, COL_B1 + 2, COL_B1 + 3,
            )
            calc = col in (
                COL_QNUM, COL_TEXT_OFFSET, COL_ARTWORK_ON, COL_IMAGE_INDEX,
                COL_TEXT_PLAYER, COL_ART_PLAYER, COL_TEXT_ASPECT, COL_ART_ASPECT,
                COL_TEXT_FILE_FR, COL_ART_FILE,
            )
            apply_cell_style(
                ws.cell(row=row, column=col),
                fill=EDIT_FILL if editable else (CALC_FILL if calc else INPUT_FILL),
                font=DATA_FONT,
                alignment=center if col != COL_ARTWORK else Alignment(horizontal="left"),
                border=DATA_BORDER,
                locked=not editable,
            )

    set_col_widths(ws, (6, 34, 16, 16, 4, 4, 11, 11, 11, 11, 10, 10, 12, 12, 14, 12))
    ws.freeze_panes = "A4"
    enable_sheet_protection(ws)


def build_codegen_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("CodeGen")
    ws.sheet_properties.tabColor = "BF8F00"
    style_merged_title(ws, "A1", "A1:E1")
    ws["A1"] = "QuestionnaireConfig.h generator"
    ws["A2"] = (
        "Copy column A (values shown) from BEGIN through END into QuestionnaireConfig.h. "
        "Includes NUM_QUESTIONS and QUESTIONS[]. Skip empty lines in the array. "
        "Row count = filled Artwork cells on Questions sheet."
    )
    style_instruction_row(ws, "A2", "A2:E2")
    ws.cell(row=CODEGEN_BEGIN_ROW, column=1, value="// --- BEGIN_QUESTIONNAIRE_CONFIG ---")
    ws.cell(row=CODEGEN_NUM_QUESTIONS_ROW, column=1, value=num_questions_cpp_formula())
    ws.cell(row=CODEGEN_ARRAY_OPEN_ROW, column=1, value='="static const QuestionEntry QUESTIONS[NUM_QUESTIONS] = {"')
    for slot in range(MAX_QUESTION_SLOTS):
        ws.cell(
            row=CODEGEN_FIRST_Q_ROW + slot,
            column=1,
            value=codegen_question_ref(QUESTIONS_FIRST_ROW + slot),
        )
    ws.cell(row=CODEGEN_CLOSE_ROW, column=1, value='="};"')
    ws.cell(row=CODEGEN_END_MARKER_ROW, column=1, value="// --- END_QUESTIONNAIRE_CONFIG ---")
    ws.cell(row=CODEGEN_END_MARKER_ROW + 1, column=1, value=(
        "NUM_QUESTIONS = count of rows with Artwork on Questions sheet. "
        "SD indices: text and artwork share the same step number on each card (0 = idle). "
        "Text filenames use language blocks on the text player only."
    ))
    for row in range(COPY_BLOCK_FIRST_ROW, CODEGEN_END_MARKER_ROW + 2):
        apply_cell_style(
            ws.cell(row=row, column=1),
            fill=COPY_FILL,
            font=Font(name="Consolas", size=10),
            alignment=Alignment(wrap_text=True, vertical="top"),
            locked=True,
        )
    set_col_widths(ws, (110,))
    ws.freeze_panes = "A5"
    enable_sheet_protection(ws)


def build_workbook() -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    build_guide_sheet(wb.create_sheet("Guide"))
    build_questions_sheet(wb.create_sheet("Questions"))
    build_wiz_sd_sheet(
        wb.create_sheet("SD WIZ1"),
        title="SD WIZ1",
        wiz_name="WIZ1 portrait display",
        default_aspect=PORTRAIT_ASPECT,
        rows=WIZ1_SD_ROWS,
        tab_color="548235",
        first_row=WIZ1_FIRST_ROW,
        last_row=WIZ1_LAST_ROW,
    )
    build_wiz_sd_sheet(
        wb.create_sheet("SD WIZ2"),
        title="SD WIZ2",
        wiz_name="WIZ2 landscape display",
        default_aspect=LANDSCAPE_ASPECT,
        rows=WIZ2_SD_ROWS,
        tab_color="7030A0",
        first_row=WIZ2_FIRST_ROW,
        last_row=WIZ2_LAST_ROW,
    )
    build_codegen_sheet(wb)
    return wb


def screen_to_cpp(screen: str) -> str:
    s = (screen or "").strip()
    return "Landscape" if s.lower().startswith("land") else "Portrait"


def iter_question_rows_from_sheet(ws: Worksheet) -> List[int]:
    """Row numbers on Questions sheet that have Artwork filled in."""
    rows: List[int] = []
    for row in range(QUESTIONS_FIRST_ROW, QUESTIONS_LAST_ROW + 1):
        artwork = ws.cell(row=row, column=COL_ARTWORK).value
        if artwork is not None and str(artwork).strip():
            rows.append(row)
    return rows


def emit_cpp_from_workbook(path: Path) -> str:
    wb = load_workbook(path, data_only=True)
    ws = wb["Questions"]
    question_rows = iter_question_rows_from_sheet(ws)
    n = len(question_rows)
    lines = [
        "// --- BEGIN_QUESTIONNAIRE_CONFIG ---",
        f"static const uint8_t NUM_QUESTIONS = {n};",
        "static const QuestionEntry QUESTIONS[NUM_QUESTIONS] = {",
    ]
    for step, row in enumerate(question_rows, start=1):
        screen = screen_to_cpp(str(ws.cell(row=row, column=COL_QUESTION_ON).value))
        artwork = ws.cell(row=row, column=COL_ARTWORK).value or f"Q{step}"
        cats = []
        for c in range(NUM_CHOICES):
            name = ws.cell(row=row, column=COL_B1 + c).value
            try:
                cats.append(CAT_CPP[CAT_NAMES.index(str(name).strip())])
            except ValueError:
                cats.append(CAT_CPP[0])
        off = ws.cell(row=row, column=COL_TEXT_OFFSET).value
        try:
            off = int(off)
        except (TypeError, ValueError):
            off = ws.cell(row=row, column=COL_QNUM).value
            try:
                off = int(off)
            except (TypeError, ValueError):
                off = step
        lines.append(f"  // Step {step} - {artwork}")
        lines.append(f"  {{ {off}, {{ {', '.join(cats)} }}, {screen} }},")
    lines += ["};", "// --- END_QUESTIONNAIRE_CONFIG ---"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    repo = Path(__file__).resolve().parents[1]
    default_out = repo / "questions" / "MediaMap_workbook.xlsx"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=default_out)
    parser.add_argument("--emit-cpp", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.emit_cpp:
        if not args.output.exists():
            raise SystemExit(f"workbook not found: {args.output}")
        print(emit_cpp_from_workbook(args.output))
        return

    wb = build_workbook()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
