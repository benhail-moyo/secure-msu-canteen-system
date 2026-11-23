"""Generate the current-state UML use-case drawing for the MSU canteen."""
from pathlib import Path
import xml.etree.ElementTree as ET


OUTPUT = Path(__file__).with_name("Use Case Diagram.drawio")
INK = "#243247"
BLUE = "#315A82"
MUTED = "#5D6D7E"
PAGE_WIDTH = 1750


def shape(root, ident, label, style, x, y, width, height):
    cell = ET.SubElement(root, "mxCell", id=ident, value=label, style=style,
                         vertex="1", parent="1")
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y),
                  width=str(width), height=str(height), **{"as": "geometry"})


def connector(root, ident, source, target, kind="association", exit_y=None):
    if kind == "association":
        style = "endArrow=none;"
        if exit_y is not None:
            style += f"exitX=1;exitY={exit_y:.3f};exitPerimeter=0;"
    else:
        style = "endArrow=open;endFill=0;dashed=1;dashPattern=8 6;"
    style += (f"html=1;rounded=0;strokeColor={INK};strokeWidth=1.7;"
              f"fontColor={INK};fontSize=16;labelBackgroundColor=#FFFFFF;")
    cell = ET.SubElement(root, "mxCell", id=ident,
                         value="" if kind == "association" else f"«{kind}»",
                         style=style, edge="1", parent="1", source=source,
                         target=target)
    ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})


def create_page(mxfile, ident, title, height=1250, boundary_bottom=1100):
    diagram = ET.SubElement(mxfile, "diagram", id=ident, name=title)
    graph = ET.SubElement(diagram, "mxGraphModel", dx=str(PAGE_WIDTH),
                          dy=str(height), grid="1", gridSize="10", guides="1",
                          tooltips="1", connect="1", arrows="1", fold="1",
                          page="1", pageScale="1", pageWidth=str(PAGE_WIDTH),
                          pageHeight=str(height), math="0", shadow="0")
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    shape(root, ident + "-boundary", "MSU Canteen System",
          "rounded=0;html=1;whiteSpace=wrap;fillColor=none;"
          f"strokeColor={INK};strokeWidth=2;fontColor={INK};fontSize=22;"
          "fontStyle=1;align=left;verticalAlign=top;spacingLeft=18;spacingTop=14;",
          310, 130, 1120, boundary_bottom - 130)
    shape(root, ident + "-heading", title,
          f"text;html=1;align=left;fontColor={INK};fontSize=28;fontStyle=1;",
          310, 45, 900, 45)
    return root


ACTOR_STYLE = ("shape=umlActor;html=1;whiteSpace=wrap;fillColor=none;"
               f"strokeColor={INK};strokeWidth=2;fontColor={INK};fontSize=19;"
               "verticalLabelPosition=bottom;verticalAlign=top;align=center;")
USE_CASE_STYLE = ("ellipse;html=1;whiteSpace=wrap;fillColor=#FFFFFF;"
                  f"strokeColor={BLUE};strokeWidth=2;fontColor={INK};fontSize=18;"
                  "align=center;verticalAlign=middle;spacing=8;")
NOTE_STYLE = ("shape=note;html=1;whiteSpace=wrap;fillColor=#F5F7FA;"
              f"strokeColor=#B8C5D1;fontColor={MUTED};fontSize=15;"
              "align=left;verticalAlign=middle;spacing=12;")


def actor(root, ident, label, x, y):
    shape(root, ident, label, ACTOR_STYLE, x, y, 115, 145)


def use_case(root, ident, label, x, y, width=430):
    shape(root, ident, label, USE_CASE_STYLE, x, y, width, 78)


def fan(root, actor_id, cases, prefix):
    """Use ordered exit points so actor associations form a readable fan."""
    for number, case_id in enumerate(cases, 1):
        fraction = number / (len(cases) + 1)
        connector(root, f"{prefix}-{number}", actor_id, case_id,
                  exit_y=fraction)


def build_visitor(mxfile):
    root = create_page(mxfile, "visitor", "01  Visitor and account access")
    actor(root, "visitor-actor", "Visitor", 90, 525)
    actor(root, "visitor-email", "Email service", 1535, 510)
    for ident, label, y in [
        ("visitor-register", "Register account", 240),
        ("visitor-login", "Log in as student", 370),
        ("visitor-browse", "Browse and search menu", 500),
        ("visitor-cart", "Manage cart", 630),
    ]:
        use_case(root, ident, label, 460, y)
    use_case(root, "visitor-verify", "Confirm registration by email code", 1010, 240, 350)
    use_case(root, "visitor-stale", "Confirm older login by email code", 1010, 370, 350)
    fan(root, "visitor-actor", ["visitor-register", "visitor-login",
                                "visitor-browse", "visitor-cart"], "visitor-action")
    connector(root, "visitor-email-register", "visitor-email", "visitor-verify")
    connector(root, "visitor-email-login", "visitor-email", "visitor-stale")
    connector(root, "visitor-register-verify", "visitor-register", "visitor-verify", "include")
    connector(root, "visitor-stale-login", "visitor-stale", "visitor-login", "extend")
    shape(root, "visitor-note",
          "Older login confirmation applies when the student last logged in at least 7 days ago. "
          "Cart actions are available before sign-in.", NOTE_STYLE, 455, 830, 900, 105)


def build_student(mxfile):
    root = create_page(mxfile, "student", "02  Student ordering and feedback", 1400, 1260)
    actor(root, "student-actor", "Student", 90, 665)
    actor(root, "student-email", "Email service", 1535, 620)
    for ident, label, y in [
        ("student-browse", "Browse and search menu", 220),
        ("student-cart", "Manage cart", 335),
        ("student-order", "Place order (demo checkout)", 450),
        ("student-list", "View own orders and status", 565),
        ("student-ticket", "View signed meal ticket", 680),
        ("student-feedback", "Submit feedback for completed order", 795),
        ("student-logout", "Log out", 910),
    ]:
        use_case(root, ident, label, 455, y, 460)
    use_case(root, "student-high", "Confirm high-value order by email code", 1005, 450, 355)
    fan(root, "student-actor", ["student-browse", "student-cart",
                                "student-order", "student-list", "student-ticket",
                                "student-feedback", "student-logout"], "student-action")
    connector(root, "student-high-order", "student-high", "student-order", "extend")
    connector(root, "student-email-high", "student-email", "student-high")
    shape(root, "student-note",
          "High-value confirmation applies when an order total exceeds $100. "
          "Checkout records a demo payment; no payment provider is connected. "
          "Feedback is available after completion.", NOTE_STYLE,
          455, 1060, 900, 125)


def build_staff(mxfile):
    root = create_page(mxfile, "staff", "03  Counter staff and collection", 1430, 1290)
    actor(root, "staff-actor", "Counter staff", 90, 665)
    for ident, label, y in [
        ("staff-login", "Log in with staff access key", 215),
        ("staff-orders", "View all orders", 325),
        ("staff-details", "View order details and ticket", 435),
        ("staff-verify", "Verify QR or manual ticket code", 545),
        ("staff-approve", "Approve meal collection", 655),
        ("staff-browse", "Browse menu", 765),
        ("staff-cart", "Manage cart", 875),
        ("staff-logout", "Log out", 985),
    ]:
        use_case(root, ident, label, 560, y, 560)
    fan(root, "staff-actor", ["staff-login", "staff-orders", "staff-details",
                              "staff-verify", "staff-approve", "staff-browse",
                              "staff-cart", "staff-logout"], "staff-action")
    connector(root, "staff-approve-verify", "staff-approve", "staff-verify", "include")
    shape(root, "staff-note",
          "Approval records the collecting staff account and time, and sets the order status to completed. "
          "Verification checks payment marker, expiry, cancellation, and prior collection.",
          NOTE_STYLE, 480, 1120, 860, 105)


def build_manager(mxfile):
    root = create_page(mxfile, "manager", "04  Manager operations", 1640, 1510)
    actor(root, "manager-actor", "Manager", 90, 795)
    for ident, label, y in [
        ("manager-login", "Log in with manager access key", 210),
        ("manager-summary", "View order and sales summary", 320),
        ("manager-menu", "Add, edit, or delete menu items", 430),
        ("manager-orders", "Search, filter, and view orders", 540),
        ("manager-status", "Change order status", 650),
        ("manager-items", "Edit ordered meals and quantities", 760),
        ("manager-extension", "Extend eligible ticket expiry", 870),
        ("manager-alerts", "Create, activate, or delete alerts", 980),
        ("manager-browse", "Browse menu", 1090),
        ("manager-cart", "Manage cart", 1200),
        ("manager-logout", "Log out", 1310),
    ]:
        use_case(root, ident, label, 560, y, 560)
    fan(root, "manager-actor", ["manager-login", "manager-summary", "manager-menu",
                                "manager-orders", "manager-status", "manager-items",
                                "manager-extension", "manager-alerts", "manager-browse",
                                "manager-cart", "manager-logout"], "manager-action")


def build_admin(mxfile):
    root = create_page(mxfile, "admin", "05  Administrator overview")
    actor(root, "admin-actor", "Administrator", 90, 530)
    for ident, label, y in [
        ("admin-login", "Log in with administrator access key", 280),
        ("admin-counts", "View student, staff, order, and menu counts", 415),
        ("admin-orders", "View all orders", 550),
        ("admin-browse", "Browse menu", 685),
        ("admin-cart", "Manage cart", 820),
        ("admin-logout", "Log out", 955),
    ]:
        use_case(root, ident, label, 560, y, 590)
    fan(root, "admin-actor", ["admin-login", "admin-counts", "admin-orders",
                              "admin-browse", "admin-cart", "admin-logout"], "admin-action")


def build():
    mxfile = ET.Element("mxfile", host="app.diagrams.net", agent="Codex",
                        version="24.7.17", type="device")
    for builder in (build_visitor, build_student, build_staff,
                    build_manager, build_admin):
        builder(mxfile)
    ET.indent(mxfile, space="  ")
    ET.ElementTree(mxfile).write(OUTPUT, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    build()
