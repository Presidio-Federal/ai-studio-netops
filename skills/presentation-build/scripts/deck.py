#!/usr/bin/env python3
"""Edit and compile a presentation deck.

The parent writes <customer>/deck.json at the workspace root.
This script rebuilds <customer>/<customer>.pptx from the bundled
Disney-Presidio template.

Stdout is one JSON object. Exit 1 on a hard failure.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "disney-presidio-template.pptx")

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

NAVY = RGBColor(0x00, 0x44, 0x7A)
ORANGE = RGBColor(0xFF, 0x99, 0x01)
INK = RGBColor(0x33, 0x33, 0x33)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CARD = RGBColor(0xF4, 0xF7, 0xF8)

PROMPTS = (
    "click to add",
    "click to edit",
    "click icon",
    "title text",
    "body level",
    "lorem",
    "ipsum",
)

# Presidio 2021 layouts on the first master. These carry the Arial
# sizes (cover 60/24, content title 36, body 28/24/20). Do not use
# the second master's generic Title, Content layouts.
LAYOUTS = {
    "cover": ("slideLayout16.xml", "Title Slide 2 Blue", 0, ("title", "subtitle"), False),
    "title-content": ("slideLayout6.xml", "Title and Content", 1, ("title", "body"), False),
    "agenda": ("slideLayout6.xml", "Title and Content", 1, ("title", "body"), False),
    "two-column": ("slideLayout28.xml", "1_Two Content", 2, ("title", "body"), False),
    "title-only": ("slideLayout7.xml", "Title Only", 0, ("title",), True),
    "section": ("slideLayout11.xml", "Section Slide", 0, ("title",), False),
    "chapter": ("slideLayout21.xml", "Chapter Slide", 1, ("title", "body"), False),
    "quote": ("slideLayout36.xml", "Large Quote w-Subtext", 0, ("title", "subtitle"), False),
    "table": ("slideLayout79.xml", "1_Title and Table", 1, ("title", "body", "table"), False),
}

BLOCK_AREA = {
    "title-only": (0.55, 1.55, 12.25, 5.15),
}


def fail(message):
    json.dump({"ok": False, "error": message}, sys.stdout)
    sys.stdout.write("\n")
    raise SystemExit(1)


def emit(obj):
    json.dump(obj, sys.stdout)
    sys.stdout.write("\n")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_slug(slug):
    if not slug or not SLUG_RE.match(slug) or len(slug) > 48:
        fail("slug must be lowercase words joined by hyphens")
    return slug


def deck_paths(workspace, slug):
    folder = os.path.join(workspace, slug)
    return {
        "folder": folder,
        "deck": os.path.join(folder, "deck.json"),
        "patch": os.path.join(folder, "patch.json"),
        "pptx": os.path.join(folder, slug + ".pptx"),
    }


def load_json(path, label):
    if not os.path.isfile(path):
        fail("missing " + label)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        fail(label + " is not JSON")
    if not isinstance(data, dict):
        fail(label + " must be an object")
    return data


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


def as_text(value, label):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            fail(label + " is empty")
        return text
    fail(label + " must be a string")


def as_items(value, label, lo, hi):
    if not isinstance(value, list) or not (lo <= len(value) <= hi):
        fail(label + " needs " + str(lo) + " to " + str(hi) + " items")
    out = []
    for i, item in enumerate(value, 1):
        out.append(as_text(item, label + " item " + str(i)))
    return out


def check_blocks(blocks, layout_id):
    _part, _name, _bodies, _slots, allows = LAYOUTS[layout_id]
    if not blocks:
        if layout_id == "blank":
            fail("blank requires blocks")
        return []
    if not allows:
        fail(layout_id + " does not take blocks")
    if not isinstance(blocks, list) or len(blocks) > 4:
        fail("blocks must be a list of at most 4")
    clean = []
    for i, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            fail("block " + str(i) + " must be an object")
        extra = set(block) - {"type", "items", "headers", "rows"}
        if extra:
            fail("block " + str(i) + " has " + ", ".join(sorted(extra)))
        kind = block.get("type")
        if kind == "bullets":
            clean.append({"type": "bullets", "items": as_items(block.get("items"), "bullets", 1, 10)})
        elif kind == "stats":
            items = _named_items(block.get("items"), "stats", 1, 3, "value", "label", 12, 40)
            clean.append({"type": "stats", "items": items})
        elif kind == "cards":
            items = _named_items(block.get("items"), "cards", 1, 3, "title", "body", 40, 180)
            clean.append({"type": "cards", "items": items})
        elif kind == "table":
            clean.append({"type": "table", **check_table(block, "block table")})
        else:
            fail("block type must be bullets, stats, cards, or table")
    return clean


def _named_items(items, label, lo, hi, a, b, amax, bmax):
    if not isinstance(items, list) or not (lo <= len(items) <= hi):
        fail(label + " needs " + str(lo) + " to " + str(hi) + " items")
    out = []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {a, b}:
            fail(label + " item " + str(i) + " needs " + a + " and " + b)
        left = as_text(item[a], label + " " + a)
        right = as_text(item[b], label + " " + b)
        if len(left) > amax or len(right) > bmax:
            fail(label + " item " + str(i) + " is too long")
        out.append({a: left, b: right})
    return out


def check_table(obj, label):
    headers = as_items(obj.get("headers"), label + " headers", 1, 6)
    rows = obj.get("rows")
    if not isinstance(rows, list) or not (1 <= len(rows) <= 8):
        fail(label + " needs 1 to 8 rows")
    clean_rows = []
    for r, row in enumerate(rows, 1):
        if not isinstance(row, list) or len(row) != len(headers):
            fail(label + " row " + str(r) + " must match the headers")
        clean_rows.append([as_text(cell, label + " cell") for cell in row])
    return {"headers": headers, "rows": clean_rows}


def cell_value(value, label):
    """A body cell is a string or a list of bullet strings."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            fail(label + " is empty")
        return text
    if isinstance(value, list):
        return as_items(value, label, 1, 10)
    fail(label + " must be a string or a list of strings")


def check_slide(slide, allow_blank_slots):
    if not isinstance(slide, dict):
        fail("a slide must be an object")
    extra = set(slide) - {"n", "layout", "slots", "blocks"}
    if extra:
        fail("slide has " + ", ".join(sorted(extra)))
    n = slide.get("n")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        fail("slide n must be a positive integer")
    layout_id = slide.get("layout")
    if layout_id not in LAYOUTS:
        fail("unknown layout " + repr(layout_id))
    _part, _name, bodies, slot_names, _allows = LAYOUTS[layout_id]
    slots = slide.get("slots", {})
    if not isinstance(slots, dict):
        fail("slide " + str(n) + " slots must be an object")
    unknown = set(slots) - set(slot_names)
    if unknown:
        fail("slide " + str(n) + " slots have " + ", ".join(sorted(unknown)))
    if layout_id != "blank" and "title" in slot_names and "title" not in slots and not allow_blank_slots:
        fail("slide " + str(n) + " needs a title")
    clean_slots = {}
    if "title" in slots:
        clean_slots["title"] = as_text(slots["title"], "slide " + str(n) + " title")
    if "subtitle" in slots:
        clean_slots["subtitle"] = as_text(slots["subtitle"], "slide " + str(n) + " subtitle")
    if "body" in slots:
        body = slots["body"]
        if bodies > 1:
            if not isinstance(body, list) or len(body) != bodies:
                fail("slide " + str(n) + " body needs " + str(bodies) + " columns")
            clean_slots["body"] = [cell_value(col, "slide " + str(n) + " column") for col in body]
        else:
            clean_slots["body"] = cell_value(body, "slide " + str(n) + " body")
    if "table" in slots:
        if not isinstance(slots["table"], dict):
            fail("slide " + str(n) + " table must be an object")
        clean_slots["table"] = check_table(slots["table"], "slide " + str(n) + " table")
    if layout_id == "centered" and "subtitle" not in clean_slots and not allow_blank_slots:
        fail("slide " + str(n) + " needs a subtitle")
    blocks = check_blocks(slide.get("blocks") or [], layout_id)
    out = {"n": n, "layout": layout_id, "slots": clean_slots}
    if blocks:
        out["blocks"] = blocks
    return out


def check_sequence(slides):
    numbers = [s["n"] for s in slides]
    if numbers != list(range(1, len(slides) + 1)):
        fail("slides must be numbered 1 through " + str(len(slides)) + " with no gaps")


def save_deck(paths, deck):
    write_json(paths["deck"], deck)


def cmd_edit(args):
    slug = check_slug(args.slug)
    paths = deck_paths(args.workspace, slug)
    patch = load_json(paths["patch"], "patch.json")
    if args.op == "init":
        if os.path.isfile(paths["deck"]):
            fail("deck exists; use set")
        if "slides" not in patch or "n" in patch:
            fail("init patch needs title and slides")
        title = as_text(patch.get("title"), "title")
        slides_in = patch.get("slides")
        if not isinstance(slides_in, list) or not slides_in or len(slides_in) > 40:
            fail("outline needs 1 to 40 slides")
        extra = set(patch) - {"title", "slides"}
        if extra:
            fail("outline has " + ", ".join(sorted(extra)))
        slides = [check_slide(s, allow_blank_slots=False) for s in slides_in]
        check_sequence(slides)
        deck = {
            "schema": "presentation-deck/v1",
            "keys": [],
            "updated_at": now(),
            "source_agent": "presentation",
            "slug": slug,
            "title": title,
            "slides": slides,
        }
    elif args.op == "set":
        if not os.path.isfile(paths["deck"]):
            fail("no deck; confirm an outline first")
        if "slides" in patch or "n" not in patch:
            fail("set patch must be one slide")
        deck = load_json(paths["deck"], "deck.json")
        slide = check_slide(patch, allow_blank_slots=False)
        slides = list(deck.get("slides") or [])
        numbers = [s.get("n") for s in slides]
        if slide["n"] == len(slides) + 1:
            slides.append(slide)
        elif slide["n"] in numbers:
            slides = [slide if s.get("n") == slide["n"] else s for s in slides]
        else:
            fail("slide " + str(slide["n"]) + " is not in the deck; the next slide is " + str(len(slides) + 1))
        check_sequence(slides)
        deck["slides"] = slides
        deck["updated_at"] = now()
        deck["keys"] = []
        deck["source_agent"] = "presentation"
        deck["schema"] = "presentation-deck/v1"
    else:
        fail("op must be init or set")
    save_deck(paths, deck)
    if os.path.isfile(paths["patch"]):
        os.remove(paths["patch"])
    summary = {
        "ok": True,
        "op": args.op,
        "slug": slug,
        "title": deck["title"],
        "slides": len(deck["slides"]),
        "layouts": [s["layout"] for s in deck["slides"]],
    }
    if args.op == "set":
        summary["n"] = patch["n"]
        summary["layout"] = patch["layout"]
    emit(summary)


def cmd_show(args):
    slug = check_slug(args.slug)
    paths = deck_paths(args.workspace, slug)
    deck = load_json(paths["deck"], "deck.json")
    if args.n is None:
        fail("show needs --n")
    for slide in deck.get("slides") or []:
        if slide.get("n") == args.n:
            emit({
                "ok": True,
                "op": "show",
                "slug": slug,
                "title": deck.get("title"),
                "slides": len(deck.get("slides") or []),
                "slide": slide,
            })
            return
    fail("slide " + str(args.n) + " is not in " + slug)


def find_layout(prs, part_name, expect_name):
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            part = str(layout.part.partname).split("/")[-1]
            if part == part_name:
                if layout.name != expect_name:
                    fail("template layout " + part_name + " is " + repr(layout.name) + ", expected " + repr(expect_name))
                return layout
    fail("template is missing " + part_name)


def drop_existing_slides(prs):
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        r_id = sld_id.get(qn("r:id"))
        prs.part.drop_rel(r_id)
        sld_id_lst.remove(sld_id)


def classify(slide):
    title = subtitle = None
    bodies, pictures, tables = [], [], []
    for shape in slide.shapes:
        if not shape.is_placeholder:
            continue
        kind = shape.placeholder_format.type
        if kind in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE) and title is None:
            title = shape
        elif kind == PP_PLACEHOLDER.SUBTITLE and subtitle is None:
            subtitle = shape
        elif kind == PP_PLACEHOLDER.PICTURE:
            pictures.append(shape)
        elif kind == PP_PLACEHOLDER.TABLE:
            tables.append(shape)
        elif kind in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
            bodies.append(shape)
    return title, subtitle, bodies, pictures, tables


def drop_shape(shape):
    element = shape._element
    element.getparent().remove(element)


def write_text(shape, value, warnings, where):
    items = value if isinstance(value, list) else [value]
    frame = shape.text_frame
    frame.word_wrap = True
    first = frame.paragraphs[0]
    first.text = items[0]
    for extra in list(frame.paragraphs)[1:]:
        extra._p.getparent().remove(extra._p)
    for item in items[1:]:
        paragraph = frame.add_paragraph()
        paragraph.text = item
        paragraph.level = 0
    for item in items:
        if len(item) > 180:
            warnings.append(where + ": a line is " + str(len(item)) + " characters")
    if len(items) > 8:
        warnings.append(where + ": " + str(len(items)) + " bullets")


def style_run(run, size, bold, color):
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def write_shape_text(shape, text, size, bold, color, align=PP_ALIGN.LEFT):
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    style_run(run, size, bold, color)


def paint_cell(cell, text, fill, color, size, bold):
    cell.text = text
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    for paragraph in cell.text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.LEFT
        for run in paragraph.runs:
            style_run(run, size, bold, color)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE


def add_table(slide, left, top, width, height, headers, rows):
    graphic = slide.shapes.add_table(len(rows) + 1, len(headers), left, top, width, height)
    table = graphic.table
    for col, header in enumerate(headers):
        paint_cell(table.cell(0, col), header, NAVY, WHITE, 12, True)
    for r, row in enumerate(rows, 1):
        fill = WHITE if r % 2 else CARD
        for c, text in enumerate(row):
            paint_cell(table.cell(r, c), text, fill, INK, 12, False)
    return graphic


def place_blocks(slide, layout_id, blocks, warnings, n):
    area = BLOCK_AREA[layout_id]
    left, top, width, height = area
    gap = 0.18
    count = len(blocks)
    each = (height - gap * (count - 1)) / count
    if each < 1.15:
        warnings.append("slide " + str(n) + ": blocks are tight")
    y = top
    for block in blocks:
        box = (Inches(left), Inches(y), Inches(width), Inches(each))
        if block["type"] == "bullets":
            shape = slide.shapes.add_textbox(*box)
            write_shape_text(shape, "", 16, False, INK)
            write_text(shape, block["items"], warnings, "slide " + str(n))
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    style_run(run, 28, False, INK)
        elif block["type"] == "stats":
            place_row(slide, box, block["items"], "value", "label", NAVY, WHITE, 32, 14)
        elif block["type"] == "cards":
            place_row(slide, box, block["items"], "title", "body", CARD, INK, 16, 13, accent=True)
        elif block["type"] == "table":
            add_table(slide, *box, block["headers"], block["rows"])
        y += each + gap


def place_row(slide, box, items, primary, secondary, fill, ink, primary_pt, secondary_pt, accent=False):
    left, top, width, height = box
    gap = Inches(0.18)
    count = len(items)
    col = int((width - gap * (count - 1)) / count)
    x = left
    for item in items:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, top, col, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
        shape.line.fill.background()
        if accent:
            bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, top, col, Inches(0.06))
            bar.fill.solid()
            bar.fill.fore_color.rgb = ORANGE
            bar.line.fill.background()
        frame = shape.text_frame
        frame.word_wrap = True
        frame.margin_left = Inches(0.14)
        frame.margin_right = Inches(0.14)
        frame.clear()
        head = frame.paragraphs[0]
        head.alignment = PP_ALIGN.LEFT
        run = head.add_run()
        run.text = item[primary]
        style_run(run, primary_pt, True, WHITE if fill == NAVY else NAVY)
        sub = frame.add_paragraph()
        sub.alignment = PP_ALIGN.LEFT
        run = sub.add_run()
        run.text = item[secondary]
        style_run(run, secondary_pt, False, ink if fill != NAVY else WHITE)
        shape.text_frame.auto_size = None
        try:
            shape.text_frame._txBody.bodyPr.set("anchor", "ctr")
        except Exception:
            pass
        x += col + gap


def fill_slide(prs, spec, warnings):
    part, expect, body_count, _slots, _blocks = LAYOUTS[spec["layout"]]
    layout = find_layout(prs, part, expect)
    slide = prs.slides.add_slide(layout)
    title, subtitle, bodies, pictures, tables = classify(slide)
    slots = spec.get("slots") or {}
    n = spec["n"]
    if "title" in slots and title is not None:
        write_text(title, slots["title"], warnings, "slide " + str(n) + " title")
        if len(slots["title"]) > 90:
            warnings.append("slide " + str(n) + ": title is " + str(len(slots["title"])) + " characters")
    elif title is not None and spec["layout"] not in ("blank", "centered"):
        drop_shape(title)
        warnings.append("slide " + str(n) + ": title empty")
        title = None
    if "subtitle" in slots and subtitle is not None:
        write_text(subtitle, slots["subtitle"], warnings, "slide " + str(n) + " subtitle")
        if len(slots["subtitle"]) > 140:
            warnings.append("slide " + str(n) + ": subtitle is " + str(len(slots["subtitle"])) + " characters")
    elif subtitle is not None:
        drop_shape(subtitle)
        if "subtitle" in LAYOUTS[spec["layout"]][3]:
            warnings.append("slide " + str(n) + ": subtitle empty")
    if body_count:
        if len(bodies) < body_count:
            fail("layout " + spec["layout"] + " has " + str(len(bodies)) + " body placeholders, expected " + str(body_count))
        body = slots.get("body")
        if body is None:
            columns = []
        elif body_count > 1:
            columns = body
        else:
            columns = [body]
        missing_body = False
        for index, shape in enumerate(bodies):
            if index >= body_count:
                drop_shape(shape)
                continue
            value = None
            if body is not None and index < len(columns):
                value = columns[index]
            if value:
                write_text(shape, value, warnings, "slide " + str(n) + " body")
            else:
                drop_shape(shape)
                missing_body = True
        if missing_body:
            warnings.append("slide " + str(n) + ": body empty")
    if "table" in slots and tables:
        graphic = tables[0].insert_table(len(slots["table"]["rows"]) + 1, len(slots["table"]["headers"]))
        table = graphic.table
        for col, header in enumerate(slots["table"]["headers"]):
            paint_cell(table.cell(0, col), header, NAVY, WHITE, 12, True)
        for r, row in enumerate(slots["table"]["rows"], 1):
            fill = WHITE if r % 2 else CARD
            for c, text in enumerate(row):
                paint_cell(table.cell(r, c), text, fill, INK, 12, False)
    elif tables:
        for shape in tables:
            drop_shape(shape)
        if "table" in LAYOUTS[spec["layout"]][3]:
            warnings.append("slide " + str(n) + ": table empty")
    for shape in pictures:
        drop_shape(shape)
    if spec.get("blocks"):
        place_blocks(slide, spec["layout"], spec["blocks"], warnings, n)
    for shape in list(slide.shapes):
        if not getattr(shape, "has_text_frame", False):
            continue
        text = shape.text_frame.text.strip().lower()
        if any(prompt in text for prompt in PROMPTS):
            warnings.append("slide " + str(n) + ": leftover placeholder text")
            break


def look(layout):
    if layout in ("title-content", "agenda"):
        return "content"
    return layout


def check_variety(slides):
    layouts = [s.get("layout") for s in slides]
    if layouts[0] != "cover":
        fail("slide 1 must be cover (Title Slide 2 Blue). That is the only intro slide")
    for n, layout in enumerate(layouts[1:], 2):
        if layout == "cover":
            fail("slide " + str(n) + " is the intro slide. Only slide 1 may be cover")
    looks = [look(layout) for layout in layouts]
    for n in range(1, len(looks)):
        if looks[n] == looks[n - 1]:
            fail("slides " + str(n) + " and " + str(n + 1) + " are the same Disney layout. Use a different one: title-content, two-column, section, chapter, quote, table")


def cmd_compile(args):
    slug = check_slug(args.slug)
    paths = deck_paths(args.workspace, slug)
    if not os.path.isfile(TEMPLATE):
        fail("skill template is missing")
    deck = load_json(paths["deck"], "deck.json")
    slides = deck.get("slides") or []
    if not slides:
        fail("deck has no slides")
    check_variety(slides)
    try:
        prs = Presentation(TEMPLATE)
    except Exception:
        fail("could not open the template")
    drop_existing_slides(prs)
    warnings = []
    for spec in slides:
        if spec.get("layout") not in LAYOUTS:
            fail("deck has unknown layout " + repr(spec.get("layout")))
        fill_slide(prs, spec, warnings)
    write_json_dir = os.path.dirname(paths["pptx"])
    os.makedirs(write_json_dir, exist_ok=True)
    prs.save(paths["pptx"])
    size = os.path.getsize(paths["pptx"])
    emit({
        "ok": True,
        "op": "compile",
        "slug": slug,
        "title": deck.get("title"),
        "path": slug + "/" + slug + ".pptx",
        "bytes": size,
        "slides": len(slides),
        "warnings": warnings,
    })


def main():
    parser = argparse.ArgumentParser(description="Edit or compile a presentation deck")
    sub = parser.add_subparsers(dest="cmd")

    edit = sub.add_parser("edit")
    edit.add_argument("--workspace", required=True)
    edit.add_argument("--slug", required=True)
    edit.add_argument("--op", required=True, choices=("init", "set"))
    edit.set_defaults(func=cmd_edit)

    show = sub.add_parser("show")
    show.add_argument("--workspace", required=True)
    show.add_argument("--slug", required=True)
    show.add_argument("--n", type=int, required=True)
    show.set_defaults(func=cmd_show)

    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--workspace", required=True)
    compile_cmd.add_argument("--slug", required=True)
    compile_cmd.set_defaults(func=cmd_compile)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        fail("use edit, show, or compile")
    if not os.path.isdir(args.workspace):
        fail("workspace is not a directory")
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:
        fail(exc.__class__.__name__ + ": " + str(exc))


if __name__ == "__main__":
    main()
