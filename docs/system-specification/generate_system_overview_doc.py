"""Create a standalone Word overview of the implemented MSU canteen system."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).with_name("MSU Canteen System Overview.docx")
NAVY = RGBColor(31, 52, 73)
TEAL = RGBColor(14, 113, 117)
GRAY = RGBColor(86, 101, 117)
PALE = "EAF3F5"


def font(size=22, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / name
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def draw_architecture() -> BytesIO:
    image = Image.new("RGB", (1500, 455), "white")
    d = ImageDraw.Draw(image)
    ink = "#24354A"
    teal = "#0E7175"
    blue = "#DCEBFA"
    green = "#DFF1EC"
    gray = "#EDF1F5"

    def box(rect, label, fill, size=23):
        d.rounded_rectangle(rect, radius=14, fill=fill, outline=ink, width=3)
        cx = (rect[0] + rect[2]) / 2
        cy = (rect[1] + rect[3]) / 2
        lines = label.split("\n")
        line_height = size + 9
        for i, line in enumerate(lines):
            f = font(size, True)
            bounds = d.textbbox((0, 0), line, font=f)
            d.text((cx - (bounds[2] - bounds[0]) / 2,
                    cy - len(lines) * line_height / 2 + i * line_height),
                   line, fill=ink, font=f)

    def arrow(x1, y1, x2, y2):
        d.line((x1, y1, x2, y2), fill=teal, width=5)
        if x2 > x1:
            tip = [(x2, y2), (x2 - 17, y2 - 9), (x2 - 17, y2 + 9)]
        elif x2 < x1:
            tip = [(x2, y2), (x2 + 17, y2 - 9), (x2 + 17, y2 + 9)]
        else:
            tip = [(x2, y2), (x2 - 9, y2 - 17), (x2 + 9, y2 - 17)]
        d.polygon(tip, fill=teal)

    box((20, 160, 230, 280), "Users", gray, 25)
    box((315, 160, 560, 280), "Web browser", blue, 25)
    box((645, 160, 905, 280), "Flask application", green, 25)
    box((1075, 22, 1460, 112), "Database\n(SQLite default)", gray, 22)
    box((1075, 173, 1460, 263), "SMTP email service", gray, 22)
    box((1075, 324, 1460, 414), "RSA ticket key", gray, 22)
    box((275, 342, 610, 430), "Browser QR / scan libraries", gray, 20)
    arrow(230, 220, 315, 220)
    arrow(560, 220, 645, 220)
    arrow(905, 205, 1060, 75)
    arrow(905, 220, 1075, 220)
    arrow(905, 235, 1060, 369)
    arrow(440, 342, 440, 280)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def keep_row_together(row):
    tr_pr = row._tr.get_or_add_trPr()
    item = OxmlElement("w:cantSplit")
    tr_pr.append(item)


def table(document, headers, rows, widths=None):
    t = document.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.autofit = False
    if widths:
        for i, width in enumerate(widths):
            t.columns[i].width = Inches(width)
    for i, label in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = label
        set_cell_shading(cell, "DCE9EC")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        if widths:
            cell.width = Inches(widths[i])
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = NAVY
            run.font.size = Pt(9)
    repeat_header(t.rows[0])
    keep_row_together(t.rows[0])
    for index, values in enumerate(rows):
        row = t.add_row()
        keep_row_together(row)
        for i, value in enumerate(values):
            cell = row.cells[i]
            cell.text = value
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            if widths:
                cell.width = Inches(widths[i])
            if index % 2:
                set_cell_shading(cell, "F5F8F9")
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    run.font.size = Pt(8.8)
                    run.font.color.rgb = NAVY
    document.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def para(document, text, bold_prefix=None):
    p = document.add_paragraph()
    if bold_prefix and text.startswith(bold_prefix):
        p.add_run(bold_prefix).bold = True
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    return p


def bullet(document, text):
    return document.add_paragraph(text, style="List Bullet")


def step(document, number, text):
    p = document.add_paragraph(style="List Paragraph")
    p.add_run(f"{number}. ").bold = True
    p.add_run(text)
    return p


def heading(document, text, level=1):
    return document.add_heading(text, level=level)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.add_run("Page ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def build():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(18)
    section.bottom_margin = Mm(17)
    section.left_margin = Mm(18)
    section.right_margin = Mm(18)

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9.5)
    normal.font.color.rgb = NAVY
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.08
    for level, size in [(1, 15), (2, 11.5), (3, 10.5)]:
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = TEAL if level == 1 else NAVY
        style.paragraph_format.space_before = Pt(12 if level == 1 else 8)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.text = "MSU CANTEEN  |  SYSTEM OVERVIEW"
    header.style = doc.styles["Caption"]
    header.runs[0].font.color.rgb = GRAY
    add_page_number(section.footer.paragraphs[0])

    doc.core_properties.title = "MSU Canteen System Overview"
    doc.core_properties.subject = "Current implementation, workflows, data and limitations"
    doc.core_properties.author = "MSU Canteen System Documentation"

    title = doc.add_paragraph()
    title.style = doc.styles["Title"]
    title.add_run("MSU Canteen System\nOverview")
    title.runs[0].font.color.rgb = NAVY
    subtitle = doc.add_paragraph("Current implementation  |  5 November 2026")
    subtitle.style = doc.styles["Subtitle"]
    subtitle.runs[0].font.color.rgb = TEAL

    heading(doc, "Executive summary")
    para(doc, "The MSU Canteen System is a Flask web application for browsing meals, "
         "placing student orders, issuing signed meal tickets and recording collection "
         "at a staffed counter. Managers maintain the menu, orders and alerts; administrators "
         "see basic operating counts. The intended result is a traceable purchase and "
         "collection process with role-based access and protection against forged or reused QR tickets.")
    para(doc, "Core flow: student selects meals → completes demo checkout → receives a signed ticket "
         "→ counter staff verify the ticket → collection is recorded.")
    para(doc, "The current checkout is a simulation. It records a local payment timestamp, "
         "but no payment provider confirms or charges real funds.")

    heading(doc, "1. Purpose and system boundary")
    para(doc, "This document describes the behavior present in the repository, not a deployed "
         "production service. The application is a server-rendered web system usable through a "
         "desktop or phone browser. It contains a single Flask application, a relational database, "
         "an SMTP email connection and an RSA signing key. Browser-loaded libraries generate "
         "and scan QR codes and render a ticket barcode.")
    para(doc, "The system supports four account roles—student, counter staff, manager and "
         "administrator—plus visitors who have not signed in. All account roles share the "
         "students table; their role field controls access.")

    heading(doc, "2. Users and permissions")
    table(doc, ["Actor", "Implemented activities"], [
        ("Visitor", "Browse/search available meals; filter by category; view meal details; "
         "add, update, remove or clear cart items; register as a student; open a login page."),
        ("Student", "Verify registration by email code; log in; browse and manage the cart; "
         "complete demo checkout; view own orders, statuses and signed tickets; submit "
         "feedback after completion; log out."),
        ("Counter staff", "Log in with a staff access key; view all orders and details; scan "
         "a signed QR ticket or enter ticket code plus registration number; verify eligibility; "
         "approve collection; browse the menu; log out."),
        ("Manager", "Log in with a manager access key; view order counts and calculated sales; "
         "add/edit/delete menu items; search/filter orders; change statuses and eligible order "
         "items; extend eligible tickets; create/activate/deactivate/delete alerts; log out."),
        ("Administrator", "Log in with an administrator access key; view student, staff, order "
         "and menu-item counts; access the shared order list and menu; log out."),
    ], [1.15, 5.65])
    para(doc, "Staff, manager and administrator accounts are created on first successful "
         "role-key login. Public registration creates only student accounts. Menu and cart "
         "routes are available before login, while checkout requires an authenticated student.")

    heading(doc, "3. End-to-end workflows")
    heading(doc, "3.1 Registration and authentication", 2)
    step(doc, 1, "A student provides student ID, name, email and password, with optional department and phone.")
    step(doc, 2, "The application checks required values, matching passwords, strength, and unique student ID/email.")
    step(doc, 3, "It creates an unverified account and sends a six-digit email verification code.")
    step(doc, 4, "The correct code verifies the account and signs the student in.")
    step(doc, 5, "Later login accepts email or student ID plus password. A login at least seven days after the prior login requires another email code.")
    para(doc, "Email challenge data is held in the session during verification. Staff, managers "
         "and administrators use separate role-key login pages rather than the student password flow.")

    heading(doc, "3.2 Catalog and cart", 2)
    para(doc, "The public catalog lists available meals and supports name search, category "
         "filtering and individual meal detail pages. A meal may have a description, price, "
         "image URL, preparation time and dietary flags. The browser session holds the cart. "
         "Users can change quantities, remove meals and clear the cart; the supported quantity "
         "range is 1–10 per meal. The cart is checked again at checkout because availability "
         "or prices may have changed.")

    heading(doc, "3.3 Ordering and demo checkout", 2)
    step(doc, 1, "The student opens checkout with a nonempty cart. The application validates meal existence, availability and quantities, then calculates the total from current prices.")
    step(doc, 2, "The student selects EcoCash, Gold Card or Bank Account and enters a demo account or phone identifier. The identifier is length-checked but is not stored.")
    step(doc, 3, "When the total exceeds $100, the student confirms an email code before the order is created.")
    step(doc, 4, "The application creates an Order and OrderItem records, captures unit prices and subtotals, records the method and local paid_at timestamp, generates an order number and ticket code, and clears the cart.")
    para(doc, "A new order has pending status. The local paid_at timestamp records successful "
         "demo checkout and is not evidence that real money was received.")

    heading(doc, "3.4 Ticket issue, verification and collection", 2)
    para(doc, "The order confirmation page presents the order and, for a student with a paid_at "
         "marker, a signed QR ticket, ticket code and barcode. The student can download a PNG "
         "ticket. The QR payload contains order ID, ticket code, registration number and expiry; "
         "tickets.py signs it using RSA-PSS/SHA-256. The signed payload is generated on demand "
         "from order data. There is no Ticket table.")
    para(doc, "A ticket normally expires at midnight in Zimbabwe time after the order date. "
         "An eligible order can receive a one-day extension. Staff may scan the QR code or "
         "enter the ticket code and registration number manually. Verification checks the "
         "server record, local payment marker, expiry, cancellation and previous collection. "
         "Approval records the collecting staff account and time and sets status to completed. "
         "A conditional update prevents a second successful collection of the same order.")
    para(doc, "The current verification rule does not require ready status: an otherwise "
         "valid pending, confirmed or preparing order may be collected.")

    heading(doc, "3.5 Management and feedback", 2)
    para(doc, "Managers search by order number, filter by status, change order statuses, edit "
         "meals or quantities on eligible orders and recalculate totals. Editing is blocked "
         "for collected, completed or cancelled orders. Managers may extend an eligible ticket "
         "once. They also create, edit and delete menu items, including prices, availability, "
         "category assignment, images and dietary fields. Managers can create, activate, "
         "deactivate and delete alerts of type info, warning or urgent.")
    para(doc, "Students may submit a rating and comment after an order reaches completed. "
         "The route checks that the order belongs to the student and has no existing feedback.")

    heading(doc, "4. Order states and business rules")
    table(doc, ["State", "Meaning in the current application"], [
        ("pending", "Initial state when a student creates an order."),
        ("confirmed", "A manager may mark an order confirmed."),
        ("preparing", "A manager may mark an order as being prepared."),
        ("ready", "A manager may mark an order ready for collection."),
        ("completed", "Staff approval sets this state; a manager can also select it. Feedback is then available."),
        ("cancelled", "A manager can cancel an order; its ticket cannot be collected."),
    ], [1.2, 5.6])
    para(doc, "A manager can move an uncollected order between supported states, including "
         "reopening a completed order. Once collected_at is set, the order cannot be reopened. "
         "Ticket eligibility also requires an unexpired, uncollected, non-cancelled order with "
         "a local paid_at marker.")

    heading(doc, "5. Data model")
    table(doc, ["Entity", "Data and purpose", "Relationships"], [
        ("Student", "Account identity, unique student ID/email, password hash, role, "
         "verification and login dates.", "Places orders; may collect orders as staff; may create alerts as manager."),
        ("Category", "Meal grouping, name, description, icon, display order and active flag.",
         "Has many MenuItems."),
        ("MenuItem", "Meal name, description, price, category, availability, image URL, "
         "preparation time and dietary flags.", "Belongs to Category; appears in OrderItems."),
        ("Order", "Order number, student, status, total, demo payment fields, ticket code, "
         "extension days, creation/update and collection details.", "Belongs to Student; has OrderItems and optional Feedback; may reference collecting staff."),
        ("OrderItem", "One ordered meal and quantity with captured unit price and subtotal.",
         "Joins Order to MenuItem."),
        ("Feedback", "Rating, comment and submission date.", "References an Order."),
        ("Alert", "Manager-authored title, message, type, active flag and dates.",
         "References its creator in Student."),
    ], [0.9, 3.4, 2.5])
    para(doc, "The cart and email code are session data. Ticket data is part of Order and its "
         "signed QR payload. There is no Payment, Inventory or Ticket table. The application "
         "intends one feedback entry per order, although feedback.order_id is not unique in the database.")

    heading(doc, "6. Technical architecture")
    picture = doc.add_paragraph()
    picture.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture.add_run().add_picture(draw_architecture(), width=Inches(6.7))
    caption = doc.add_paragraph("Figure 1. Current application and external connections")
    caption.style = doc.styles["Caption"]
    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table(doc, ["Component", "Current responsibility"], [
        ("Browser", "Displays Jinja pages, manages the session cookie, and runs QR generation, barcode and camera scanning libraries loaded from CDNs."),
        ("Flask application", "Runs routes, role checks, validation, business logic, HTML rendering and two public JSON endpoints."),
        ("Database", "SQLite by default; DATABASE_URL can supply another SQLAlchemy URI. Holds the seven model tables."),
        ("SMTP service", "Delivers registration, stale-login and high-value-order codes when configured."),
        ("RSA key", "Signs tickets and verifies scanned QR payload signatures; configured for production or generated locally in development."),
    ], [1.45, 5.35])
    para(doc, "The public JSON endpoints are /api/menu, which lists available menu items, "
         "and /api/categories, which lists active categories. Startup creates missing tables, "
         "attempts to add missing columns, assigns ticket codes to older orders and seeds or "
         "refreshes menu data. The local runner starts the Flask development server on port 5000.")

    heading(doc, "7. Controls and current limits")
    table(doc, ["Area", "Current state and implication"], [
        ("Payment", "Demo checkout only. paid_at is a local marker; there is no provider charge, callback or reconciliation."),
        ("Ticket protection", "Signed QR payloads are checked against the server record. Manual entry uses ticket code plus registration number. A ticket may be collected once."),
        ("Authentication", "Student passwords are hashed and email codes are used for registration, older login and high-value orders. Staff roles use shared access keys and first-login account creation."),
        ("Email challenge", "The six-digit challenge is stored in the session; the code has no explicit expiry or attempt limit in the reviewed routes."),
        ("Form protection", "Checkout, collection and some manager order actions check session tokens. Other state-changing forms lack a consistent application-wide CSRF mechanism."),
        ("Configuration", "Production mode requires a configured Flask secret and ticket signing key. Configuration also contains fallback secrets and mail credentials that should be removed before real deployment."),
        ("Operations", "No stock reservation, refund flow, dedicated audit log, category management screen or student-facing alert delivery is implemented."),
        ("Reporting", "Manager sales is a sum of stored order totals, including orders regardless of status; it is not a reconciled financial report."),
        ("Data integrity", "Monetary values use floating-point columns. The feedback one-per-order rule is enforced in the route rather than by a unique database constraint."),
        ("Database changes", "The app uses create_all() and startup column additions instead of versioned migrations."),
    ], [1.35, 5.45])

    heading(doc, "8. Repository basis")
    para(doc, "This overview was prepared from the current repository implementation:")
    for path in ["app.py — routes, workflows, role checks and startup behavior",
                 "models.py — database entities and relationships",
                 "tickets.py — ticket expiry, signing and verification",
                 "config.py — database, email, role-key and signing configuration",
                 "requirements.txt — Python dependencies",
                 "templates/ — rendered pages and browser-side ticket, checkout and scanning behavior"]:
        bullet(doc, path)
    para(doc, "The document describes repository behavior; it does not certify the security "
         "of a deployment or confirm operation of external services.")

    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
