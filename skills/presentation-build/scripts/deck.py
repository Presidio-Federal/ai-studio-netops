#!/usr/bin/env python3
"""Edit, decompile, and compile a presentation deck.

The parent writes <customer>/deck.json at the workspace root, or
`restyle` decompiles an attached pptx into that file. Compile
rebuilds <customer>/<customer>.pptx from the bundled Disney-Presidio
template.

Stdout is one JSON object. Exit 1 on a hard failure.
"""
import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

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
TINT = RGBColor(0xFF, 0xF4, 0xE5)

P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

# Fit a decompiled slide inside the Presidio canvas. The left rail is the
# template logo. The footer line sits at about 7.03in.
MIRROR_PART = ("slideLayout28.xml", "1_Two Content")
SAFE = (0.78, 0.16, 12.05, 6.62)
ROLE = {
    "navy": NAVY,
    "ink": INK,
    "accent": ORANGE,
    "white": WHITE,
    "card": CARD,
    "tint": TINT,
}
FILL_HEX = {
    "FBF8F3": "card",
    "F1E1DE": "tint",
    "A63032": "accent",
    "242321": "navy",
    "00447A": "navy",
    "FF9901": "accent",
    "F4F7F8": "card",
    "FFFFFF": "white",
    "FFF4E5": "tint",
}
INK_HEX = {
    "A63032": "accent",
    "282625": "navy",
    "68615B": "ink",
    "FFFFFF": "white",
    "333333": "ink",
    "00447A": "navy",
    "FF9901": "accent",
    "000000": "navy",
}
SHAPE_KINDS = ("text", "roundRect", "rect", "chevron", "line")

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
    extra = set(slide) - {"n", "layout", "slots", "blocks", "shapes"}
    if extra:
        fail("slide has " + ", ".join(sorted(extra)))
    n = slide.get("n")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        fail("slide n must be a positive integer")
    layout_id = slide.get("layout")
    if layout_id == "mirror":
        if slide.get("blocks"):
            fail("slide " + str(n) + " is mirror and does not take blocks")
        return {"n": n, "layout": "mirror", "slots": {}, "shapes": check_shapes(slide.get("shapes"), n)}
    if "shapes" in slide:
        fail("slide " + str(n) + " is not a mirror slide")
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


def inches(emu):
    return round(int(emu) / 914400.0, 2)


def luminance(hex_color):
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def snap_fill(hex_color):
    if hex_color and hex_color.upper() in FILL_HEX:
        return FILL_HEX[hex_color.upper()]
    if not hex_color:
        return "card"
    return "card" if luminance(hex_color) > 160 else "navy"


def snap_ink(hex_color):
    if hex_color and hex_color.upper() in INK_HEX:
        return INK_HEX[hex_color.upper()]
    if not hex_color:
        return "ink"
    lum = luminance(hex_color)
    if lum > 200:
        return "white"
    if lum < 80:
        return "navy"
    return "ink"


def first_srgb(node):
    for color in node.iter(A_NS + "srgbClr"):
        value = color.attrib.get("val")
        if value and len(value) == 6:
            return value.upper()
    return ""


def shape_fill(sp_pr):
    for child in list(sp_pr):
        if child.tag == A_NS + "noFill":
            return None
        if child.tag == A_NS + "solidFill":
            return snap_fill(first_srgb(child))
    return None


def shape_box(el):
    sp_pr = None
    for child in list(el):
        if child.tag == P_NS + "spPr":
            sp_pr = child
            break
    if sp_pr is None:
        return None
    off = ext = None
    for child in list(sp_pr):
        if child.tag != A_NS + "xfrm":
            continue
        for part in list(child):
            if part.tag == A_NS + "off":
                off = (inches(part.attrib["x"]), inches(part.attrib["y"]))
            elif part.tag == A_NS + "ext" and "cx" in part.attrib:
                ext = (inches(part.attrib["cx"]), inches(part.attrib["cy"]))
    if off is None or ext is None:
        return None
    return off, ext, sp_pr


def shape_text(el):
    body = None
    for child in el.iter(P_NS + "txBody"):
        body = child
        break
    if body is None:
        return "", 14, False, "left", "ink"
    lines = []
    for paragraph in body.findall(A_NS + "p"):
        parts = []
        for run in paragraph.findall(A_NS + "r"):
            node = run.find(A_NS + "t")
            if node is not None and node.text:
                parts.append(node.text)
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    text = "\n".join(lines).strip()
    size, bold, align, ink = 14, False, "left", "ink"
    for run_pr in body.iter(A_NS + "rPr"):
        if "sz" in run_pr.attrib:
            size = int(round(int(run_pr.attrib["sz"]) / 100.0))
        bold = run_pr.attrib.get("b") in ("1", "true")
        ink = snap_ink(first_srgb(run_pr))
        break
    for paragraph_pr in body.iter(A_NS + "pPr"):
        align = {"ctr": "center", "r": "right"}.get(paragraph_pr.attrib.get("algn"), "left")
        break
    return text, size, bold, align, ink


def placeholder_type(el):
    for ph in el.iter(P_NS + "ph"):
        return ph.attrib.get("type", "body")
    return ""


def geometry(el):
    for geom in el.iter(A_NS + "prstGeom"):
        return geom.attrib.get("prst", "")
    return ""


def read_shape(el):
    if placeholder_type(el) == "sldNum":
        return None
    box = shape_box(el)
    if box is None:
        return None
    (x, y), (w, h), sp_pr = box
    if w <= 0:
        return None
    text, size, bold, align, ink = shape_text(el)
    size = max(8, min(80, size))
    kind_name = geometry(el)
    fill = shape_fill(sp_pr)
    if kind_name == "line" or el.tag == P_NS + "cxnSp":
        stroke = ""
        for line in sp_pr.iter(A_NS + "ln"):
            stroke = first_srgb(line)
            break
        return {
            "kind": "line",
            "x": x,
            "y": y,
            "w": w,
            "h": max(h, 0.0),
            "fill": snap_fill(stroke) if stroke else "accent",
        }
    if kind_name == "chevron":
        item = {"kind": "chevron", "x": x, "y": y, "w": w, "h": h, "fill": fill or "accent"}
    elif kind_name == "roundRect":
        item = {"kind": "roundRect", "x": x, "y": y, "w": w, "h": h, "fill": fill or "card"}
    elif text and fill is None:
        item = {
            "kind": "text",
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "text": text,
            "size": size,
            "bold": bold,
            "align": align,
            "ink": ink,
        }
    elif fill is not None:
        item = {"kind": "rect", "x": x, "y": y, "w": w, "h": h, "fill": fill}
    else:
        return None
    if text and item["kind"] != "text":
        item["text"] = text
        item["size"] = size
        item["bold"] = bold
        item["align"] = align
        item["ink"] = ink
    return item


def decompile_pptx(path):
    try:
        package = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        fail("source is not a pptx")
    slides = sorted(
        (name for name in package.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)),
        key=lambda name: int(re.search(r"(\d+)", os.path.basename(name)).group(1)),
    )
    if not slides:
        fail("source has no slides")
    if len(slides) > 40:
        fail("source has more than 40 slides")
    out = []
    for number, name in enumerate(slides, 1):
        root = ET.fromstring(package.read(name))
        canvas = root.find(P_NS + "cSld")
        tree = canvas.find(P_NS + "spTree") if canvas is not None else None
        if tree is None:
            fail("slide " + str(number) + " has no shapes")
        shapes = []
        for el in list(tree):
            tag = el.tag.split("}")[-1]
            if tag == "grpSp":
                fail("slide " + str(number) + " has grouped shapes")
            if tag not in ("sp", "cxnSp"):
                continue
            item = read_shape(el)
            if item:
                shapes.append(item)
        if not shapes:
            fail("slide " + str(number) + " has no drawn shapes")
        out.append({
            "n": number,
            "layout": "mirror",
            "slots": {},
            "shapes": check_shapes(shapes, number),
        })
    return out


def deck_title(slides):
    best = ""
    best_size = 0
    for shape in slides[0]["shapes"]:
        if shape.get("kind") != "text":
            continue
        size = shape.get("size") or 0
        text = shape.get("text") or ""
        if size >= best_size and text:
            best = text.split("\n")[0]
            best_size = size
    if len(best) > 120:
        best = best[:120].rstrip()
    return best or "Deck"


def check_shapes(shapes, n):
    label = "slide " + str(n)
    if not isinstance(shapes, list) or not shapes:
        fail(label + " has no shapes")
    if len(shapes) > 80:
        fail(label + " has too many shapes")
    clean = []
    for index, shape in enumerate(shapes, 1):
        where = label + " shape " + str(index)
        if not isinstance(shape, dict):
            fail(where + " must be an object")
        kind = shape.get("kind")
        if kind not in SHAPE_KINDS:
            fail(where + " has unknown kind " + repr(kind))
        try:
            x = float(shape["x"])
            y = float(shape["y"])
            w = float(shape["w"])
            h = float(shape["h"])
        except (KeyError, TypeError, ValueError):
            fail(where + " needs x, y, w, and h")
        if w <= 0 or h < 0 or (kind != "line" and h <= 0):
            fail(where + " has an empty box")
        item = {"kind": kind, "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}
        fill = shape.get("fill")
        if kind == "text":
            item["text"] = as_text(shape.get("text"), where)
            item["size"] = shape_size(shape.get("size"), where)
            item["bold"] = bool(shape.get("bold"))
            item["align"] = shape_align(shape.get("align"))
            item["ink"] = shape_role(shape.get("ink"), "ink", where)
        else:
            if fill not in ROLE:
                fail(where + " has unknown fill " + repr(fill))
            item["fill"] = fill
            if shape.get("text"):
                item["text"] = as_text(shape.get("text"), where)
                item["size"] = shape_size(shape.get("size"), where)
                item["bold"] = bool(shape.get("bold"))
                item["align"] = shape_align(shape.get("align"))
                item["ink"] = shape_role(shape.get("ink"), "ink", where)
        clean.append(item)
    return clean


def shape_size(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(where + " needs a font size")
    size = int(round(value))
    if size < 8 or size > 80:
        fail(where + " font size is out of range")
    return size


def shape_align(value):
    if value in (None, "left"):
        return "left"
    if value in ("center", "right"):
        return value
    fail("align must be left, center, or right")


def shape_role(value, fallback, where):
    if value in (None, ""):
        return fallback
    if value not in ("navy", "ink", "accent", "white"):
        fail(where + " has unknown ink " + repr(value))
    return value


def fit_shapes(shapes):
    min_x = min(shape["x"] for shape in shapes)
    min_y = min(shape["y"] for shape in shapes)
    max_x = max(shape["x"] + shape["w"] for shape in shapes)
    max_y = max(shape["y"] + max(shape["h"], 0.05) for shape in shapes)
    width = max(max_x - min_x, 0.1)
    height = max(max_y - min_y, 0.1)
    left, top, area_w, area_h = SAFE
    scale = min(area_w / width, area_h / height)
    offset_x = left + (area_w - width * scale) / 2.0
    offset_y = top + (area_h - height * scale) / 2.0
    fitted = []
    for shape in shapes:
        item = dict(shape)
        item["x"] = offset_x + (shape["x"] - min_x) * scale
        item["y"] = offset_y + (shape["y"] - min_y) * scale
        item["w"] = shape["w"] * scale
        item["h"] = shape["h"] * scale
        if shape["kind"] == "line":
            item["h"] = max(item["h"], 0.035)
        if "size" in item:
            item["size"] = max(9, int(round(item["size"] * scale)))
        fitted.append(item)
    return fitted


def paint_text(shape, text, size, bold, color, align):
    frame = shape.text_frame
    frame.word_wrap = True
    frame.auto_size = None
    frame.margin_left = Inches(0.04)
    frame.margin_right = Inches(0.04)
    frame.margin_top = Inches(0.02)
    frame.margin_bottom = Inches(0.02)
    frame.clear()
    alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
    lines = text.split("\n")
    first = frame.paragraphs[0]
    first.alignment = alignment
    run = first.add_run()
    run.text = lines[0]
    style_run(run, size, bold, color)
    for line in lines[1:]:
        paragraph = frame.add_paragraph()
        paragraph.alignment = alignment
        run = paragraph.add_run()
        run.text = line
        style_run(run, size, bold, color)
    try:
        frame._txBody.bodyPr.set("anchor", "t")
    except Exception:
        pass


def add_drawn_shape(slide, kind, x, y, w, h, fill):
    preset = {
        "roundRect": MSO_SHAPE.ROUNDED_RECTANGLE,
        "rect": MSO_SHAPE.RECTANGLE,
        "chevron": MSO_SHAPE.CHEVRON,
        "line": MSO_SHAPE.RECTANGLE,
    }[kind]
    drawn = slide.shapes.add_shape(preset, Inches(x), Inches(y), Inches(w), Inches(h))
    drawn.fill.solid()
    drawn.fill.fore_color.rgb = ROLE[fill]
    drawn.line.fill.background()
    if kind == "roundRect":
        try:
            drawn.adjustments[0] = 0.15
        except Exception:
            pass
    return drawn


def paint_mirror(prs, shapes, warnings, n):
    layout = find_layout(prs, MIRROR_PART[0], MIRROR_PART[1])
    slide = prs.slides.add_slide(layout)
    for shape in list(slide.shapes):
        if not shape.is_placeholder:
            continue
        kind = shape.placeholder_format.type
        if kind in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT):
            drop_shape(shape)
    for spec in fit_shapes(shapes):
        kind = spec["kind"]
        if kind == "text":
            box = slide.shapes.add_textbox(Inches(spec["x"]), Inches(spec["y"]), Inches(spec["w"]), Inches(spec["h"]))
            paint_text(box, spec["text"], spec["size"], spec["bold"], ROLE[spec["ink"]], spec["align"])
            continue
        drawn = add_drawn_shape(slide, kind, spec["x"], spec["y"], spec["w"], spec["h"], spec["fill"])
        if spec.get("text"):
            paint_text(drawn, spec["text"], spec["size"], spec["bold"], ROLE[spec["ink"]], spec["align"])
    if len(shapes) > 60:
        warnings.append("slide " + str(n) + ": " + str(len(shapes)) + " shapes")


def render_deck(paths, deck):
    slides = deck.get("slides") or []
    if not slides:
        fail("deck has no slides")
    if not os.path.isfile(TEMPLATE):
        fail("skill template is missing")
    try:
        prs = Presentation(TEMPLATE)
    except Exception:
        fail("could not open the template")
    drop_existing_slides(prs)
    warnings = []
    mirror = [slide.get("layout") == "mirror" for slide in slides]
    if any(mirror):
        if not all(mirror):
            fail("a restyled deck is all mirror slides")
        for spec in slides:
            shapes = check_shapes(spec.get("shapes"), spec.get("n"))
            paint_mirror(prs, shapes, warnings, spec.get("n"))
    else:
        check_variety(slides)
        for spec in slides:
            if spec.get("layout") not in LAYOUTS:
                fail("deck has unknown layout " + repr(spec.get("layout")))
            fill_slide(prs, spec, warnings)
    os.makedirs(os.path.dirname(paths["pptx"]), exist_ok=True)
    prs.save(paths["pptx"])
    return os.path.getsize(paths["pptx"]), warnings


def emit_built(op, slug, deck, size, warnings):
    slides = deck.get("slides") or []
    emit({
        "ok": True,
        "op": op,
        "slug": slug,
        "title": deck.get("title"),
        "path": slug + "/" + slug + ".pptx",
        "bytes": size,
        "slides": len(slides),
        "warnings": warnings,
    })


def cmd_compile(args):
    slug = check_slug(args.slug)
    paths = deck_paths(args.workspace, slug)
    deck = load_json(paths["deck"], "deck.json")
    size, warnings = render_deck(paths, deck)
    emit_built("compile", slug, deck, size, warnings)


def cmd_restyle(args):
    slug = check_slug(args.slug)
    source = args.source
    if not source or not os.path.isfile(source):
        fail("source pptx is missing")
    paths = deck_paths(args.workspace, slug)
    slides = decompile_pptx(source)
    deck = {
        "schema": "presentation-deck/v1",
        "keys": [],
        "updated_at": now(),
        "source_agent": "presentation",
        "slug": slug,
        "title": deck_title(slides),
        "slides": slides,
    }
    save_deck(paths, deck)
    size, warnings = render_deck(paths, deck)
    emit_built("restyle", slug, deck, size, warnings)


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

    restyle = sub.add_parser("restyle")
    restyle.add_argument("--workspace", required=True)
    restyle.add_argument("--slug", required=True)
    restyle.add_argument("--source", required=True)
    restyle.set_defaults(func=cmd_restyle)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        fail("use edit, show, compile, or restyle")
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
