"""Build the editable, current-state UML use-case diagrams in one draw.io file."""
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "UC-02-professional-use-cases.drawio"
INK = "#243247"
BLUE = "#315A82"


def vertex(root, ident, label, style, x, y, width, height):
    cell = ET.SubElement(root, "mxCell", id=ident, value=label, style=style,
                         vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(width),
                  height=str(height), **{"as": "geometry"})


def edge(root, ident, source, target, included=False):
    style = ("endArrow=open;endFill=0;dashed=1;dashPattern=7 5;"
             if included else "endArrow=none;")
    style += f"html=1;rounded=0;strokeColor={INK};strokeWidth=1.6;fontColor={INK};fontSize=17;"
    cell = ET.SubElement(root, "mxCell", id=ident,
                         value="«include»" if included else "", style=style,
                         edge="1", parent="1", source=source, target=target)
    ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})


def page(mxfile, ident, name, width=1850, height=1220):
    diagram = ET.SubElement(mxfile, "diagram", id=ident, name=name)
    model = ET.SubElement(diagram, "mxGraphModel", dx=str(width), dy=str(height),
                          grid="1", gridSize="10", guides="1", tooltips="1",
                          connect="1", arrows="1", fold="1", page="1",
                          pageScale="1", pageWidth=str(width),
                          pageHeight=str(height), math="0", shadow="0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    vertex(root, ident + "-boundary", "MSU Canteen System",
           "rounded=0;whiteSpace=wrap;html=1;fillColor=none;"
           f"strokeColor={INK};strokeWidth=2;fontColor={INK};fontSize=23;"
           "fontStyle=1;align=left;verticalAlign=top;spacingLeft=18;spacingTop=15;",
           350, 130, 1130, 990)
    return root


ACTOR = ("shape=umlActor;html=1;whiteSpace=wrap;fillColor=none;"
         f"strokeColor={INK};strokeWidth=2;fontColor={INK};fontSize=19;"
         "verticalLabelPosition=bottom;verticalAlign=top;align=center;")
CASE = ("ellipse;html=1;whiteSpace=wrap;fillColor=#FFFFFF;"
        f"strokeColor={BLUE};strokeWidth=2;fontColor={INK};fontSize=19;"
        "align=center;verticalAlign=middle;spacing=8;")


def add_actor(root, ident, label, x, y):
    vertex(root, ident, label, ACTOR, x, y, 120, 125)


def add_case(root, ident, label, x, y, width=340):
    vertex(root, ident, label, CASE, x, y, width, 78)


def build():
    mxfile = ET.Element("mxfile", host="app.diagrams.net", agent="Codex",
                        version="24.7.17", type="device")

    root = page(mxfile, "uc-ordering", "01 - Ordering and collection")
    add_actor(root, "visitor", "Visitor", 100, 280)
    add_actor(root, "student", "Student", 100, 630)
    add_actor(root, "staff", "Counter staff", 1600, 940)

    for ident, label, y in [
        ("register", "Register account", 220),
        ("browse", "Browse menu", 350),
        ("cart", "Manage cart", 480),
        ("order", "Place order", 610),
        ("ticket", "View orders and signed ticket", 740),
        ("feedback", "Submit order feedback", 870),
    ]:
        add_case(root, ident, label, 500, y)
    add_case(root, "demo", "Complete demo checkout", 1030, 610, 360)
    add_case(root, "verify", "Verify meal ticket", 1030, 870, 360)
    add_case(root, "redeem", "Redeem meal ticket", 1030, 1000, 360)

    for ident, source, target in [
        ("visitor-register", "visitor", "register"),
        ("visitor-browse", "visitor", "browse"),
        ("student-browse", "student", "browse"),
        ("student-cart", "student", "cart"),
        ("student-order", "student", "order"),
        ("student-ticket", "student", "ticket"),
        ("student-feedback", "student", "feedback"),
        ("staff-verify", "staff", "verify"),
        ("staff-redeem", "staff", "redeem"),
    ]:
        edge(root, ident, source, target)
    edge(root, "order-includes-demo", "order", "demo", True)
    edge(root, "redeem-includes-verify", "redeem", "verify", True)

    root = page(mxfile, "uc-operations", "02 - Canteen management")
    add_actor(root, "manager", "Manager", 100, 570)
    add_actor(root, "admin", "Administrator", 1600, 940)
    for ident, label, y in [
        ("menu", "Manage menu items", 220),
        ("view-orders", "View and search orders", 340),
        ("status", "Update order status", 460),
        ("items", "Edit order items", 580),
        ("extension", "Extend ticket expiry", 700),
        ("alerts", "Manage alerts", 820),
        ("summary", "View sales and order summary", 940),
    ]:
        add_case(root, ident, label, 560, y, 400)
        edge(root, "manager-" + ident, "manager", ident)
    add_case(root, "counts", "View system counts", 1080, 940, 330)
    edge(root, "admin-counts", "admin", "counts")

    ET.indent(mxfile, space="  ")
    ET.ElementTree(mxfile).write(OUTPUT, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    build()
