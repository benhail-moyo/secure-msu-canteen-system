#!/usr/bin/env python
"""Add a test student account for password reset testing."""

import sys
sys.path.insert(0, '/users/smong/documents/new/secure-msu-canteen-system')

from app import create_app, db
from models import Student
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Check if test student already exists
    existing = Student.query.filter_by(student_id="TEST001").first()
    
    if existing:
        print(f"Test student already exists: {existing.email}")
    else:
        # Create test student
        test_student = Student(
            student_id="TEST001",
            name="Test Student",
            email="test@msu.edu",
            password_hash=generate_password_hash("OldPassword123!"),
            department="Computer Science",
            phone="0712345678",
            role="student",
            is_verified=True
        )
        
        db.session.add(test_student)
        db.session.commit()
        
        print("✓ Test student created successfully!")
        print(f"  Student ID: TEST001")
        print(f"  Email: test@msu.edu")
        print(f"  Phone: 0712345678")
        print(f"  Current Password: OldPassword123!")
        print("\nUse these credentials to test the password reset flow.")
