from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import inspect, text
from datetime import datetime, timedelta
import os
import random
import string

from config import config
from models import db, Student, Category, MenuItem, Order, OrderItem, Feedback

mail = Mail()


def create_app(config_name=None):
    """Create and configure the Flask application."""

    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

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
            if student and student.is_verified:
                return student
            return None
        except (ValueError, TypeError):
            return None

    register_routes(app)

    with app.app_context():
        db.create_all()
        ensure_student_verified_column(app)
        seed_database()

    return app


def ensure_student_verified_column(app):
    """Ensure is_verified column exists in students table for backwards compatibility."""
    try:
        inspector = inspect(db.engine)
        if "students" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("students")]
            if "is_verified" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE students ADD COLUMN is_verified BOOLEAN DEFAULT 0"))
    except Exception as e:
        app.logger.warning(f"Could not ensure is_verified column: {e}")


def register_routes(app):
    """Register all application routes."""

    def send_2fa_email(email, code):
        """Send 2FA verification code via email."""
        if not app.config.get("MAIL_USERNAME") or not app.config.get("MAIL_PASSWORD"):
            app.logger.warning("Email credentials are not configured; dropping 2FA email and printing code to console.")
            print(f"[2FA DEBUG] Send code to {email}: {code}")
            return True

        msg = Message(
            subject="Your 2FA Verification Code",
            recipients=[email],
            body=f"Your verification code is: {code}\n\nPlease enter this code to complete your registration."
        )
        try:
            mail.send(msg)
            return True
        except Exception as exc:
            app.logger.error("Failed to send 2FA email: %s", exc)
            return False

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

            if Student.query.filter_by(student_id=student_id).first():
                flash("Student ID already registered.", "danger")
                return render_template("register.html")

            if Student.query.filter_by(email=email).first():
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

            # Generate 2FA code
            code = ''.join(random.choices(string.digits, k=6))
            session['2fa_code'] = code
            session['pending_user_id'] = student.id

            # Send verification email
            if not send_2fa_email(student.email, code):
                flash("Unable to send verification email right now. Please try again later.", "danger")
                return render_template("register.html")

            flash("Registration successful! Please check your email for the verification code.", "success")
            return redirect(url_for("verify_2fa"))

        return render_template("register.html")

    @app.route("/verify-2fa", methods=["GET", "POST"])
    def verify_2fa():
        if current_user.is_authenticated:
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
                    student.is_verified = True
                    db.session.commit()
                    session.pop('2fa_code', None)
                    session.pop('pending_user_id', None)
                    login_user(student)
                    flash("Verification successful! Welcome!", "success")
                    return redirect_user_by_role(student)
                else:
                    flash("User not found.", "danger")
            else:
                flash("Invalid verification code.", "danger")

        return render_template("verify_2fa.html")

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
                    # Generate new 2FA code for unverified user
                    code = ''.join(random.choices(string.digits, k=6))
                    session['2fa_code'] = code
                    session['pending_user_id'] = student.id
                    if not send_2fa_email(student.email, code):
                        flash("Unable to send verification email right now. Please try again later.", "danger")
                        return render_template("login.html")
                    flash("Please verify your account first. Check your email for the code.", "warning")
                    return redirect(url_for("verify_2fa"))
                login_user(student)
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

        quantity = int(request.form.get("quantity", 1))
        cart_data = session.get("cart", {})
        cart_data[str(item_id)] = cart_data.get(str(item_id), 0) + quantity
        session["cart"] = cart_data

        flash(f"{item.name} added to cart!", "success")
        return redirect(url_for("cart"))

    @app.route("/cart/update/<int:item_id>", methods=["POST"])
    def update_cart(item_id):
        quantity = int(request.form.get("quantity", 0))
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
            if item and item.is_available:
                subtotal = item.price * quantity
                order_items.append({"item": item, "quantity": quantity, "subtotal": subtotal})
                total += subtotal

        if request.method == "POST":
            notes = request.form.get("notes")
            order_number = generate_order_number()

            order = Order(
                order_number=order_number,
                student_id=current_user.id,
                total_amount=total,
                notes=notes,
                estimated_ready_time=datetime.utcnow() + timedelta(minutes=20)
            )

            db.session.add(order)
            db.session.flush()

            for item_id, quantity in cart_data.items():
                item = MenuItem.query.get(int(item_id))
                if item and item.is_available:
                    order_item = OrderItem(
                        order_id=order.id,
                        menu_item_id=item.id,
                        quantity=quantity,
                        unit_price=item.price,
                        subtotal=item.price * quantity
                    )
                    db.session.add(order_item)

            db.session.commit()
            session.pop("cart", None)

            flash(f"Order placed successfully! Order number: {order_number}", "success")
            return redirect(url_for("order_confirmation", order_id=order.id))

        return render_template("checkout.html", order_items=order_items, total=total)

    @app.route("/order/<int:order_id>")
    @login_required
    def order_confirmation(order_id):
        order = Order.query.get_or_404(order_id)

        if current_user.role == "student" and order.student_id != current_user.id:
            flash("Access denied.", "danger")
            return redirect(url_for("menu"))

        return render_template("order_confirmation.html", order=order)

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

        return jsonify({
            "order_number": order.order_number,
            "status": order.status,
            "estimated_ready_time": (
                order.estimated_ready_time.isoformat()
                if order.estimated_ready_time else None
            )
        })

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
                role=role
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
    """Add default categories and menu items if database is empty."""
    if Category.query.first():
        return

    categories = [
        Category(name="Main Meals", description="Hearty main dishes", icon="utensils", display_order=1),
        Category(name="Fast Food", description="Quick bites and snacks", icon="hamburger", display_order=2),
        Category(name="Beverages", description="Drinks and refreshments", icon="coffee", display_order=3),
        Category(name="Snacks", description="Light snacks and treats", icon="cookie", display_order=4),
        Category(name="Vegetarian", description="Vegetarian options", icon="leaf", display_order=5),
    ]
    for category in categories:
        db.session.add(category)
    db.session.commit()

    menu_items = [
        MenuItem(name="Chicken Stew", description="Tender chicken in rich tomato sauce with vegetables", price=45.00, category_id=1, preparation_time=20, calories=450),
        MenuItem(name="Beef Sadza", description="Traditional sadza with tender beef and vegetables", price=50.00, category_id=1, preparation_time=25, calories=550),
        MenuItem(name="Fish and Chips", description="Crispy fried fish with golden chips", price=55.00, category_id=1, preparation_time=15, calories=480),
        MenuItem(name="Pasta Carbonara", description="Creamy pasta with bacon and parmesan", price=40.00, category_id=1, preparation_time=15, calories=520),
        MenuItem(name="Rice and Stew", description="Steamed rice with vegetable stew", price=35.00, category_id=1, preparation_time=15, calories=380),
        MenuItem(name="Hamburger", description="Beef patty with lettuce, tomato, and special sauce", price=30.00, category_id=2, preparation_time=10, calories=380),
        MenuItem(name="Chicken Wrap", description="Grilled chicken with fresh vegetables in a wrap", price=35.00, category_id=2, preparation_time=8, calories=320),
        MenuItem(name="Pizza Slice", description="Cheese and tomato pizza slice", price=15.00, category_id=2, preparation_time=5, calories=250),
        MenuItem(name="Hot Dog", description="Grilled sausage in a bun with toppings", price=20.00, category_id=2, preparation_time=5, calories=290),
        MenuItem(name="Fresh Juice", description="Mixed fruit juice seasonal", price=20.00, category_id=3, preparation_time=3, calories=120),
        MenuItem(name="Coffee", description="Hot brewed coffee", price=15.00, category_id=3, preparation_time=2, calories=5),
        MenuItem(name="Tea", description="Hot tea with milk and sugar", price=10.00, category_id=3, preparation_time=2, calories=40),
        MenuItem(name="Soft Drink", description="Assorted soft drinks 350ml", price=12.00, category_id=3, preparation_time=1, calories=140),
        MenuItem(name="Water", description="Bottled water 500ml", price=8.00, category_id=3, preparation_time=1, calories=0),
        MenuItem(name="Sandwich", description="Ham and cheese sandwich", price=25.00, category_id=4, preparation_time=5, calories=280),
        MenuItem(name="Samosa", description="Crispy vegetable samosa 2 pieces", price=15.00, category_id=4, preparation_time=5, calories=200),
        MenuItem(name="Fried Chips", description="Seasoned fried potato chips", price=20.00, category_id=4, preparation_time=8, calories=310),
        MenuItem(name="Fruit Salad", description="Fresh seasonal fruits", price=25.00, category_id=4, preparation_time=5, calories=150),
        MenuItem(name="Vegetable Curry", description="Mixed vegetables in creamy curry sauce", price=35.00, category_id=5, preparation_time=15, calories=320, is_vegetarian=True, is_vegan=True),
        MenuItem(name="Bean Stew", description="Hearty bean stew with rice", price=30.00, category_id=5, preparation_time=15, calories=280, is_vegetarian=True, is_vegan=True),
        MenuItem(name="Veggie Burger", description="Plant-based burger with all the toppings", price=40.00, category_id=5, preparation_time=10, calories=350, is_vegetarian=True, is_vegan=True),
    ]
    for item in menu_items:
        db.session.add(item)
    db.session.commit()
    print("Database seeded successfully!")


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)