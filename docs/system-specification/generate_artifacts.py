"""Rebuild editable draw.io diagrams, PNG previews, and the Word specification."""
from __future__ import annotations

import heapq
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor

OUT = Path(__file__).resolve().parent
W, H = 1600, 900
COLORS = {
    "actor": (238, 242, 247), "process": (221, 237, 253),
    "store": (234, 228, 250), "external": (238, 242, 247),
    "demo": (255, 236, 201), "key": (222, 245, 230),
    "muted": (249, 250, 252),
}
STROKES = {
    "actor": "#718096", "process": "#2774B8", "store": "#8064A2",
    "external": "#718096", "demo": "#C98212", "key": "#38835A", "muted": "#AAB3C0",
}
FONT_FILE = Path("C:/Windows/Fonts/segoeui.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/segoeuib.ttf")


def N(id, label, x, y, w=200, h=86, kind="process"):
    return dict(id=id, label=label, x=x, y=y, w=w, h=h, kind=kind)


def E(src, dst, label=""):
    return (src, dst, label)


DIAGRAMS = [
    dict(file="SAD-01-high-level", title="SAD-01  |  Current high level architecture",
         note="One Flask process; payment is simulated inside checkout.", nodes=[
        N("student", "Student\nBrowser / phone", 70, 105, 270, 90, "actor"),
        N("staff", "Cashier\nBrowser + camera", 450, 105, 270, 90, "actor"),
        N("manager", "Manager\nWeb browser", 830, 105, 270, 90, "actor"),
        N("admin", "Administrator\nWeb browser", 1210, 105, 270, 90, "actor"),
        N("web", "Flask web application\nJinja pages + limited JSON", 550, 250, 500, 90),
        N("identity", "Identity & sessions\nroles, email codes", 90, 410, 300, 100),
        N("catalog", "Catalog & management\nmenu, alerts, dashboards", 465, 410, 300, 100),
        N("orders", "Ordering & demo payment\ncart, checkout, orders", 840, 410, 300, 100, "demo"),
        N("tickets", "Ticket & collection\nRSA QR, staff approval", 1215, 410, 300, 100),
        N("db", "SQL database\nSQLite default; 7 tables", 450, 660, 310, 105, "store"),
        N("session", "Signed browser session\ncart, login, 2FA, CSRF", 85, 660, 310, 105, "store"),
        N("smtp", "SMTP relay\nverification email", 835, 660, 300, 105, "external"),
        N("rsa", "RSA private key\nenvironment / instance file", 1200, 660, 315, 105, "key"),
    ], edges=[
        E("student","web","HTML / JSON"), E("staff","web","scan / approval"),
        E("manager","web","manage"), E("admin","web","counts"),
        E("web","identity"), E("web","catalog"), E("web","orders"), E("web","tickets"),
        E("identity","session","session state"), E("identity","db","users"),
        E("identity","smtp","email codes"), E("catalog","db","menu / alerts"),
        E("orders","session","cart"), E("orders","db","orders / items"),
        E("tickets","db","validate / collect"), E("tickets","rsa","sign / verify"),
    ]),
    dict(file="SAD-02-detailed", title="SAD-02  |  Logical modules and interactions",
         note="All blue modules run in app.py except RSA operations in tickets.py; models.py maps SQL tables.", nodes=[
        N("clients", "Student / staff / manager / admin\nHTML forms, JSON, QR camera", 45, 115, 360, 100, "actor"),
        N("routes", "Flask routes + Jinja templates\nrole checks / response rendering", 475, 115, 435, 100),
        N("cdn", "Browser CDN libraries\nQR, scanner, Bootstrap", 1080, 115, 390, 100, "external"),
        N("identity", "Identity\nregister, login, 2FA", 65, 310, 245, 95),
        N("catalog", "Catalog\nmenu, availability", 355, 310, 245, 95),
        N("cart", "Cart\nitem quantities", 645, 310, 245, 95),
        N("checkout", "Checkout\ndemo payment + order", 935, 310, 245, 95, "demo"),
        N("ticket", "Ticket service\nsign, expiry, verify", 1225, 310, 245, 95),
        N("manager", "Manager operations\nmeals, orders, alerts", 65, 525, 245, 95),
        N("reports", "Dashboards\ncounts, summed totals", 355, 525, 245, 95),
        N("feedback", "Feedback\ncompleted order rating", 645, 525, 245, 95),
        N("serve", "Counter service\nverify + collect once", 935, 525, 245, 95),
        N("smtp", "SMTP relay\nemail codes", 1225, 525, 245, 95, "external"),
        N("session", "S1  Browser signed session\ncart / login / challenges", 65, 725, 330, 90, "store"),
        N("sql", "SQLAlchemy SQL database\nusers, menu, orders, feedback, alerts", 495, 725, 610, 90, "store"),
        N("key", "RSA signing key\nconfigured / local file", 1205, 725, 305, 90, "key"),
    ], edges=[
        E("clients","routes","requests"), E("cdn","clients","browser scripts"),
        E("routes","identity"), E("routes","catalog"), E("routes","cart"),
        E("routes","checkout"), E("routes","manager"), E("routes","serve"),
        E("identity","session","challenge"), E("identity","sql","users"),
        E("identity","smtp","code"), E("catalog","sql","menu"),
        E("catalog","cart","selection"), E("cart","session","cart"),
        E("cart","checkout","lines"), E("checkout","sql","order + paid_at"),
        E("checkout","ticket","eligible order"), E("ticket","key","RSA"),
        E("ticket","sql","order match"), E("ticket","serve","payload"),
        E("serve","sql","collected_at"), E("manager","sql","updates"),
        E("manager","catalog","meal edits"), E("reports","sql","aggregate"),
        E("feedback","sql","rating"),
    ]),
    dict(file="DFD-00-context", title="DFD-00  |  Level 0 context",
         note="External payment gateway absent; checkout records demo payment internally.", nodes=[
        N("student", "Student", 80, 225, 240, 100, "actor"),
        N("staff", "Cashier", 80, 565, 240, 100, "actor"),
        N("system", "0  MSU Canteen System\naccounts, orders, tickets, collection", 575, 315, 450, 250),
        N("manager", "Manager", 1280, 170, 240, 100, "actor"),
        N("admin", "Administrator", 1280, 405, 240, 100, "actor"),
        N("smtp", "SMTP relay", 1280, 645, 240, 100, "external"),
    ], edges=[
        E("student","system","account / cart / demo choice"),
        E("system","student","menu / order / signed ticket"),
        E("staff","system","scan / approval"), E("system","staff","ticket result / order items"),
        E("manager","system","menu / order / alert changes"),
        E("system","manager","orders / totals / alerts"),
        E("admin","system","dashboard request"), E("system","admin","counts"),
        E("system","smtp","verification email"),
    ]),
    dict(file="DFD-01-level-1", title="DFD-01  |  Level 1 major processes",
         note="D1–D5 are tables in one SQL database; S1 is the signed browser session.", nodes=[
        N("student", "Student", 35, 135, 170, 75, "actor"),
        N("staff", "Cashier", 35, 285, 170, 75, "actor"),
        N("manager", "Manager", 35, 435, 170, 75, "actor"),
        N("admin", "Administrator", 35, 585, 170, 75, "actor"),
        N("smtp", "SMTP relay", 35, 735, 170, 75, "external"),
        N("p1", "1.0 Identity\nregistration / login / 2FA", 330, 120, 320, 100),
        N("p2", "2.0 Catalog\nbrowse / edit meals", 330, 270, 320, 100),
        N("p3", "3.0 Order & fulfilment\ndemo pay / ticket / collect", 330, 420, 320, 115, "demo"),
        N("p4", "4.0 Management\norders / alerts", 330, 585, 320, 100),
        N("p5", "5.0 Insights & feedback\ndashboards / ratings", 330, 735, 320, 100),
        N("s1", "S1  Browser session", 880, 70, 260, 75, "store"),
        N("d1", "D1  Students / roles", 880, 205, 260, 75, "store"),
        N("d2", "D2  Categories / meals", 880, 340, 260, 75, "store"),
        N("d3", "D3  Orders / items", 880, 475, 260, 75, "store"),
        N("d4", "D4  Alerts", 880, 610, 260, 75, "store"),
        N("d5", "D5  Feedback", 880, 745, 260, 75, "store"),
    ], edges=[
        E("student","p1","credentials"), E("p1","student","login result"),
        E("p1","smtp","code email"), E("p1","s1","challenge"),
        E("p1","d1","account update"), E("d1","p1","account lookup"),
        E("student","p2","browse"), E("manager","p2","meal edits"),
        E("p2","d2","meal update"), E("d2","p2","available menu"), E("p2","student","menu"),
        E("student","p3","cart / checkout"), E("staff","p3","scan / approval"),
        E("p3","student","order / ticket"), E("p3","staff","verify result"),
        E("s1","p3","cart"), E("d2","p3","prices"),
        E("p3","d3","orders / collection"), E("d3","p3","ticket / status"),
        E("manager","p4","status / alerts"), E("p4","d3","order edits"),
        E("p4","d4","alert edits"), E("admin","p5","counts request"),
        E("student","p5","feedback"), E("d1","p5","user counts"),
        E("d2","p5","menu count"), E("d3","p5","order data"),
        E("p5","d5","ratings"), E("p5","admin","counts"),
    ]),
    dict(file="DFD-02-level-2", title="DFD-02  |  Level 2 decomposition of 3.0",
         note="The payment selection is demo input; no provider settlement or callback occurs.", nodes=[
        N("student", "Student", 40, 165, 180, 80, "actor"),
        N("staff", "Cashier", 40, 625, 180, 80, "actor"),
        N("p31", "3.1 Maintain cart\nquantities / selection", 345, 135, 300, 100),
        N("p32", "3.2 Checkout\nvalidate / demo paid_at", 345, 285, 300, 105, "demo"),
        N("p33", "3.3 Issue ticket\nRSA sign / expiry", 345, 450, 300, 100),
        N("p34", "3.4 Verify & collect\nscan / manual / approve", 345, 610, 300, 100),
        N("p35", "3.5 Order status\nstudent order lookup", 345, 755, 300, 100),
        N("s1", "S1  Browser cart / challenge", 920, 95, 330, 80, "store"),
        N("d2", "D2  Menu and prices", 920, 230, 330, 80, "store"),
        N("d3", "D3  Orders and items", 920, 365, 330, 80, "store"),
        N("k", "K1  RSA signing key", 920, 500, 330, 80, "key"),
    ], edges=[
        E("student","p31","item / quantity"), E("p31","s1","cart state"),
        E("d2","p31","availability"), E("p31","p32","cart"),
        E("student","p32","demo method / reference"), E("p32","s1","2FA if >100"),
        E("d2","p32","current prices"), E("p32","d3","order + paid_at"),
        E("p32","p33","eligible order"), E("k","p33","signing key"),
        E("d3","p33","ticket code / expiry"), E("p33","student","signed QR"),
        E("staff","p34","scan / code / approve"), E("k","p34","verification key"),
        E("d3","p34","order state"), E("p34","d3","collected_at"), E("p34","staff","result / items"),
        E("student","p35","status request"), E("d3","p35","order status"),
        E("p35","student","status"),
    ]),
    dict(file="DFD-03-level-3", title="DFD-03  |  Level 3 decomposition of 3.4",
         note="Verify and approve are distinct requests; approve checks state again before conditional update.", nodes=[
        N("staff", "Cashier\nscan or manual entry", 55, 350, 260, 110, "actor"),
        N("p341", "3.4.1 Receive code\nmode + registration", 430, 100, 325, 95),
        N("p342", "3.4.2 Resolve ticket\nQR signature or manual lookup", 430, 250, 325, 105),
        N("p343", "3.4.3 Check eligibility\norder match / paid / expiry / reuse", 430, 415, 325, 110),
        N("p344", "3.4.4 Approve collection\nconditional update once", 430, 590, 325, 105),
        N("p345", "3.4.5 Return result\nitems / error / success", 430, 745, 325, 95),
        N("key", "K1  RSA public key\nfrom configured private key", 1035, 170, 350, 95, "key"),
        N("d3", "D3  Orders + items\nticket code / paid_at / status / collection", 1035, 405, 350, 120, "store"),
        N("s1", "S1  Staff signed session\nlogin + serve CSRF", 1035, 665, 350, 95, "store"),
    ], edges=[
        E("staff","p341","scan / manual code"), E("s1","p341","role + CSRF"),
        E("p341","p342","code / registration"), E("key","p342","QR verify"),
        E("d3","p342","lookup / payload match"), E("p342","p343","resolved order"),
        E("d3","p343","paid / expiry / reuse"), E("p343","p345","error or item list"),
        E("staff","p344","approval with code + reg"),
        E("s1","p344","role + CSRF"), E("d3","p344","recheck state"),
        E("p344","d3","conditional collected_at"),
        E("p344","p345","write result"), E("p345","staff","JSON result"),
    ]),
]


def spaced_dfd(d):
    """Repeat external entities and stores beside each process to avoid crossing rows.

    Gane-Sarson DFDs permit repeated symbols for the same entity/store. IDs and
    flow endpoints remain the same semantically; only their visual copies differ.
    """
    if d["file"] not in {"DFD-01-level-1", "DFD-02-level-2", "DFD-03-level-3"}:
        return d
    original = {n["id"]: n for n in d["nodes"]}
    processes = [n for n in d["nodes"] if n["id"].startswith("p")]
    by_process = {p["id"]: {"actors": [], "stores": []} for p in processes}
    for src, dst, _ in d["edges"]:
        for process_id, other_id in ((src, dst), (dst, src)):
            if process_id not in by_process or other_id in by_process:
                continue
            category = "actors" if original[other_id]["kind"] in ("actor", "external") else "stores"
            if other_id not in by_process[process_id][category]:
                by_process[process_id][category].append(other_id)
    nodes = []
    for row, p in enumerate(processes):
        base = 125 + row * 535
        nodes.append(N(p["id"], p["label"], 930, base+180, 415, 145, p["kind"]))
        actors = by_process[p["id"]]["actors"]
        stores = by_process[p["id"]]["stores"]
        for rank, actor_id in enumerate(actors):
            actor = original[actor_id]
            y = base + (65 if len(actors) == 1 else 55 + rank*245)
            nodes.append(N(f"{actor_id}_{p['id']}", actor["label"], 100, y, 290, 105, actor["kind"]))
        for rank, store_id in enumerate(stores):
            store = original[store_id]
            y = base + 25 + rank * (425 // max(1, len(stores)))
            nodes.append(N(f"{store_id}_{p['id']}", store["label"], 1830, y, 410, 100, store["kind"]))
    edges = []
    for src, dst, label in d["edges"]:
        if src in by_process and dst not in by_process:
            dst = f"{dst}_{src}"
        elif dst in by_process and src not in by_process:
            src = f"{src}_{dst}"
        edges.append(E(src, dst, label))
    return {**d, "nodes": nodes, "edges": edges, "size": (2340, 2920),
            "note": d["note"] + " Repeated actor and store symbols refer to the same named entity or store."}


def canvas_size(d):
    return d.get("size", (W, H))


def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_FILE
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def side_toward(a, b):
    ax, ay = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    bx, by = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    dx, dy = bx - ax, by - ay
    if abs(dx) >= abs(dy) * .75:
        return "right" if dx > 0 else "left"
    return "bottom" if dy > 0 else "top"


def opposite(side):
    return {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}[side]


def port(n, side, fraction):
    if side == "left":
        return (n["x"], n["y"] + n["h"] * fraction)
    if side == "right":
        return (n["x"] + n["w"], n["y"] + n["h"] * fraction)
    if side == "top":
        return (n["x"] + n["w"] * fraction, n["y"])
    return (n["x"] + n["w"] * fraction, n["y"] + n["h"])


def outside(p, side, distance=15):
    delta = {"left": (-distance, 0), "right": (distance, 0),
             "top": (0, -distance), "bottom": (0, distance)}[side]
    return (p[0] + delta[0], p[1] + delta[1])


def intersects_box(p, q, box, pad=5):
    x1, y1, x2, y2 = box
    if p[0] == q[0]:
        return x1-pad < p[0] < x2+pad and max(p[1], q[1]) > y1-pad and min(p[1], q[1]) < y2+pad
    return y1-pad < p[1] < y2+pad and max(p[0], q[0]) > x1-pad and min(p[0], q[0]) < x2+pad


def route(d):
    """Route all edges on a Manhattan grid, clear of every node."""
    width, height = canvas_size(d)
    nodes = {n["id"]: n for n in d["nodes"]}
    boxes = [(n["x"], n["y"], n["x"]+n["w"], n["y"]+n["h"]) for n in d["nodes"]]
    assignments = []
    sides = {}
    for i, (src, dst, _) in enumerate(d["edges"]):
        s = side_toward(nodes[src], nodes[dst])
        t = opposite(s)
        assignments.append((s, t))
        sides.setdefault((src, s), []).append((i, dst))
        sides.setdefault((dst, t), []).append((i, src))
    fractions = {}
    for (node, side), entries in sides.items():
        other_axis = 1 if side in ("left", "right") else 0
        entries.sort(key=lambda item: (nodes[item[1]]["y" if other_axis else "x"] +
                                       nodes[item[1]]["h" if other_axis else "w"] / 2, item[0]))
        for rank, (i, _) in enumerate(entries, 1):
            fractions[i, node] = rank / (len(entries) + 1)
    ports = []
    for i, (src, dst, _) in enumerate(d["edges"]):
        s, t = assignments[i]
        a = port(nodes[src], s, fractions[i, src])
        b = port(nodes[dst], t, fractions[i, dst])
        ports.append((a, outside(a, s), outside(b, t), b))
    grid_step = 25 if "size" in d else 20
    xs = {float(x) for x in range(20, width-19, grid_step)}
    ys = {float(y) for y in range(95, height-44, grid_step)}
    for x1, y1, x2, y2 in boxes:
        xs.update((x1-15, x2+15))
        ys.update((y1-15, y2+15))
    for a, aout, bout, b in ports:
        xs.update((a[0], aout[0], bout[0], b[0]))
        ys.update((a[1], aout[1], bout[1], b[1]))
    xs = sorted(x for x in xs if 10 <= x <= width-10)
    ys = sorted(y for y in ys if 90 <= y <= height-35)
    xi, yi = {x: i for i, x in enumerate(xs)}, {y: i for i, y in enumerate(ys)}
    used = []
    paths = []
    for a, aout, bout, b in ports:
        start, goal = (xi[aout[0]], yi[aout[1]]), (xi[bout[0]], yi[bout[1]])
        queue = [(0, 0, start[0], start[1], 0)]
        best = {(start[0], start[1], 0): 0}
        previous = {}
        final = None
        while queue:
            _, cost, ix, iy, direction = heapq.heappop(queue)
            state = (ix, iy, direction)
            if cost != best.get(state):
                continue
            if (ix, iy) == goal:
                final = state
                break
            for nx, ny, ndir in ((ix-1, iy, 1), (ix+1, iy, 1), (ix, iy-1, 2), (ix, iy+1, 2)):
                if nx < 0 or nx >= len(xs) or ny < 0 or ny >= len(ys):
                    continue
                p, q = (xs[ix], ys[iy]), (xs[nx], ys[ny])
                if any(intersects_box(p, q, box) for box in boxes):
                    continue
                extra = abs(q[0]-p[0]) + abs(q[1]-p[1])
                if direction and direction != ndir:
                    extra += 22
                # Crossings are allowed when needed, but shared tracks are discouraged.
                for u, v in used:
                    if p[0] == q[0] == u[0] == v[0] and max(min(p[1],q[1]),min(u[1],v[1])) < min(max(p[1],q[1]),max(u[1],v[1])):
                        extra += 45
                    elif p[1] == q[1] == u[1] == v[1] and max(min(p[0],q[0]),min(u[0],v[0])) < min(max(p[0],q[0]),max(u[0],v[0])):
                        extra += 45
                new = cost + extra
                nxt = (nx, ny, ndir)
                if new < best.get(nxt, float("inf")):
                    best[nxt] = new
                    previous[nxt] = state
                    heuristic = abs(xs[nx]-bout[0]) + abs(ys[ny]-bout[1])
                    heapq.heappush(queue, (new+heuristic, new, nx, ny, ndir))
        if final is None:
            raise RuntimeError(f"No orthogonal route in {d['file']} from {a} to {b}")
        cells = []
        while final in previous:
            cells.append((xs[final[0]], ys[final[1]]))
            final = previous[final]
        cells.append(aout)
        points = [a] + list(reversed(cells)) + [b]
        simplified = [points[0]]
        for p in points[1:]:
            if p == simplified[-1]:
                continue
            simplified.append(p)
            while len(simplified) >= 3:
                u, v, w = simplified[-3:]
                if (u[0] == v[0] == w[0]) or (u[1] == v[1] == w[1]):
                    simplified.pop(-2)
                else:
                    break
        assert all(u[0] == v[0] or u[1] == v[1] for u, v in zip(simplified, simplified[1:]))
        paths.append(simplified)
        used.extend(zip(simplified, simplified[1:]))
    return paths, assignments, fractions


def draw_png(d, paths):
    width, height = canvas_size(d)
    spacious = "size" in d
    img = Image.new("RGB", (width, height), "#FFFFFF")
    dr = ImageDraw.Draw(img)
    dr.text((55, 28), d["title"], fill="#15263B", font=font(34, True))
    dr.line((55, 82, width - 55, 82), fill="#B9CADC", width=2)
    for path in paths:
        dr.line(path, fill="#75899D", width=2, joint="curve")
        p, q = path[-2:]
        ux, uy = (int(q[0] > p[0]) - int(q[0] < p[0]),
                  int(q[1] > p[1]) - int(q[1] < p[1]))
        tip = q[0] - ux * 11, q[1] - uy * 11
        left = (tip[0] - uy * 6, tip[1] + ux * 6)
        right = (tip[0] + uy * 6, tip[1] - ux * 6)
        dr.polygon([q, left, right], fill="#60768B")
    for n in d["nodes"]:
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        kind = n["kind"]
        fill = COLORS[kind]
        stroke = STROKES[kind]
        if d["file"].startswith("DFD") and kind in ("store", "key"):
            # Gane-Sarson data store: three sides, open at the right.
            dr.rectangle((x, y, x+w, y+h), fill=fill)
            dr.line([(x+w, y), (x, y), (x, y+h), (x+w, y+h)], fill=stroke, width=3)
        elif kind in ("process", "demo"):
            dr.rounded_rectangle((x, y, x+w, y+h), radius=18, fill=fill, outline=stroke, width=3)
        else:
            dr.rectangle((x, y, x+w, y+h), fill=fill, outline=stroke, width=3)
        lines = n["label"].split("\n")
        sizes = [(27 if spacious else 22) if i == 0 else (21 if spacious else 17)
                 for i in range(len(lines))]
        line_h = [(33 if spacious else 27) if i == 0 else (27 if spacious else 22)
                  for i in range(len(lines))]
        top = y + (h - sum(line_h))/2
        for i, line in enumerate(lines):
            f = font(sizes[i], i == 0)
            box = dr.textbbox((0, 0), line, font=f)
            dr.text((x + (w - (box[2]-box[0]))/2, top), line, fill="#182B40", font=f)
            top += line_h[i]
    occupied = [(n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]) for n in d["nodes"]]
    label_font = font(20 if spacious else 13)
    for path, (src, dst, label) in zip(paths, d["edges"]):
        if not label:
            continue
        bounds = dr.textbbox((0, 0), label, font=label_font)
        tw, th = bounds[2] - bounds[0] + 12, bounds[3] - bounds[1] + 9
        best = None
        segments = sorted(zip(path, path[1:]),
                          key=lambda seg: -abs(seg[1][0]-seg[0][0])-abs(seg[1][1]-seg[0][1]))
        for p, q in segments:
            dx, dy = q[0] - p[0], q[1] - p[1]
            length = max(1, abs(dx) + abs(dy))
            nx, ny = -dy / length, dx / length
            for t in (.5, .3, .7):
              for offset in (15, -15, 32, -32, 50, -50):
                cx = p[0] + dx*t + nx*offset
                cy = p[1] + dy*t + ny*offset
                box = (cx-tw/2, cy-th/2, cx+tw/2, cy+th/2)
                penalty = 0
                if box[0] < 12 or box[2] > width-12 or box[1] < 87 or box[3] > height-38:
                    penalty += 100000
                for other in occupied:
                    ix = max(0, min(box[2], other[2]) - max(box[0], other[0]))
                    iy = max(0, min(box[3], other[3]) - max(box[1], other[1]))
                    penalty += ix*iy
                for other_path in paths:
                    for u, v in zip(other_path, other_path[1:]):
                        if u[0] == v[0] and box[0] < u[0] < box[2] and max(u[1],v[1]) > box[1] and min(u[1],v[1]) < box[3]:
                            penalty += 45
                        if u[1] == v[1] and box[1] < u[1] < box[3] and max(u[0],v[0]) > box[0] and min(u[0],v[0]) < box[2]:
                            penalty += 45
                penalty += abs(offset)*.1
                if best is None or penalty < best[0]:
                    best = (penalty, box)
        box = best[1]
        dr.rounded_rectangle(box, radius=5, fill="#FFFFFF", outline="#D9E1E9", width=1)
        dr.text((box[0]+6, box[1]+3), label, fill="#344A5F", font=label_font)
        occupied.append(box)
    dr.text((55, height - 35), d["note"], fill="#52677D", font=font(20 if "size" in d else 17))
    img.save(OUT / (d["file"] + ".png"), optimize=True)


def drawio(d, paths, assignments, fractions):
    width, height = canvas_size(d)
    root = ET.Element("mxfile", host="app.diagrams.net", modified="2026-10-30T00:00:00.000Z", agent="Codex", version="24.7.17", type="device")
    page = ET.SubElement(root, "diagram", id=d["file"], name=d["title"].split("|")[-1].strip())
    model = ET.SubElement(page, "mxGraphModel", dx=str(width), dy=str(height), grid="1", gridSize="10", guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(width), pageHeight=str(height), math="0", shadow="0")
    layer = ET.SubElement(model, "root")
    ET.SubElement(layer, "mxCell", id="0")
    ET.SubElement(layer, "mxCell", id="1", parent="0")
    for n in d["nodes"]:
        k = n["kind"]
        fill = "#%02X%02X%02X" % COLORS[k]
        if d["file"].startswith("DFD") and k in ("store", "key"):
            shape = "shape=partialRectangle;left=1;right=0;top=1;bottom=1;rounded=0"
        else:
            shape = "rounded=1;arcSize=14" if k in ("process", "demo") else "rounded=0"
        node_font_size = 25 if "size" in d else 18
        style = f"{shape};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={STROKES[k]};strokeWidth=2;fontColor=#182B40;fontSize={node_font_size};align=center;verticalAlign=middle;spacing=6;"
        parts = n["label"].split("\n")
        rich_label = "<b>" + parts[0] + "</b>" + ("<br>" + "<br>".join(parts[1:]) if len(parts) > 1 else "")
        cell = ET.SubElement(layer, "mxCell", id=n["id"], value=rich_label, style=style, vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry", x=str(n["x"]), y=str(n["y"]), width=str(n["w"]), height=str(n["h"]), **{"as": "geometry"})
    for i, (src, dst, label) in enumerate(d["edges"], 1):
        s, t = assignments[i-1]
        sf, tf = fractions[i-1, src], fractions[i-1, dst]
        coords = {"left": (0, sf), "right": (1, sf),
                  "top": (sf, 0), "bottom": (sf, 1)}
        ex, ey = coords[s]
        coords = {"left": (0, tf), "right": (1, tf),
                  "top": (tf, 0), "bottom": (tf, 1)}
        tx, ty = coords[t]
        style = (f"edgeStyle=segmentEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;"
                 f"exitX={ex:.16g};exitY={ey:.16g};exitPerimeter=0;"
                 f"entryX={tx:.16g};entryY={ty:.16g};entryPerimeter=0;"
                 f"strokeColor=#697E91;strokeWidth={2 if 'size' in d else 1.5};fontColor=#344A5F;fontSize={22 if 'size' in d else 13};labelBackgroundColor=#FFFFFF;")
        edge = ET.SubElement(layer, "mxCell", id=f"e{i}", value=label, style=style, edge="1", parent="1", source=src, target=dst)
        geometry = ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        points = ET.SubElement(geometry, "Array", **{"as": "points"})
        for x, y in paths[i-1][1:-1]:
            ET.SubElement(points, "mxPoint", x=str(x), y=str(y))
    if "size" in d:
        note = ET.SubElement(layer, "mxCell", id="layout-note", value=d["note"],
                             style="text;html=1;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize=19;fontColor=#52677D;",
                             vertex="1", parent="1")
        ET.SubElement(note, "mxGeometry", x="100", y=str(height-80),
                      width=str(width-200), height="45", **{"as": "geometry"})
    ET.ElementTree(root).write(OUT / (d["file"] + ".drawio"), encoding="utf-8", xml_declaration=True)


def add_inline(paragraph, text):
    for i, segment in enumerate(re.split(r"(\*\*[^*]+\*\*)", text)):
        if segment.startswith("**") and segment.endswith("**"):
            paragraph.add_run(segment[2:-2]).bold = True
        else:
            paragraph.add_run(segment.replace("`", ""))


def build_docx():
    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Inches(11.69), Inches(8.27)
    section.top_margin = Inches(.65)
    section.bottom_margin = Inches(.6)
    section.left_margin = Inches(.72)
    section.right_margin = Inches(.72)
    styles = doc.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(9.5)
    styles["Normal"].paragraph_format.space_after = Pt(5)
    for s, size in (("Title", 21), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
        styles[s].font.name = "Aptos Display"
        styles[s].font.size = Pt(size)
        styles[s].font.color.rgb = RGBColor(22, 60, 93)
    footer = section.footer.paragraphs[0]
    footer.text = "MSU Canteen System  |  Preliminary system specification  |  30 October 2026"
    footer.style = "Caption"
    lines = (OUT / "MSU-Canteen-System-Specification.md").read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if m:
                p = doc.add_paragraph()
                p.alignment = 1
                image_path = OUT / m.group(2)
                image_width = 8.9 if m.group(2) == "UC-01-user-interactions.png" else 10.1
                p.add_run().add_picture(str(image_path), width=Inches(image_width))
                cap = doc.add_paragraph(m.group(1), style="Caption")
                cap.alignment = 1
            i += 1
            continue
        if line.startswith("# "):
            doc.add_paragraph(line[2:], style="Title")
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=1)
        elif line.startswith("### "):
            if i + 2 < len(lines) and lines[i + 2].startswith("!["):
                doc.add_page_break()
            doc.add_heading(line[4:], level=2)
        elif line.startswith("| "):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append(cells)
                i += 1
            table = doc.add_table(rows=0, cols=len(rows[0]))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for ri, row in enumerate(rows):
                cells = table.add_row().cells
                for ci, value in enumerate(row):
                    cells[ci].text = value.replace("`", "").replace("**", "")
                    if ri == 0:
                        for run in cells[ci].paragraphs[0].runs:
                            run.bold = True
            doc.add_paragraph()
            continue
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, line[2:])
        else:
            p = doc.add_paragraph()
            add_inline(p, line)
        i += 1
    doc.save(OUT / "MSU-Canteen-System-Specification.docx")


if __name__ == "__main__":
    for diagram in DIAGRAMS:
        diagram = spaced_dfd(diagram)
        paths, assignments, fractions = route(diagram)
        drawio(diagram, paths, assignments, fractions)
        draw_png(diagram, paths)
    build_docx()
