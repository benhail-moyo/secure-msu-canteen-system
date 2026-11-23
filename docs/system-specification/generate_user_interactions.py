"""Generate UC-01, an editable UML use-case view of canteen interactions."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 2450, 2240
BLUE, INK, GRAY, AMBER = "#2774B8", "#182B40", "#718096", "#C98212"

ACTORS = {
    "visitor": ("Public visitor", 160, 215, 120, 130),
    "student": ("Student", 160, 635, 120, 160),
    "staff": ("Cashier", 160, 1190, 120, 150),
    "manager": ("Manager", 160, 1420, 120, 180),
    "admin": ("Administrator", 160, 1940, 120, 150),
}
EXTERNAL = {
    "smtp": ("SMTP email relay", 2050, 242.5, 330, 110, False),
    "provider": ("Payment provider (proposed)", 2050, 612.5, 330, 110, True),
}
CASES = {
    "register": ("Register and verify account", 810, 245, 500, 105, False),
    "browse": ("Browse meals", 810, 425, 500, 105, False),
    "checkout": ("Place order (demo checkout)", 810, 605, 500, 105, False),
    "ticket": ("View order and signed ticket", 810, 785, 500, 105, False),
    "feedback": ("Submit order feedback", 810, 965, 500, 105, False),
    "collect": ("Verify and collect ticket", 810, 1215, 500, 105, False),
    "menu": ("Manage menu", 810, 1435, 500, 105, False),
    "orders": ("Update orders and ticket expiry", 810, 1615, 500, 105, False),
    "alerts": ("Manage alerts", 810, 1795, 500, 105, False),
    "dashboard": ("View system counts", 810, 1965, 500, 105, False),
    "payment": ("Confirm provider payment", 1430, 610, 430, 115, True),
}

# Association routes are explicitly orthogonal. Human actor routes use a
# separate vertical lane for each use case to keep associations apart.
ASSOCIATIONS = [
    ("visitor", "register", .30, [(700, 254), (700, 297.5)], False),
    ("visitor", "browse", .70, [(650, 306), (650, 477.5)], False),
    ("student", "checkout", .19, [(700, 665.4), (700, 657.5)], False),
    ("student", "payment", .10,
     [(400, 651), (400, 560), (1380, 560), (1380, 667.5)], True),
    ("student", "ticket", .50, [(650, 715), (650, 837.5)], False),
    ("student", "feedback", .81, [(600, 764.6), (600, 1017.5)], False),
    ("staff", "collect", .50, [(680, 1265), (680, 1267.5)], False),
    ("manager", "menu", 1/6, [(700, 1450), (700, 1487.5)], False),
    ("manager", "orders", .50, [(650, 1510), (650, 1667.5)], False),
    ("manager", "alerts", 5/6, [(600, 1570), (600, 1847.5)], False),
    ("admin", "dashboard", .50, [(680, 2015), (680, 2017.5)], False),
    ("smtp", "register", .50, [], False),
    ("provider", "payment", .50, [], True),
]


def font(size: int, bold: bool = False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def add_vertex(parent, ident, label, style, x, y, w, h):
    cell = ET.SubElement(parent, "mxCell", id=ident, value=label, style=style,
                         vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w),
                  height=str(h), **{"as": "geometry"})


def add_association(parent, index, source, target, fraction, waypoints, planned):
    human = source in ACTORS
    exit_x, exit_y = (1, fraction) if human else (0, .5)
    entry_x, entry_y = (0, .5) if human else (1, .5)
    style = ("edgeStyle=segmentEdgeStyle;rounded=0;html=0;"
             "startArrow=none;endArrow=none;"
             f"exitX={exit_x:.16g};exitY={exit_y:.16g};exitPerimeter=0;"
             f"entryX={entry_x:.16g};entryY={entry_y:.16g};entryPerimeter=0;"
             f"strokeColor={AMBER if planned else GRAY};strokeWidth=2;"
             + ("dashed=1;dashPattern=8 6;" if planned else ""))
    cell = ET.SubElement(parent, "mxCell", id=f"association-{index}", value="",
                         style=style, edge="1", parent="1", source=source, target=target)
    geom = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
    if waypoints:
        array = ET.SubElement(geom, "Array", **{"as": "points"})
        for x, y in waypoints:
            ET.SubElement(array, "mxPoint", x=str(x), y=str(y))


def build_drawio():
    root = ET.Element("mxfile", host="app.diagrams.net", agent="Codex",
                      version="24.7.17", type="device")
    page = ET.SubElement(root, "diagram", id="UC-01-user-interactions",
                         name="User interactions and external actors")
    model = ET.SubElement(page, "mxGraphModel", dx=str(WIDTH), dy=str(HEIGHT),
                          grid="1", gridSize="10", guides="1", tooltips="1",
                          connect="1", arrows="1", fold="1", page="1",
                          pageScale="1", pageWidth=str(WIDTH), pageHeight=str(HEIGHT),
                          math="0", shadow="0")
    layer = ET.SubElement(model, "root")
    ET.SubElement(layer, "mxCell", id="0")
    ET.SubElement(layer, "mxCell", id="1", parent="0")
    add_vertex(layer, "system-boundary", "MSU Canteen System",
               "rounded=0;html=1;whiteSpace=wrap;fillColor=#F9FBFE;"
               f"strokeColor={BLUE};strokeWidth=2;fontColor={INK};fontSize=29;"
               "fontStyle=1;align=left;verticalAlign=top;spacingTop=22;spacingLeft=25;",
               450, 120, 1480, 1990)
    for index, (src, dst, fraction, waypoints, planned) in enumerate(ASSOCIATIONS, 1):
        add_association(layer, index, src, dst, fraction, waypoints, planned)
    for ident, (label, x, y, w, h) in ACTORS.items():
        add_vertex(layer, ident, label,
                   "shape=umlActor;html=1;whiteSpace=wrap;fillColor=none;"
                   f"strokeColor={GRAY};strokeWidth=2;fontColor={INK};fontSize=24;"
                   "verticalLabelPosition=bottom;verticalAlign=top;align=center;spacingTop=8;",
                   x, y, w, h)
    for ident, (label, x, y, w, h, planned) in EXTERNAL.items():
        add_vertex(layer, ident, label,
                   "rounded=0;html=1;whiteSpace=wrap;"
                   f"fillColor={'#FFF1D9' if planned else '#EEF2F7'};"
                   f"strokeColor={AMBER if planned else GRAY};strokeWidth=2;"
                   f"fontColor={INK};fontSize=23;align=center;verticalAlign=middle;"
                   + ("dashed=1;dashPattern=8 6;" if planned else ""),
                   x, y, w, h)
    for ident, (label, x, y, w, h, planned) in CASES.items():
        add_vertex(layer, ident, label,
                   "ellipse;html=1;whiteSpace=wrap;"
                   f"fillColor={'#FFF1D9' if planned else '#EAF3FC'};"
                   f"strokeColor={AMBER if planned else BLUE};strokeWidth=2;"
                   f"fontColor={INK};fontSize=23;align=center;verticalAlign=middle;"
                   + ("dashed=1;dashPattern=8 6;" if planned else ""),
                   x, y, w, h)
    add_vertex(layer, "future-label", "PROPOSED PAYMENT INTEGRATION",
               f"text;html=1;align=center;fontSize=18;fontStyle=1;fontColor={AMBER};",
               1410, 558, 470, 35)
    add_vertex(layer, "legend", "Solid = implemented interaction. Dashed amber = proposed integration; current checkout records demo payment only.",
               f"text;html=1;whiteSpace=wrap;align=left;fontSize=20;fontColor={INK};",
               455, 2150, 1900, 55)
    ET.ElementTree(root).write(OUT / "UC-01-user-interactions.drawio",
                               encoding="utf-8", xml_declaration=True)


def text_center(draw, rect, label, size=24, bold=False, fill=INK):
    x1, y1, x2, y2 = rect
    f = font(size, bold)
    box = draw.textbbox((0, 0), label, font=f)
    draw.text((x1 + (x2-x1-(box[2]-box[0]))/2,
               y1 + (y2-y1-(box[3]-box[1]))/2 - 4), label, fill=fill, font=f)


def dashed_line(draw, points, fill, width=3, dash=12, gap=8):
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        length = math.hypot(x2-x1, y2-y1)
        if not length:
            continue
        ux, uy = (x2-x1)/length, (y2-y1)/length
        pos = 0
        while pos < length:
            end = min(length, pos+dash)
            draw.line((x1+ux*pos, y1+uy*pos, x1+ux*end, y1+uy*end),
                      fill=fill, width=width)
            pos += dash+gap


def build_preview():
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((450, 120, 1930, 2110), fill="#F9FBFE", outline=BLUE, width=3)
    draw.text((480, 145), "MSU Canteen System", fill=INK, font=font(32, True))
    for src, dst, fraction, waypoints, planned in ASSOCIATIONS:
        if src in ACTORS:
            _, x, y, w, h = ACTORS[src]
            start = (x+w, y+h*fraction)
            _, tx, ty, tw, th, _ = CASES[dst]
            end = (tx, ty+th/2)
        else:
            _, x, y, w, h, _ = EXTERNAL[src]
            start = (x, y+h/2)
            _, tx, ty, tw, th, _ = CASES[dst]
            end = (tx+tw, ty+th/2)
        path = [start, *waypoints, end]
        assert all(a[0] == b[0] or a[1] == b[1]
                   for a, b in zip(path, path[1:])), (src, dst, path)
        if planned:
            dashed_line(draw, path, AMBER)
        else:
            draw.line(path, fill=GRAY, width=3)
    for _, (label, x, y, w, h) in ACTORS.items():
        cx = x+w/2
        draw.ellipse((cx-17, y+10, cx+17, y+44), outline=GRAY, width=4)
        draw.line((cx, y+44, cx, y+91), fill=GRAY, width=4)
        draw.line((cx-37, y+62, cx+37, y+62), fill=GRAY, width=4)
        draw.line((cx, y+91, cx-31, y+122), fill=GRAY, width=4)
        draw.line((cx, y+91, cx+31, y+122), fill=GRAY, width=4)
        text_center(draw, (x-80, y+h+1, x+w+80, y+h+46), label, 24, True)
    for _, (label, x, y, w, h, planned) in EXTERNAL.items():
        fill = "#FFF1D9" if planned else "#EEF2F7"
        draw.rectangle((x, y, x+w, y+h), fill=fill, outline=AMBER if planned else GRAY, width=3)
        text_center(draw, (x, y, x+w, y+h), label, 22, True)
    for _, (label, x, y, w, h, planned) in CASES.items():
        draw.ellipse((x, y, x+w, y+h), fill="#FFF1D9" if planned else "#EAF3FC",
                     outline=AMBER if planned else BLUE, width=3)
        text_center(draw, (x+12, y, x+w-12, y+h), label, 22, True)
    draw.text((1440, 565), "PROPOSED PAYMENT INTEGRATION", fill=AMBER, font=font(20, True))
    draw.text((455, 2155),
              "Solid = implemented interaction. Dashed amber = proposed integration; current checkout records demo payment only.",
              fill=INK, font=font(20))
    image.save(OUT / "UC-01-user-interactions.png", optimize=True)


if __name__ == "__main__":
    build_drawio()
    build_preview()
