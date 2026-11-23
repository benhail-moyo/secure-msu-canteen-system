"""Build the four-page editable workflow and risk-control activity diagram."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
WIDTH = 2400
COLOR = {
    "user": ("#EEF2F7", "#718096"),
    "current": ("#EAF3FC", "#2774B8"),
    "planned": ("#FFF1D9", "#C98212"),
    "decision": ("#EAF3FC", "#2774B8"),
    "reject": ("#FCE8E8", "#C85A5A"),
    "success": ("#E3F5E9", "#38835A"),
    "note": ("#FFFAEE", "#B08935"),
}
INK = "#182B40"


def N(ident, label, x, y, w=500, h=105, kind="current"):
    return dict(id=ident, label=label, x=x, y=y, w=w, h=h, kind=kind)


def E(src, dst, source_side="right", target_side="left", label="", via=()):
    return dict(src=src, dst=dst, source_side=source_side,
                target_side=target_side, label=label, via=list(via))


def H(src, dst, label=""):
    return E(src, dst, "right", "left", label)


def L(src, dst, label=""):
    return E(src, dst, "left", "right", label)


def V(src, dst, label=""):
    return E(src, dst, "bottom", "top", label)


PAGES = [
    dict(id="WF-01-login", title="1  Login and access", height=1820,
         lanes=[("User: student / staff / manager / admin", 60, 520),
                ("Canteen application", 550, 1750),
                ("SMTP relay", 1780, 2360)],
         nodes=[
             N("start", "", 276, 214, 48, 48, "start"),
             N("credentials", "Submit login credentials", 100, 290, 400, 105, "user"),
             N("authenticate", "Check password or role key\nand account / role", 900, 290),
             N("valid", "Credentials\nvalid?", 1040, 490, 220, 140, "decision"),
             N("reject-login", "Reject login; show\ngeneric error", 1450, 510, 270, 100, "reject"),
             N("end-bad-login", "", 1547, 640, 76, 76, "end"),
             N("challenge", "When needed, start email challenge\n(unverified or stale student login)", 900, 720, 500, 125),
             N("relay", "Send verification code\n(if SMTP configured)", 1830, 730, 470, 105, "user"),
             N("enter-code", "Enter code if prompted", 100, 960, 400, 105, "user"),
             N("check-code", "Check challenge response", 900, 960),
             N("code-valid", "Valid or not\nrequired?", 1040, 1160, 220, 140, "decision"),
             N("reject-code", "Reject invalid challenge", 1450, 1180, 270, 100, "reject"),
             N("end-bad-code", "", 1547, 1320, 76, 76, "end"),
             N("session", "Create login session;\nredirect by role", 900, 1410),
             N("dashboard", "Open role dashboard", 100, 1410, 400, 105, "user"),
             N("end", "", 262, 1600, 76, 76, "end"),
             N("risk-note", "PROPOSED: individual staff accounts, expiring and attempt-limited codes, login rate limits.\nCURRENT: staff, manager and admin access keys can create accounts on first login.",
               680, 1550, 1540, 115, "note"),
         ], edges=[
             V("start", "credentials"), H("credentials", "authenticate"),
             V("authenticate", "valid"), H("valid", "reject-login", "[no]"),
             V("reject-login", "end-bad-login"),
             V("valid", "challenge", "[yes]"), H("challenge", "relay", "[if needed]"),
             E("relay", "enter-code", "left", "right", "email code",
               [(1780, 782.5), (1780, 910), (540, 910), (540, 1012.5)]),
             H("enter-code", "check-code"), V("check-code", "code-valid"),
             H("code-valid", "reject-code", "[no]"),
             V("reject-code", "end-bad-code"),
             V("code-valid", "session", "[yes]"), L("session", "dashboard"),
             V("dashboard", "end"),
         ],
         footer="Current challenge codes live in the signed browser session; stronger challenge controls are proposed."),
    dict(id="WF-02-order", title="2  Place an order and verify payment", height=2360,
         lanes=[("Student", 60, 520), ("Canteen application", 550, 1750),
                ("Payment provider (proposed)", 1780, 2360)],
         nodes=[
             N("start", "", 276, 214, 48, 48, "start"),
             N("cart", "Choose meals and quantities", 100, 270, 400, 105, "user"),
             N("validate-cart", "Recheck availability, quantity,\nprice and student role", 900, 270),
             N("cart-valid", "Cart and access\nvalid?", 1020, 470, 260, 140, "decision"),
             N("cart-reject", "Return to cart;\nno order or ticket", 1450, 490, 270, 100, "reject"),
             N("end-bad-cart", "", 1547, 630, 76, 76, "end"),
             N("checkout", "Submit checkout request", 100, 680, 400, 105, "user"),
             N("checkout-check", "Check CSRF; require email code\nfor orders above $100", 900, 680),
             N("pending", "Create pending-payment order\nwith fixed server total", 900, 910, 500, 110, "planned"),
             N("provider-authorize", "Process payment request", 1830, 910, 470, 110, "planned"),
             N("provider-webhook", "Send signed server-to-server\npayment confirmation", 1830, 1140, 470, 110, "planned"),
             N("verify-webhook", "Verify signature, order, amount,\nevent ID and idempotency", 900, 1140, 500, 110, "planned"),
             N("confirmed", "Provider confirms\nvalid payment?", 1010, 1370, 280, 140, "decision"),
             N("payment-reject", "Keep pending / flag mismatch;\nissue no ticket", 1450, 1390, 270, 100, "reject"),
             N("end-bad-payment", "", 1547, 1530, 76, 76, "end"),
             N("mark-paid", "Atomically mark paid after\nverified provider event", 900, 1600, 500, 110, "planned"),
             N("ticket", "Issue RSA-PSS signed QR\nfrom paid order", 900, 1830, 500, 110),
             N("show-ticket", "View order and ticket", 100, 1830, 400, 110, "user"),
             N("end", "", 262, 2030, 76, 76, "end"),
             N("reconcile", "PROPOSED: daily reconciliation of\nprovider settlements and issued tickets", 1810, 1780, 500, 120, "note"),
             N("prototype-note", "CURRENT PROTOTYPE: checkout accepts a demo method / reference and sets paid_at locally.\nThe provider sequence above is a required future control, not a live integration.",
               700, 2120, 1510, 110, "note"),
         ], edges=[
             V("start", "cart"), H("cart", "validate-cart"),
             V("validate-cart", "cart-valid"), H("cart-valid", "cart-reject", "[no]"),
             V("cart-reject", "end-bad-cart"),
             E("cart-valid", "checkout", "left", "top", "[yes]",
               [(770, 540), (770, 640), (300, 640)]),
             H("checkout", "checkout-check"), V("checkout-check", "pending"),
             H("pending", "provider-authorize"), V("provider-authorize", "provider-webhook"),
             L("provider-webhook", "verify-webhook"), V("verify-webhook", "confirmed"),
             H("confirmed", "payment-reject", "[no]"),
             V("payment-reject", "end-bad-payment"),
             V("confirmed", "mark-paid", "[yes]"), V("mark-paid", "ticket"),
             L("ticket", "show-ticket"), V("show-ticket", "end"),
         ],
         footer="Control: browser success or a user-entered reference never establishes paid status in the proposed design."),
    dict(id="WF-03-collection", title="3  Verify and collect an order", height=2370,
         lanes=[("Student", 60, 420), ("Counter staff", 450, 850),
                ("Canteen application", 880, 1780), ("Order database", 1810, 2360)],
         nodes=[
             N("start", "", 217, 214, 46, 46, "start"),
             N("present", "Present QR or manual code", 95, 270, 290, 105, "user"),
             N("scan", "Scan or enter code\nand registration", 490, 270, 320, 105, "user"),
             N("access", "Require staff role and\nserve-page CSRF", 1080, 270, 480, 105),
             N("resolve", "Verify RSA-PSS QR signature\nor manual code + registration", 1080, 500, 480, 115),
             N("state", "Check server order, paid marker,\nexpiry, cancellation and prior use", 1080, 735, 480, 115),
             N("eligible", "Eligible?", 1200, 980, 240, 140, "decision"),
             N("reject", "Reject invalid, expired\nor reused ticket", 1480, 1000, 270, 100, "reject"),
             N("end-bad-ticket", "", 1577, 1130, 76, 76, "end"),
             N("photo", "Compare student name / photo\nat counter", 490, 1230, 320, 105, "planned"),
             N("approve", "Approve collection", 490, 1460, 320, 105, "user"),
             N("recheck", "Recheck eligibility immediately\nbefore update", 1080, 1460, 480, 105),
             N("atomic", "Conditional update: collected_at,\ncollected_by_id, completed", 1850, 1460, 460, 105),
             N("updated", "One row\nupdated?", 1200, 1690, 240, 140, "decision"),
             N("duplicate", "Reject duplicate approval", 1480, 1710, 270, 100, "reject"),
             N("end-duplicate", "", 1577, 1850, 76, 76, "end"),
             N("serve", "Serve meal to student", 490, 1940, 320, 105, "user"),
             N("end", "", 612, 2140, 76, 76, "end"),
             N("risk-note", "CURRENT: online RSA verification and atomic single-use update; paid_at can come from demo checkout.\nPROPOSED: student photo check, individual cashier audit trail; controlled offline fallback requires separate design.",
               930, 2090, 1400, 115, "note"),
         ], edges=[
             V("start", "present"), H("present", "scan"), H("scan", "access"),
             V("access", "resolve"), V("resolve", "state"), V("state", "eligible"),
             H("eligible", "reject", "[no]"), V("reject", "end-bad-ticket"),
             E("eligible", "photo", "left", "right", "[yes]",
               [(1010, 1050), (1010, 1282.5)]),
             V("photo", "approve"), H("approve", "recheck"), H("recheck", "atomic"),
             E("atomic", "updated", "bottom", "top", "update result",
               [(2080, 1640), (1320, 1640)]),
             H("updated", "duplicate", "[no]"), V("duplicate", "end-duplicate"),
             E("updated", "serve", "left", "right", "[yes]",
               [(1010, 1760), (1010, 1992.5)]),
             V("serve", "end"),
         ],
         footer="A scan is advisory; approval rechecks state and uses a conditional database update to prevent replay."),
    dict(id="WF-04-edit", title="4  Edit order details", height=2380, width=2620,
         lanes=[("Manager", 60, 480), ("Canteen application", 510, 1580),
                ("Payment provider (proposed)", 1610, 2050),
                ("Order database", 2080, 2560)],
         nodes=[
             N("start", "", 247, 214, 46, 46, "start"),
             N("open", "Find and open order", 90, 270, 360, 105, "user"),
             N("auth", "Require manager role;\ncheck edit form CSRF", 760, 270, 500, 105),
             N("load", "Load order and current state", 760, 500, 500, 105),
             N("editable", "Item edit allowed?\nOpen and uncollected", 870, 730, 280, 140, "decision"),
             N("reject", "Reject edit to closed\nor collected order", 1280, 750, 270, 100, "reject"),
             N("end-bad-edit", "", 1377, 890, 76, 76, "end"),
             N("submit", "Submit meal and\nquantity changes", 90, 960, 360, 105, "user"),
             N("validate", "Validate availability and\nquantity; recalculate total", 760, 960, 500, 105),
             N("amount", "Paid amount\nchanges?", 870, 1185, 280, 140, "decision"),
             N("adjust", "Process adjustment\nor refund", 1640, 1200, 380, 110, "planned"),
             N("confirm-adjust", "Return signed adjustment\nconfirmation", 1640, 1430, 380, 110, "planned"),
             N("verify-adjust", "Verify provider adjustment\nbefore changing paid total", 760, 1430, 500, 110, "planned"),
             N("commit", "Commit validated order change", 760, 1660, 500, 110),
             N("persist", "Persist items and total", 2110, 1660, 400, 110),
             N("result", "Review updated order", 90, 1890, 360, 105, "user"),
             N("end", "", 232, 2090, 76, 76, "end"),
             N("risk-note", "CURRENT: paid item edits can change totals without provider adjustment. Status and ticket extension have separate manager actions.\nPROPOSED: reconcile price changes with provider and append immutable manager audit events.",
               590, 2130, 1870, 115, "note"),
         ], edges=[
             V("start", "open"), H("open", "auth"), V("auth", "load"),
             V("load", "editable"), H("editable", "reject", "[no]"),
             V("reject", "end-bad-edit"),
             E("editable", "submit", "left", "top", "[yes]",
               [(650, 800), (650, 920), (270, 920)]),
             H("submit", "validate"), V("validate", "amount"),
             H("amount", "adjust", "[yes]"), V("adjust", "confirm-adjust"),
             L("confirm-adjust", "verify-adjust"), V("verify-adjust", "commit"),
             E("amount", "commit", "left", "left", "[no]",
               [(650, 1255), (650, 1715)]),
             H("commit", "persist"),
             E("persist", "result", "left", "right", "saved",
               [(2065, 1715), (2065, 1840), (480, 1840), (480, 1942.5)]),
             V("result", "end"),
         ],
         footer="Changing a paid order total must not silently diverge from provider settlement in the proposed design."),
]


def port(node, side):
    x, y, w, h = (node[k] for k in ("x", "y", "w", "h"))
    return {"left": (x, y+h/2), "right": (x+w, y+h/2),
            "top": (x+w/2, y), "bottom": (x+w/2, y+h)}[side]


def path_for(edge, nodes):
    path = [port(nodes[edge["src"]], edge["source_side"]),
            *edge["via"], port(nodes[edge["dst"]], edge["target_side"])]
    assert all(a[0] == b[0] or a[1] == b[1]
               for a, b in zip(path, path[1:])), (edge, path)
    return path


def make_drawio():
    root = ET.Element("mxfile", host="app.diagrams.net", agent="Codex",
                      version="24.7.17", type="device")
    for page_data in PAGES:
        width, height = page_data.get("width", WIDTH), page_data["height"]
        page = ET.SubElement(root, "diagram", id=page_data["id"], name=page_data["title"])
        model = ET.SubElement(page, "mxGraphModel", dx=str(width), dy=str(height),
                              grid="1", gridSize="10", guides="1", tooltips="1",
                              connect="1", arrows="1", fold="1", page="1", pageScale="1",
                              pageWidth=str(width), pageHeight=str(height), math="0", shadow="0")
        layer = ET.SubElement(model, "root")
        ET.SubElement(layer, "mxCell", id="0")
        ET.SubElement(layer, "mxCell", id="1", parent="0")
        for index, (name, left, right) in enumerate(page_data["lanes"]):
            cell = ET.SubElement(layer, "mxCell", id=f"lane-{index}", value=name,
                                 style="swimlane;startSize=72;horizontal=1;rounded=0;"
                                       "container=0;collapsible=0;html=1;whiteSpace=wrap;"
                                       f"fillColor={'#F9FBFE' if index % 2 == 0 else '#F4F8FC'};"
                                       "strokeColor=#C8D6E3;strokeWidth=2;"
                                       f"fontColor={INK};fontSize=24;fontStyle=1;align=center;",
                                 vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry", x=str(left), y="140", width=str(right-left),
                          height=str(height-260), **{"as": "geometry"})
        nodes = {n["id"]: n for n in page_data["nodes"]}
        for index, edge in enumerate(page_data["edges"], 1):
            path = path_for(edge, nodes)
            src, dst = nodes[edge["src"]], nodes[edge["dst"]]
            source = path[0]
            target = path[-1]
            ex, ey = ((source[0]-src["x"])/src["w"], (source[1]-src["y"])/src["h"])
            tx, ty = ((target[0]-dst["x"])/dst["w"], (target[1]-dst["y"])/dst["h"])
            style = ("edgeStyle=segmentEdgeStyle;rounded=0;html=0;"
                     "endArrow=block;endFill=1;strokeColor=#697E91;strokeWidth=2;"
                     f"exitX={ex:.16g};exitY={ey:.16g};exitPerimeter=0;"
                     f"entryX={tx:.16g};entryY={ty:.16g};entryPerimeter=0;"
                     "fontSize=19;fontColor=#344A5F;labelBackgroundColor=#FFFFFF;")
            cell = ET.SubElement(layer, "mxCell", id=f"flow-{index}",
                                 value=edge["label"], style=style, edge="1", parent="1",
                                 source=edge["src"], target=edge["dst"])
            geom = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
            if edge["via"]:
                points = ET.SubElement(geom, "Array", **{"as": "points"})
                for x, y in edge["via"]:
                    ET.SubElement(points, "mxPoint", x=str(x), y=str(y))
        for n in page_data["nodes"]:
            fill, stroke = COLOR.get(n["kind"], ("#172B40", "#172B40"))
            if n["kind"] in ("start", "end"):
                shape = "shape=startState" if n["kind"] == "start" else "shape=endState"
                style = f"{shape};fillColor=#172B40;strokeColor=#172B40;"
            elif n["kind"] == "decision":
                style = f"rhombus;fillColor={fill};strokeColor={stroke};strokeWidth=2;"
            else:
                style = (f"rounded={0 if n['kind'] == 'note' else 1};arcSize=14;"
                         f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
                         + ("dashed=1;dashPattern=7 5;" if n["kind"] == "note" else ""))
            style += ("html=1;whiteSpace=wrap;align=center;verticalAlign=middle;"
                      f"fontColor={INK};fontSize={19 if n['kind']=='note' else 22};spacing=7;")
            cell = ET.SubElement(layer, "mxCell", id=n["id"], value=n["label"].replace("\n", "<br>"),
                                 style=style, vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry", x=str(n["x"]), y=str(n["y"]),
                          width=str(n["w"]), height=str(n["h"]), **{"as": "geometry"})
        for ident, value, x, y, w, h in (
            ("title", "act  " + page_data["title"], 60, 38, width-120, 65),
            ("legend", "Blue = implemented   |   Amber = proposed control   |   Red = rejected request   |   Gray = user or external action",
             70, height-101, width-140, 35),
            ("footer", page_data["footer"], 70, height-61, width-140, 35),
        ):
            cell = ET.SubElement(layer, "mxCell", id=ident, value=value,
                                 style="text;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;"
                                       f"fontColor={INK if ident == 'title' else '#52677D'};"
                                       f"fontSize={34 if ident == 'title' else 18};"
                                       f"fontStyle={1 if ident == 'title' else 0};",
                                 vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w),
                          height=str(h), **{"as": "geometry"})
    ET.ElementTree(root).write(OUT / "WF-01-user-workflows-and-risk-controls.drawio",
                               encoding="utf-8", xml_declaration=True)


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def center_text(draw, box, label, size=21, bold=False):
    x1, y1, x2, y2 = box
    lines = label.split("\n")
    f = font(size, bold)
    line_height = size + 7
    top = y1 + ((y2-y1) - len(lines)*line_height)/2
    for line in lines:
        bounds = draw.textbbox((0, 0), line, font=f)
        draw.text((x1 + ((x2-x1)-(bounds[2]-bounds[0]))/2, top),
                  line, font=f, fill=INK)
        top += line_height


def preview(page):
    width, height = page.get("width", WIDTH), page["height"]
    image = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    draw.text((60, 39), "act  " + page["title"], fill=INK, font=font(35, True))
    for index, (name, left, right) in enumerate(page["lanes"]):
        draw.rectangle((left, 140, right, height-120),
                       fill="#F9FBFE" if index % 2 == 0 else "#F4F8FC",
                       outline="#C8D6E3", width=2)
        draw.rectangle((left, 140, right, 212), fill="#E4EDF5", outline="#C8D6E3", width=2)
        center_text(draw, (left, 140, right, 212), name, 23, True)
    nodes = {n["id"]: n for n in page["nodes"]}
    for edge in page["edges"]:
        path = path_for(edge, nodes)
        draw.line(path, fill="#697E91", width=3)
        p, q = path[-2:]
        dx, dy = q[0]-p[0], q[1]-p[1]
        length = max(1, math.hypot(dx, dy))
        ux, uy = dx/length, dy/length
        tip = (q[0]-ux*13, q[1]-uy*13)
        draw.polygon([q, (tip[0]-uy*7, tip[1]+ux*7),
                      (tip[0]+uy*7, tip[1]-ux*7)], fill="#697E91")
        if edge["label"]:
            longest = max(zip(path, path[1:]),
                          key=lambda s: abs(s[1][0]-s[0][0])+abs(s[1][1]-s[0][1]))
            a, b = longest
            cx, cy = (a[0]+b[0])/2, (a[1]+b[1])/2
            label = edge["label"]
            bounds = draw.textbbox((0, 0), label, font=font(18))
            tw, th = bounds[2]-bounds[0]+12, bounds[3]-bounds[1]+8
            box = (cx-tw/2, cy-th/2-12, cx+tw/2, cy+th/2-12)
            draw.rounded_rectangle(box, radius=4, fill="white", outline="#D7E1EB", width=1)
            draw.text((box[0]+6, box[1]+3), label, fill="#344A5F", font=font(18))
    for n in page["nodes"]:
        x,y,w,h = n["x"],n["y"],n["w"],n["h"]
        fill, stroke = COLOR.get(n["kind"], ("#172B40", "#172B40"))
        if n["kind"] == "start":
            draw.ellipse((x,y,x+w,y+h), fill="#172B40")
            continue
        if n["kind"] == "end":
            draw.ellipse((x,y,x+w,y+h), outline="#172B40", width=5)
            draw.ellipse((x+13,y+13,x+w-13,y+h-13), fill="#172B40")
            continue
        if n["kind"] == "decision":
            draw.polygon([(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)],
                         fill=fill, outline=stroke, width=3)
        elif n["kind"] == "note":
            draw.rectangle((x,y,x+w,y+h), fill=fill, outline=stroke, width=2)
        else:
            draw.rounded_rectangle((x,y,x+w,y+h), radius=17, fill=fill,
                                   outline=stroke, width=3)
        center_text(draw, (x+10,y+5,x+w-10,y+h-5), n["label"],
                    18 if n["kind"] == "note" else 21,
                    n["kind"] in ("decision", "success"))
    draw.text((70, height-104),
              "Blue = implemented   |   Amber = proposed control   |   Red = rejected request   |   Gray = user or external action",
              fill="#52677D", font=font(18))
    draw.text((70, height-63), page["footer"], fill="#52677D", font=font(18))
    image.save(OUT / f"{page['id']}.png", optimize=True)


if __name__ == "__main__":
    make_drawio()
    for item in PAGES:
        preview(item)
