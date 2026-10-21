from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import random
import secrets
import string

from config import config
from models import db, Student, Category, MenuItem, Order, OrderItem, Feedback, Alert
from tickets import load_private_key, issue_ticket, verify_ticket_payload, expiry_for

mail = Mail()

STALE_LOGIN_2FA_DAYS = 7
HIGH_VALUE_ORDER_LIMIT = 100
ORDER_STATUSES = ("pending", "confirmed", "preparing", "ready", "completed", "cancelled")
TICKET_TIMEZONE = ZoneInfo("Africa/Harare")
COMMON_WEAK_PASSWORDS = {
    "password",
    "password1",
    "123456",
    "12345678",
    "qwerty",
    "admin",
    "letmein",
    "welcome",
}


def create_app(config_name=None):
    """Create and configure the Flask application."""

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    if config_name == "production" and (not os.environ.get("SECRET_KEY") or os.environ.get("SECRET_KEY") == "msu-canteen-secret-key-2026"):
        raise RuntimeError("Configure a unique SECRET_KEY for production")
    app.ticket_private_key = load_private_key(app)

    db.init_app(app)
    mail.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            student = Student.query.get(int(user_id))
            # Allow verified students, or any staff/manager/admin users (they verify on creation)
            if student and (student.is_verified or student.role in ['manager', 'staff', 'admin']):
                return student
            return None
        except (ValueError, TypeError):
            return None

    register_routes(app)

    with app.app_context():
        db.create_all()
        sync_database_schema(app)
        for order in Order.query.filter_by(ticket_code=None).all():
            order.ticket_code = secrets.token_hex(8).upper()
        db.session.commit()
        seed_database()

    return app


def sync_database_schema(app):
    """Add model columns that are missing from existing database tables."""
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if "students" in existing_tables:
            columns = {col["name"] for col in inspector.get_columns("students")}
            if "is_verified" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE students ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
            if "last_login_at" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE students ADD COLUMN last_login_at DATETIME"))
            if "last_2fa_at" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE students ADD COLUMN last_2fa_at DATETIME"))

        if "orders" in existing_tables:
            columns = {col["name"] for col in inspector.get_columns("orders")}
            if "ticket_extension_days" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE orders ADD COLUMN ticket_extension_days INTEGER NOT NULL DEFAULT 0"))
            else:
                with db.engine.begin() as connection:
                    connection.execute(text("UPDATE orders SET ticket_extension_days = 0 WHERE ticket_extension_days IS NULL"))

        inspector = inspect(db.engine)
        for table in db.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in columns or column.primary_key:
                    continue
                add_column_to_table(table.name, column)
    except Exception as e:
        app.logger.warning(f"Could not sync database schema: {e}")


def add_column_to_table(table_name, column):
    """Add a missing model column to a SQLite table without making the DB read-only."""
    preparer = db.engine.dialect.identifier_preparer
    column_type = column.type.compile(dialect=db.engine.dialect)
    sql = (
        f"ALTER TABLE {preparer.quote(table_name)} "
        f"ADD COLUMN {preparer.quote(column.name)} {column_type}"
    )

    if column.server_default is not None:
        default_sql = str(column.server_default.arg)
        sql += f" DEFAULT {default_sql}"
        if not column.nullable:
            sql += " NOT NULL"

    with db.engine.begin() as connection:
        connection.execute(text(sql))


def evaluate_password_strength(password, student_id=None, name=None, email=None):
    """Return password strength and practical feedback for registration."""
    feedback = []
    score = 0
    normalized_password = (password or "").lower()

    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        feedback.append("use at least 8 characters")

    checks = [
        (any(char.islower() for char in password), "add lowercase letters"),
        (any(char.isupper() for char in password), "add uppercase letters"),
        (any(char.isdigit() for char in password), "add at least one number"),
        (any(not char.isalnum() for char in password), "add a special character"),
    ]

    for passed, message in checks:
        if passed:
            score += 1
        else:
            feedback.append(message)

    personal_values = [student_id, name, email.split("@")[0] if email and "@" in email else email]
    for value in personal_values:
        value = (value or "").strip().lower()
        if value and len(value) >= 3 and value in normalized_password:
            score -= 1
            feedback.append("avoid using your name, student ID, or email in the password")
            break

    if normalized_password in COMMON_WEAK_PASSWORDS:
        score = 0
        feedback.append("avoid common passwords")

    if score >= 6:
        strength = "Strong"
    elif score >= 4:
        strength = "Medium"
    else:
        strength = "Weak"

    return strength, sorted(set(feedback))


def register_routes(app):
    """Register all application routes."""

    def send_2fa_email(email, code, purpose="verify your account"):
        """Send 2FA verification code via email."""
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
            app.logger.warning("Email credentials are not configured; dropping 2FA email and printing code to console.")
            print(f"[2FA DEBUG] Send code to {email}: {code}")
            return True

        msg = Message(
            subject="Your MSU Canteen Account Verification Code",
            recipients=[email],
            body=f"Your verification code is: {code}\n\nPlease enter this code to {purpose}."
        )
        try:
            mail.send(msg)
            return True
        except Exception as exc:
            app.logger.error("Failed to send 2FA email: %s", exc)
            return False

    def start_2fa(student, purpose, message, **extra_session_data):
        """Start an email 2FA challenge for a specific purpose."""
        code = ''.join(random.choices(string.digits, k=6))
        session['2fa_code'] = code
        session['2fa_purpose'] = purpose
        session['pending_user_id'] = student.id
        for key, value in extra_session_data.items():
            session[key] = value

        if not send_2fa_email(student.email, code, message.lower()):
            session.pop('2fa_code', None)
            session.pop('2fa_purpose', None)
            session.pop('pending_user_id', None)
            for key in extra_session_data:
                session.pop(key, None)
            return False
        return True

    def is_stale_login(student):
        """Require 2FA when the previous login was at least a week ago."""
        if not student.last_login_at:
            return False
        return datetime.utcnow() - student.last_login_at >= timedelta(days=STALE_LOGIN_2FA_DAYS)

    def finish_login(student):
        student.last_login_at = datetime.utcnow()
        db.session.commit()
        login_user(student)

    def create_order_from_cart(student, payment_method=None):
        cart_data = session.get("cart", {})
        if not cart_data or any(
            not isinstance(quantity, int) or not 1 <= quantity <= 10 or
            not (item := db.session.get(MenuItem, int(item_id))) or not item.is_available
            for item_id, quantity in cart_data.items()
        ):
            raise ValueError("Cart changed or contains unavailable items")
        order_number = generate_order_number()
        total = 0

        order = Order(
            order_number=order_number,
            ticket_code=secrets.token_hex(8).upper(),
            payment_method=payment_method,
            paid_at=datetime.utcnow(),
            student_id=student.id,
            total_amount=0,
            notes=None
        )
        db.session.add(order)
        db.session.flush()

        for item_id, quantity in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.is_available and isinstance(quantity, int) and 1 <= quantity <= 10:
                subtotal = item.price * quantity
                total += subtotal
                db.session.add(OrderItem(
                    order_id=order.id,
                    menu_item_id=item.id,
                    quantity=quantity,
                    unit_price=item.price,
                    subtotal=subtotal
                ))

        order.total_amount = total
        db.session.commit()
        session.pop("cart", None)
        return order

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect_user_by_role(current_user)
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect_user_by_role(current_user)

        if request.method == "POST":
            student_id = request.form.get("student_id")
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")
            department = request.form.get("department")
            phone = request.form.get("phone")

            confirm_password = request.form.get("confirm_password")

            if not student_id or not name or not email or not password:
                flash("Please fill in all required fields.", "danger")
                return render_template("register.html")

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return render_template("register.html")

            strength, password_feedback = evaluate_password_strength(
                password,
                student_id=student_id,
                name=name,
                email=email
            )
            if strength == "Weak":
                flash(
                    "Password strength: Weak. Improve it by choosing a less predictable password: "
                    + "; ".join(password_feedback)
                    + ".",
                    "danger"
                )
                return render_template("register.html")
            if password_feedback:
                flash(
                    "Password strength: Medium. You can make it stronger if you "
                    + "; ".join(password_feedback)
                    + ".",
                    "warning"
                )

            existing_id = Student.query.filter_by(student_id=student_id).first()
            existing_email = Student.query.filter_by(email=email).first()

            if (existing_id is not None and existing_id == existing_email
                    and existing_id.role == "student" and not existing_id.is_verified
                    and check_password_hash(existing_id.password_hash, password)):
                if not start_2fa(existing_id, "registration", "complete your registration"):
                    flash("Unable to send verification email right now. Please try again later.", "danger")
                    return render_template("register.html")
                flash("Please check your email for the verification code.", "success")
                return redirect(url_for("verify_2fa"))

            if existing_id:
                flash("Student ID already registered.", "danger")
                return render_template("register.html")

            if existing_email:
                flash("Email already registered.", "danger")
                return render_template("register.html")

            student = Student(
                student_id=student_id,
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                department=department,
                phone=phone,
                role="student",
                is_verified=False
            )

            db.session.add(student)
            db.session.commit()

            if not start_2fa(
                student,
                "registration",
                "complete your registration"
            ):
                flash("Unable to send verification email right now. Please try again later.", "danger")
                return render_template("register.html")

            flash("Registration successful! Please check your email for the verification code.", "success")
            return redirect(url_for("verify_2fa"))

        return render_template("register.html")

    @app.route("/verify-2fa", methods=["GET", "POST"])
    def verify_2fa():
        purpose = session.get('2fa_purpose')

        if current_user.is_authenticated and purpose != "high_value_order":
            return redirect_user_by_role(current_user)

        if 'pending_user_id' not in session or '2fa_code' not in session:
            flash("No pending verification. Please register first.", "danger")
            return redirect(url_for("register"))

        if request.method == "POST":
            entered_code = request.form.get("code")
            if entered_code == session['2fa_code']:
                user_id = session['pending_user_id']
                student = Student.query.get(user_id)
                if student:
                    student.last_2fa_at = datetime.utcnow()

                    if purpose == "registration":
                        student.is_verified = True
                        finish_login(student)
                        success_message = "Verification successful! Welcome!"
                        redirect_response = redirect_user_by_role(student)
                    elif purpose == "stale_login":
                        finish_login(student)
                        success_message = "Verification successful. Welcome back!"
                        redirect_response = redirect_user_by_role(student)
                    elif purpose == "high_value_order":
                        if not current_user.is_authenticated or current_user.id != student.id:
                            flash("Please log in again before completing this order.", "danger")
                            return redirect(url_for("login"))
                        if session.get("cart") != session.get("pending_order_cart"):
                            flash("Cart changed during verification. Please check out again.", "danger")
                            session.pop("pending_order_cart", None)
                            return redirect(url_for("checkout"))
                        db.session.commit()
                        payment_method = session.get('pending_payment_method')
                        if payment_method not in ("ecocash", "gold_card", "bank_account"):
                            flash("Payment selection expired. Please return to checkout.", "danger")
                            return redirect(url_for("checkout"))
                        try:
                            order = create_order_from_cart(student, payment_method=payment_method)
                        except ValueError:
                            flash("Cart items changed. Please check out again.", "danger")
                            return redirect(url_for("checkout"))
                        success_message = f"Order placed successfully! Order number: {order.order_number}"
                        redirect_response = redirect(url_for("order_confirmation", order_id=order.id))
                    else:
                        flash("Unknown verification request. Please try again.", "danger")
                        return redirect(url_for("login"))

                    session.pop('2fa_code', None)
                    session.pop('pending_user_id', None)
                    session.pop('2fa_purpose', None)
                    session.pop('pending_payment_method', None)
                    session.pop('pending_order_cart', None)
                    flash(success_message, "success")
                    return redirect_response
                else:
                    flash("User not found.", "danger")
            else:
                flash("Invalid verification code.", "danger")

        return render_template("verify_2fa.html", purpose=purpose)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect_user_by_role(current_user)

        if request.method == "POST":
            email = request.form.get("email")
            student_id = request.form.get("student_id")
            password = request.form.get("password")

            if email:
                student = Student.query.filter_by(email=email, role="student").first()
            else:
                student = Student.query.filter_by(student_id=student_id, role="student").first()

            if student and check_password_hash(student.password_hash, password):
                if not student.is_verified:
                    if not start_2fa(
                        student,
                        "registration",
                        "verify your account"
                    ):
                        flash("Unable to send verification email right now. Please try again later.", "danger")
                        return render_template("login.html")
                    flash("Please verify your account first. Check your email for the code.", "warning")
                    return redirect(url_for("verify_2fa"))
                if is_stale_login(student):
                    if not start_2fa(
                        student,
                        "stale_login",
                        "confirm your login"
                    ):
                        flash("Unable to send verification email right now. Please try again later.", "danger")
                        return render_template("login.html")
                    flash("Please check your email for a verification code.", "warning")
                    return redirect(url_for("verify_2fa"))
                finish_login(student)
                flash("Logged in successfully!", "success")
                return redirect_user_by_role(student)

            flash("Invalid email/student ID or password.", "danger")

        return render_template("login.html")

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        return special_role_login(
            role="admin",
            required_key=app.config["ADMIN_KEY"],
            dashboard_endpoint="admin_dashboard",
            template="admin_login.html"
        )

    @app.route("/manager/login", methods=["GET", "POST"])
    def manager_login():
        return special_role_login(
            role="manager",
            required_key=app.config["MANAGER_KEY"],
            dashboard_endpoint="manager_dashboard",
            template="manager_login.html"
        )

    @app.route("/staff/login", methods=["GET", "POST"])
    def staff_login():
        return special_role_login(
            role="staff",
            required_key=app.config["STAFF_KEY"],
            dashboard_endpoint="staff_dashboard",
            template="staff_login.html"
        )

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    # ─────────────────────────────────────────────
    # DASHBOARDS  (all now include a link to menu)
    # ─────────────────────────────────────────────

    @app.route("/admin/dashboard")
    @login_required
    def admin_dashboard():
        if current_user.role != "admin":
            flash("Access denied. Admins only.", "danger")
            return redirect_user_by_role(current_user)

        total_students = Student.query.filter_by(role="student").count()
        total_staff = Student.query.filter_by(role="staff").count()
        total_orders = Order.query.count()
        total_menu_items = MenuItem.query.count()

        return render_template(
            "admin_dashboard.html",
            total_students=total_students,
            total_staff=total_staff,
            total_orders=total_orders,
            total_menu_items=total_menu_items
        )

    @app.route("/manager/dashboard")
    @login_required
    def manager_dashboard():
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status="pending").count()
        completed_orders = Order.query.filter_by(status="completed").count()

        orders = Order.query.all()
        total_sales = sum(order.total_amount for order in orders)

        return render_template(
            "manager_dashboard.html",
            total_orders=total_orders,
            pending_orders=pending_orders,
            completed_orders=completed_orders,
            total_sales=total_sales
        )

    @app.route("/staff/dashboard")
    @login_required
    def staff_dashboard():
        if current_user.role != "staff":
            flash("Access denied. Staff only.", "danger")
            return redirect_user_by_role(current_user)

        orders = Order.query.order_by(Order.created_at.desc()).all()
        return render_template("staff_dashboard.html", orders=orders)

    def ticket_error(order):
        if not order:
            return "Invalid ticket code or registration number."
        if not order.paid_at:
            return "Ticket has no confirmed payment."
        if order.collected_at:
            return "Ticket already collected."
        if order.status == "cancelled":
            return "Order was cancelled."
        if order.status == "completed":
            return "Order already completed."
        if not order.created_at or datetime.now(TICKET_TIMEZONE) >= expiry_for(order.created_at, order.ticket_extension_days or 0):
            return "Ticket expired."
        return None

    @app.route("/staff/serve")
    @login_required
    def serve_orders():
        if current_user.role != "staff":
            return redirect_user_by_role(current_user)
        token = secrets.token_urlsafe(32)
        session["serve_csrf"] = token
        return render_template("serve_orders.html", serve_csrf=token)

    @app.route("/staff/serve/verify", methods=["POST"])
    @login_required
    def verify_ticket():
        if current_user.role != "staff":
            return jsonify(error="Staff access required."), 403
        if request.headers.get("X-Serve-CSRF") != session.get("serve_csrf") or not session.get("serve_csrf"):
            return jsonify(error="Session expired. Reload this page."), 403
        data = request.get_json(silent=True) or {}
        scanned_value = str(data.get("code", "")).strip()
        code = scanned_value.upper()
        reg = str(data.get("registration", "")).strip()
        if not code or (data.get("mode") == "manual" and not reg):
            return jsonify(error="Enter both registration number and ticket code."), 400
        if data.get("mode") == "scan" and scanned_value.startswith("MSUT1."):
            payload = verify_ticket_payload(scanned_value, app.ticket_private_key.public_key())
            if not payload:
                return jsonify(error="Invalid ticket signature."), 400
            order = db.session.get(Order, payload["id"])
            if not order or order.ticket_code != payload.get("code") or order.student.student_id != payload.get("reg") or not order.created_at or payload.get("exp") not in (int(expiry_for(order.created_at, days).timestamp()) for days in range((order.ticket_extension_days or 0) + 1)):
                return jsonify(error="Ticket details do not match the server."), 400
        else:
            order = Order.query.filter_by(ticket_code=code).first()
        if order and reg and order.student.student_id.casefold() != reg.casefold():
            order = None
        error = ticket_error(order)
        if error:
            return jsonify(error=error), 400
        return jsonify(order_id=order.id, code=order.ticket_code,
                       registration=order.student.student_id,
                       items=[{"name": item.menu_item.name, "quantity": item.quantity} for item in order.items])

    @app.route("/staff/serve/approve", methods=["POST"])
    @login_required
    def approve_ticket():
        if current_user.role != "staff":
            return jsonify(error="Staff access required."), 403
        if request.headers.get("X-Serve-CSRF") != session.get("serve_csrf") or not session.get("serve_csrf"):
            return jsonify(error="Session expired. Reload this page."), 403
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip().upper()
        reg = str(data.get("registration", "")).strip()
        # The conditional update prevents a second concurrent approval from collecting twice.
        order = Order.query.filter_by(ticket_code=code).first()
        if order and order.student.student_id.casefold() != reg.casefold():
            order = None
        error = ticket_error(order)
        if error:
            return jsonify(error=error), 400
        changed = Order.query.filter_by(id=order.id, collected_at=None).update({
            "collected_at": datetime.utcnow(), "collected_by_id": current_user.id,
            "status": "completed"}, synchronize_session=False)
        if not changed:
            db.session.rollback()
            return jsonify(error="Ticket already collected."), 400
        db.session.commit()
        return jsonify(message="Meal collected successfully.")

    # ─────────────────────────────────────────────
    # MANAGER ROUTES  (Manager only)
    # ─────────────────────────────────────────────

    @app.route("/manager/meals")
    @login_required
    def manager_meals():
        """Display all menu items for management."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        page = request.args.get("page", 1, type=int)
        items = MenuItem.query.paginate(page=page, per_page=12)
        categories = Category.query.filter_by(is_active=True).all()

        return render_template(
            "manager_meals.html",
            items=items,
            categories=categories
        )

    @app.route("/manager/meal/add", methods=["GET", "POST"])
    @login_required
    def add_meal():
        """Add a new meal to the menu."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            price = request.form.get("price", "")
            category_id = request.form.get("category_id", "")
            image_url = request.form.get("image_url", "").strip()
            preparation_time = request.form.get("preparation_time", 15, type=int)
            calories = request.form.get("calories", "", type=lambda x: int(x) if x else None)
            is_vegetarian = request.form.get("is_vegetarian") == "on"
            is_vegan = request.form.get("is_vegan") == "on"
            is_gluten_free = request.form.get("is_gluten_free") == "on"

            if not name or not price or not category_id:
                flash("Name, price, and category are required.", "danger")
                categories = Category.query.filter_by(is_active=True).all()
                return render_template("manager_meal_form.html", categories=categories)

            try:
                price = float(price)
                if not 0 < price <= (0.30 if name.casefold() == "water" else 1.50):
                    raise ValueError("Price must be positive")
            except ValueError:
                flash("Price must be between $0.01 and $1.50 ($0.30 maximum for water).", "danger")
                categories = Category.query.filter_by(is_active=True).all()
                return render_template("manager_meal_form.html", categories=categories)

            category = Category.query.get(category_id)
            if not category:
                flash("Invalid category selected.", "danger")
                categories = Category.query.filter_by(is_active=True).all()
                return render_template("manager_meal_form.html", categories=categories)

            item = MenuItem(
                name=name,
                description=description,
                price=price,
                category_id=category_id,
                image_url=image_url if image_url else None,
                preparation_time=preparation_time,
                calories=calories,
                is_vegetarian=is_vegetarian,
                is_vegan=is_vegan,
                is_gluten_free=is_gluten_free,
                is_available=True
            )

            db.session.add(item)
            db.session.commit()

            flash(f"Meal '{name}' added successfully!", "success")
            return redirect(url_for("manager_meals"))

        categories = Category.query.filter_by(is_active=True).all()
        return render_template("manager_meal_form.html", categories=categories)

    @app.route("/manager/meal/<int:item_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_meal(item_id):
        """Edit an existing meal."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        item = MenuItem.query.get_or_404(item_id)

        if request.method == "POST":
            item.name = request.form.get("name", "").strip() or item.name
            item.description = request.form.get("description", "").strip()
            
            price = request.form.get("price", "")
            if price:
                try:
                    price = float(price)
                    if not 0 < price <= (0.30 if item.name.casefold() == "water" else 1.50):
                        raise ValueError("Price must be positive")
                    item.price = price
                except ValueError:
                    flash("Price must be between $0.01 and $1.50 ($0.30 maximum for water).", "danger")
                    categories = Category.query.filter_by(is_active=True).all()
                    return render_template("manager_meal_form.html", item=item, categories=categories)

            category_id = request.form.get("category_id", "")
            if category_id:
                category = Category.query.get(category_id)
                if category:
                    item.category_id = category_id
                else:
                    flash("Invalid category selected.", "danger")
                    categories = Category.query.filter_by(is_active=True).all()
                    return render_template("manager_meal_form.html", item=item, categories=categories)

            item.image_url = request.form.get("image_url", "").strip() or None
            item.preparation_time = request.form.get("preparation_time", item.preparation_time, type=int)
            
            calories = request.form.get("calories", "")
            if calories:
                try:
                    item.calories = int(calories)
                except ValueError:
                    pass

            item.is_vegetarian = request.form.get("is_vegetarian") == "on"
            item.is_vegan = request.form.get("is_vegan") == "on"
            item.is_gluten_free = request.form.get("is_gluten_free") == "on"
            item.is_available = request.form.get("is_available") == "on"
            if item.name.casefold() == "water" and item.price > 0.30:
                flash("Water cannot cost more than $0.30.", "danger")
                categories = Category.query.filter_by(is_active=True).all()
                return render_template("manager_meal_form.html", item=item, categories=categories)

            db.session.commit()
            flash(f"Meal '{item.name}' updated successfully!", "success")
            return redirect(url_for("manager_meals"))

        categories = Category.query.filter_by(is_active=True).all()
        return render_template("manager_meal_form.html", item=item, categories=categories)

    @app.route("/manager/meal/<int:item_id>/delete", methods=["POST"])
    @login_required
    def delete_meal(item_id):
        """Delete a meal from the menu."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        item = MenuItem.query.get_or_404(item_id)
        item_name = item.name

        db.session.delete(item)
        db.session.commit()

        flash(f"Meal '{item_name}' deleted successfully!", "success")
        return redirect(url_for("manager_meals"))

    @app.route("/manager/alerts")
    @login_required
    def manager_alerts():
        """Manage canteen alerts and announcements."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        alerts = Alert.query.order_by(Alert.created_at.desc()).all()
        return render_template("manager_alerts.html", alerts=alerts)

    @app.route("/manager/alert/create", methods=["POST"])
    @login_required
    def create_alert():
        """Create a new alert."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        alert_type = request.form.get("alert_type", "info")

        if not title or not message:
            flash("Title and message are required.", "danger")
            return redirect(url_for("manager_alerts"))

        if alert_type not in ["info", "warning", "urgent"]:
            alert_type = "info"

        alert = Alert(
            title=title,
            message=message,
            alert_type=alert_type,
            created_by=current_user.id,
            is_active=True
        )

        db.session.add(alert)
        db.session.commit()

        flash(f"Alert '{title}' created successfully!", "success")
        return redirect(url_for("manager_alerts"))

    @app.route("/manager/alert/<int:alert_id>/delete", methods=["POST"])
    @login_required
    def delete_alert(alert_id):
        """Delete an alert."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        alert = Alert.query.get_or_404(alert_id)
        alert_title = alert.title

        db.session.delete(alert)
        db.session.commit()

        flash(f"Alert '{alert_title}' deleted successfully!", "success")
        return redirect(url_for("manager_alerts"))

    @app.route("/manager/alert/<int:alert_id>/toggle", methods=["POST"])
    @login_required
    def toggle_alert(alert_id):
        """Toggle alert active status."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        alert = Alert.query.get_or_404(alert_id)
        alert.is_active = not alert.is_active
        db.session.commit()

        status = "activated" if alert.is_active else "deactivated"
        flash(f"Alert '{alert.title}' {status}!", "success")
        return redirect(url_for("manager_alerts"))

    @app.route("/manager/orders/modify")
    @login_required
    def manager_modify_orders():
        """Search and manage orders, including replacing unavailable items."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        search_term = request.args.get("q", "").strip()
        status_filter = request.args.get("status", "pending")
        if status_filter not in ("", *ORDER_STATUSES):
            status_filter = "pending"

        orders_query = Order.query
        if search_term:
            orders_query = orders_query.filter(
                Order.order_number.ilike(f"%{search_term}%")
            )
            status_filter = ""
        elif status_filter:
            orders_query = orders_query.filter_by(status=status_filter)
        orders = orders_query.order_by(Order.created_at.desc()).all()

        available_items = MenuItem.query.filter_by(is_available=True).all()
        session["manager_order_csrf"] = secrets.token_urlsafe(32)
        return render_template(
            "manager_modify_orders.html",
            orders=orders,
            available_items=available_items,
            manager_order_csrf=session["manager_order_csrf"],
            ticket_expiry=lambda order: expiry_for(order.created_at, order.ticket_extension_days or 0),
            can_extend_ticket=lambda order: order.paid_at and order.ticket_code and not order.collected_at
                and order.status not in ("completed", "cancelled") and not order.ticket_extension_days
                and order.created_at and datetime.now(TICKET_TIMEZONE) < expiry_for(order.created_at, 1),
            status_filter=status_filter,
            search_term=search_term,
            order_statuses=ORDER_STATUSES
        )

    @app.route("/manager/order/<int:order_id>/status", methods=["POST"])
    @login_required
    def update_order_status(order_id):
        """Update an order's status, including reopening completed orders."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        order = Order.query.get_or_404(order_id)
        new_status = request.form.get("status", "").strip()
        if new_status not in ORDER_STATUSES:
            flash("Select a valid order status.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))

        previous_status = order.status
        if order.collected_at and new_status != "completed":
            flash("Collected orders cannot be reopened.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))
        order.status = new_status
        db.session.commit()

        flash(
            f"Order {order.order_number} status changed from "
            f"{previous_status.title()} to {new_status.title()}.",
            "success"
        )
        search_term = request.form.get("order_search", "").strip()
        if search_term:
            return redirect(url_for("manager_modify_orders", q=search_term))
        return redirect(url_for("manager_modify_orders", status=new_status))

    @app.route("/manager/order/<int:order_id>/modify-items", methods=["POST"])
    @login_required
    def modify_order_items(order_id):
        """Edit each meal and quantity in an order."""
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)

        order = Order.query.get_or_404(order_id)
        if not session.get("manager_order_csrf") or not secrets.compare_digest(request.form.get("manager_order_csrf", ""), session["manager_order_csrf"]):
            flash("Manager session expired. Reload the order page.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))
        if order.collected_at or order.status in ("completed", "cancelled"):
            flash("Collected, completed, or cancelled orders cannot be edited.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))

        changes = []
        for order_item in order.items:
            try:
                new_item_id = int(request.form.get(f"meal_{order_item.id}"))
                quantity = int(request.form.get(f"quantity_{order_item.id}"))
            except (TypeError, ValueError):
                flash("Select a valid meal and quantity for every item.", "danger")
                return redirect(url_for("manager_modify_orders", q=order.order_number))
            new_item = db.session.get(MenuItem, new_item_id)
            if (not new_item or not 1 <= quantity <= 10 or
                    (not new_item.is_available and new_item.id != order_item.menu_item_id)):
                flash("Select an available meal and a quantity from 1 to 10.", "danger")
                return redirect(url_for("manager_modify_orders", q=order.order_number))
            changes.append((order_item, new_item, quantity))

        for order_item, new_item, quantity in changes:
            order_item.menu_item_id = new_item.id
            order_item.quantity = quantity
            order_item.unit_price = new_item.price
            order_item.subtotal = round(new_item.price * quantity, 2)

        order.total_amount = round(sum(item.subtotal for item in order.items), 2)
        db.session.commit()
        flash("Order meals and quantities updated.", "success")
        return redirect(url_for("manager_modify_orders", q=order.order_number))

    @app.route("/manager/order/<int:order_id>/extend-ticket", methods=["POST"])
    @login_required
    def extend_ticket(order_id):
        if current_user.role != "manager":
            flash("Access denied. Managers only.", "danger")
            return redirect_user_by_role(current_user)
        order = Order.query.get_or_404(order_id)
        if not session.get("manager_order_csrf") or not secrets.compare_digest(request.form.get("manager_order_csrf", ""), session["manager_order_csrf"]):
            flash("Manager session expired. Reload the order page.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))
        if (not order.paid_at or not order.ticket_code or order.collected_at or
                order.status in ("completed", "cancelled") or order.ticket_extension_days or
                not order.created_at or datetime.now(TICKET_TIMEZONE) >= expiry_for(order.created_at, 1)):
            flash("This ticket cannot be extended.", "danger")
            return redirect(url_for("manager_modify_orders", q=order.order_number))
        order.ticket_extension_days = 1
        db.session.commit()
        flash("Ticket extended by one day. The holder will see the new expiry on their ticket.", "success")
        return redirect(url_for("manager_modify_orders", q=order.order_number))

    # ─────────────────────────────────────────────
    # MENU  (accessible to ALL authenticated roles)
    # ─────────────────────────────────────────────

    @app.route("/menu")
    def menu():
        category_id = request.args.get("category")
        search_query = request.args.get("q")

        if category_id:
            items = MenuItem.query.filter_by(
                category_id=category_id, is_available=True
            ).all()
        elif search_query:
            items = MenuItem.query.filter(
                MenuItem.is_available == True,
                MenuItem.name.ilike(f"%{search_query}%")
            ).all()
        else:
            items = MenuItem.query.filter_by(is_available=True).all()

        categories = Category.query.filter_by(
            is_active=True
        ).order_by(Category.display_order).all()

        return render_template(
            "menu.html",
            items=items,
            categories=categories,
            selected_category=category_id
        )

    @app.route("/menu/<int:item_id>")
    def menu_item_detail(item_id):
        item = MenuItem.query.get_or_404(item_id)
        return render_template("item_detail.html", item=item)

    # ─────────────────────────────────────────────
    # CART  (students only for placing orders)
    # ─────────────────────────────────────────────

    @app.route("/cart")
    def cart():
        cart_data = session.get("cart", {})
        cart_items = []
        total = 0

        for item_id, quantity in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.is_available:
                subtotal = item.price * quantity
                cart_items.append({"item": item, "quantity": quantity, "subtotal": subtotal})
                total += subtotal

        return render_template("cart.html", cart_items=cart_items, total=total)

    @app.route("/cart/add/<int:item_id>", methods=["POST"])
    def add_to_cart(item_id):
        item = MenuItem.query.get_or_404(item_id)

        if not item.is_available:
            flash("This item is currently unavailable.", "danger")
            return redirect(url_for("menu"))

        quantity = request.form.get("quantity", 1, type=int)
        if quantity is None or not 1 <= quantity <= 10:
            flash("Choose a quantity from 1 to 10.", "danger")
            return redirect(url_for("menu"))
        cart_data = session.get("cart", {})
        cart_data[str(item_id)] = min(10, cart_data.get(str(item_id), 0) + quantity)
        session["cart"] = cart_data

        flash(f"{item.name} added to cart!", "success")
        return redirect(url_for("cart"))

    @app.route("/cart/update/<int:item_id>", methods=["POST"])
    def update_cart(item_id):
        quantity = request.form.get("quantity", 0, type=int)
        if quantity is None or quantity > 10:
            flash("Choose a quantity from 1 to 10.", "danger")
            return redirect(url_for("cart"))
        cart_data = session.get("cart", {})

        if quantity > 0:
            cart_data[str(item_id)] = quantity
        else:
            cart_data.pop(str(item_id), None)

        session["cart"] = cart_data
        flash("Cart updated.", "success")
        return redirect(url_for("cart"))

    @app.route("/cart/remove/<int:item_id>")
    def remove_from_cart(item_id):
        cart_data = session.get("cart", {})
        cart_data.pop(str(item_id), None)
        session["cart"] = cart_data
        flash("Item removed from cart.", "info")
        return redirect(url_for("cart"))

    @app.route("/cart/clear")
    def clear_cart():
        session.pop("cart", None)
        flash("Cart cleared.", "info")
        return redirect(url_for("cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        if current_user.role != "student":
            flash("Only students can place orders.", "danger")
            return redirect_user_by_role(current_user)

        cart_data = session.get("cart", {})

        if not cart_data:
            flash("Your cart is empty.", "warning")
            return redirect(url_for("menu"))

        total = 0
        order_items = []

        for item_id, quantity in cart_data.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.is_available and isinstance(quantity, int) and 1 <= quantity <= 10:
                subtotal = item.price * quantity
                order_items.append({"item": item, "quantity": quantity, "subtotal": subtotal})
                total += subtotal

        if not order_items or len(order_items) != len(cart_data):
            flash("Some cart items are unavailable. Review your cart before paying.", "danger")
            return redirect(url_for("cart"))

        if request.method == "POST":
            if not session.get("checkout_csrf") or not secrets.compare_digest(request.form.get("checkout_csrf", ""), session["checkout_csrf"]):
                flash("Checkout session expired. Please try again.", "danger")
                return redirect(url_for("checkout"))
            payment_method = request.form.get("payment_method")
            payment_reference = request.form.get("payment_reference", "").strip()
            if payment_method not in ("ecocash", "gold_card", "bank_account") or not (4 <= len(payment_reference) <= 50):
                flash("Choose a payment option and enter a demo account or phone identifier (4–50 characters).", "danger")
                return redirect(url_for("checkout"))
            if total > HIGH_VALUE_ORDER_LIMIT:
                if not start_2fa(
                    current_user,
                    "high_value_order",
                    f"confirm your ${total:.2f} order",
                    pending_payment_method=payment_method,
                    pending_order_cart=dict(cart_data)
                ):
                    flash("Unable to send verification email right now. Please try again later.", "danger")
                    return render_template("checkout.html", order_items=order_items, total=total, checkout_csrf=session["checkout_csrf"])
                flash("Please verify this order with the code sent to your email.", "warning")
                return redirect(url_for("verify_2fa"))

            order = create_order_from_cart(current_user, payment_method=payment_method)
            session.pop("checkout_csrf", None)
            flash(f"Demo payment successful! Order number: {order.order_number}", "success")
            return redirect(url_for("order_confirmation", order_id=order.id))

        session["checkout_csrf"] = secrets.token_urlsafe(32)
        return render_template("checkout.html", order_items=order_items, total=total, checkout_csrf=session["checkout_csrf"])

    @app.route("/order/<int:order_id>")
    @login_required
    def order_confirmation(order_id):
        order = Order.query.get_or_404(order_id)

        if current_user.role == "student" and order.student_id != current_user.id:
            flash("Access denied.", "danger")
            return redirect(url_for("menu"))

        signed_ticket = issue_ticket(order, app.ticket_private_key) if order.paid_at and order.ticket_code else None
        expires_at = expiry_for(order.created_at, order.ticket_extension_days or 0) if signed_ticket else None
        return render_template("order_confirmation.html", order=order, signed_ticket=signed_ticket, expires_at=expires_at)

    @app.route("/orders")
    @login_required
    def my_orders():
        if current_user.role == "student":
            orders = Order.query.filter_by(
                student_id=current_user.id
            ).order_by(Order.created_at.desc()).all()
        else:
            orders = Order.query.order_by(Order.created_at.desc()).all()

        return render_template("my_orders.html", orders=orders)

    @app.route("/order/<int:order_id>/status")
    @login_required
    def order_status(order_id):
        order = Order.query.get_or_404(order_id)

        if current_user.role == "student" and order.student_id != current_user.id:
            return jsonify({"error": "Access denied"}), 403

        return jsonify({"order_number": order.order_number, "status": order.status})

    @app.route("/order/<int:order_id>/feedback", methods=["GET", "POST"])
    @login_required
    def submit_feedback(order_id):
        if current_user.role != "student":
            flash("Only students can submit feedback.", "danger")
            return redirect_user_by_role(current_user)

        order = Order.query.get_or_404(order_id)

        if order.student_id != current_user.id:
            flash("Access denied.", "danger")
            return redirect(url_for("menu"))

        if order.status != "completed":
            flash("You can only provide feedback for completed orders.", "warning")
            return redirect(url_for("my_orders"))

        if order.feedback:
            flash("Feedback already submitted for this order.", "info")
            return redirect(url_for("my_orders"))

        if request.method == "POST":
            rating = int(request.form.get("rating"))
            comment = request.form.get("comment")

            feedback = Feedback(
                order_id=order.id,
                rating=rating,
                comment=comment
            )

            db.session.add(feedback)
            db.session.commit()

            flash("Thank you for your feedback!", "success")
            return redirect(url_for("my_orders"))

        return render_template("feedback.html", order=order)

    @app.route("/api/menu")
    def api_menu():
        items = MenuItem.query.filter_by(is_available=True).all()
        return jsonify([item.to_dict() for item in items])

    @app.route("/api/categories")
    def api_categories():
        categories = Category.query.filter_by(
            is_active=True
        ).order_by(Category.display_order).all()
        return jsonify([category.to_dict() for category in categories])


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def special_role_login(role, required_key, dashboard_endpoint, template):
    """
    Login for admin, manager, and staff.

    These users do not sign up via the public register page.
    They enter their email + the role-specific access key.
    If the email is new and the key is correct, the account is created automatically.
    After a successful login they are redirected to their dashboard AND can also
    navigate to the menu just like a student.
    """

    if current_user.is_authenticated:
        return redirect_user_by_role(current_user)

    if request.method == "POST":
        email = request.form.get("email")
        access_key = request.form.get("access_key")

        if not email or not access_key:
            flash("Please enter your email and access key.", "danger")
            return redirect(request.path)

        if access_key != required_key:
            flash("Invalid access key.", "danger")
            return redirect(request.path)

        user = Student.query.filter_by(email=email).first()

        if user:
            if user.role != role:
                flash(f"This email is already registered as {user.role}.", "danger")
                return redirect(request.path)
        else:
            user = Student(
                student_id=generate_system_user_id(role),
                name=f"{role.title()} User",
                email=email,
                password_hash=generate_password_hash(required_key),
                role=role,
                is_verified=True
            )
            db.session.add(user)
            db.session.commit()

        login_user(user)
        flash(f"Logged in successfully as {role}.", "success")
        return redirect(url_for(dashboard_endpoint))

    return render_template(template, role=role)


def redirect_user_by_role(user):
    """Redirect logged-in users to the correct dashboard."""
    if user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if user.role == "manager":
        return redirect(url_for("manager_dashboard"))
    if user.role == "staff":
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("menu"))


def generate_system_user_id(role):
    """Generate a short unique ID for admin, manager, and staff accounts."""
    prefix = role.upper()[:5]
    while True:
        random_suffix = "".join(random.choices(string.digits, k=6))
        generated_id = f"{prefix}{random_suffix}"
        if not Student.query.filter_by(student_id=generated_id).first():
            return generated_id


def generate_order_number():
    """Generate a unique cafeteria order number."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    random_suffix = "".join(random.choices(string.digits, k=4))
    return f"MSU-{timestamp}-{random_suffix}"


def seed_database():
    """Seed and refresh the affordable Zimbabwean canteen menu."""
    categories = [
        Category(name="Main Meals", description="Hearty main dishes", icon="utensils", display_order=1),
        Category(name="Fast Food", description="Quick bites and snacks", icon="hamburger", display_order=2),
        Category(name="Beverages", description="Drinks and refreshments", icon="coffee", display_order=3),
        Category(name="Snacks", description="Light snacks and treats", icon="cookie", display_order=4),
        Category(name="Vegetarian", description="Vegetarian options", icon="leaf", display_order=5),
    ]
    if not Category.query.first():
        db.session.add_all(categories)
        db.session.flush()

    menu = {
        "Chicken Stew": (1.50, "Chicken stew served with sadza", "Main Meals"),
        "Beef Sadza": (1.50, "Sadza with beef stew and vegetables", "Main Meals"),
        "Rice and Stew": (1.20, "Rice with vegetable stew", "Main Meals"),
        "Sadza and Beans": (0.80, "Sadza with sugar beans and vegetables", "Main Meals"),
        "Sadza and Vegetables": (0.70, "Sadza with seasonal greens", "Vegetarian"),
        "Rice and Chicken": (1.50, "Rice with chicken stew", "Main Meals"),
        "Maputi": (0.40, "Roasted maize snack", "Snacks"),
        "Fried Chips": (0.80, "Freshly fried potato chips", "Snacks"),
        "Samosa": (0.50, "Vegetable samosa", "Snacks"),
        "Banana": (0.30, "Fresh banana", "Snacks"),
        "Tea": (0.30, "Hot tea", "Beverages"),
        "Water": (0.30, "Bottled water 500ml", "Beverages"),
        "Bean Stew": (1.00, "Sugar beans served with rice", "Vegetarian"),
    }
    category_ids = {category.name: category.id for category in Category.query.all()}
    retired_items = {"Fish and Chips", "Pasta Carbonara", "Hamburger", "Chicken Wrap",
                     "Pizza Slice", "Hot Dog", "Fresh Juice", "Coffee", "Soft Drink",
                     "Sandwich", "Fruit Salad", "Vegetable Curry", "Veggie Burger"}
    for item in MenuItem.query.all():
        if item.name in menu:
            price, description, category = menu[item.name]
            if item.price > 1.50 or (item.name == "Water" and item.price != 0.30):
                item.price = price
            item.description = description
            item.category_id = category_ids[category]
        elif item.name in retired_items:
            if item.order_items.count():
                item.is_available = False
            else:
                db.session.delete(item)
        elif item.price > 1.50:
            item.is_available = False
    for name, (price, description, category) in menu.items():
        if not MenuItem.query.filter_by(name=name).first():
            db.session.add(MenuItem(name=name, price=price, description=description,
                                    category_id=category_ids[category], is_available=True))
    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
