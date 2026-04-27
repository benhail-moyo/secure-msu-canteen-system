from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class Student(UserMixin, db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)

    name = db.Column(db.String(100), nullable=False, default="System User")

    email = db.Column(db.String(120), unique=True, nullable=False, index=True)

    password_hash = db.Column(db.String(256), nullable=False)

    department = db.Column(db.String(100))

    phone = db.Column(db.String(20))

    role = db.Column(db.String(20), default="student", nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_active = db.Column(db.Boolean, default=True)

    is_verified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Student {self.email} - {self.role}>"

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "role": self.role
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(50), unique=True, nullable=False)

    description = db.Column(db.String(200))

    icon = db.Column(db.String(50), default="food")

    display_order = db.Column(db.Integer, default=0)

    is_active = db.Column(db.Boolean, default=True)

    items = db.relationship("MenuItem", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<Category {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon
        }


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text)

    price = db.Column(db.Float, nullable=False)

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    image_url = db.Column(db.String(200))

    is_available = db.Column(db.Boolean, default=True)

    preparation_time = db.Column(db.Integer, default=15)

    calories = db.Column(db.Integer)

    is_vegetarian = db.Column(db.Boolean, default=False)

    is_vegan = db.Column(db.Boolean, default=False)

    is_gluten_free = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship("OrderItem", backref="menu_item", lazy="dynamic")

    def __repr__(self):
        return f"<MenuItem {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category.name if self.category else None,
            "image_url": self.image_url,
            "preparation_time": self.preparation_time,
            "calories": self.calories,
            "is_vegetarian": self.is_vegetarian,
            "is_vegan": self.is_vegan,
            "is_gluten_free": self.is_gluten_free
        }


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)

    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False
    )

    status = db.Column(db.String(20), default="pending", index=True)

    total_amount = db.Column(db.Float, nullable=False)

    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    estimated_ready_time = db.Column(db.DateTime)

    items = db.relationship(
        "OrderItem",
        backref="order",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Order {self.order_number}>"

    def to_dict(self):
        return {
            "id": self.id,
            "order_number": self.order_number,
            "student": self.student.to_dict() if self.student else None,
            "status": self.status,
            "total_amount": self.total_amount,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "estimated_ready_time": self.estimated_ready_time.isoformat()
            if self.estimated_ready_time else None
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    menu_item_id = db.Column(
        db.Integer,
        db.ForeignKey("menu_items.id"),
        nullable=False
    )

    quantity = db.Column(db.Integer, nullable=False, default=1)

    unit_price = db.Column(db.Float, nullable=False)

    subtotal = db.Column(db.Float, nullable=False)

    special_instructions = db.Column(db.Text)

    def __repr__(self):
        return f"<OrderItem {self.id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "menu_item": self.menu_item.to_dict() if self.menu_item else None,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.subtotal,
            "special_instructions": self.special_instructions
        }


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    rating = db.Column(db.Integer, nullable=False)

    comment = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship(
        "Order",
        backref=db.backref("feedback", uselist=False)
    )

    def __repr__(self):
        return f"<Feedback {self.id}>"