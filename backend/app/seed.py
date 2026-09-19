"""Seed the database with master data and demo login users.

Purchase requests, orders and deliveries are intentionally not seeded —
create them through the UI.

Run with: venv\\Scripts\\python -m app.seed
"""
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Category, Department, User, UserRole, Vendor

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    if db.query(User).count() > 0:
        print("Database already seeded. Skipping.")
    else:
        departments = {
            name: Department(name=name)
            for name in ["Operations", "HSSE", "IT", "Administration", "Marine", "Finance"]
        }
        db.add_all(departments.values())

        categories = {
            name: Category(name=name)
            for name in [
                "Spare Parts",
                "Safety Equipment",
                "IT Hardware",
                "Office Furniture",
                "Catering Services",
                "Professional Services",
            ]
        }
        db.add_all(categories.values())

        vendor_catalogue = [
            ("Gulf Marine Supplies LLC", "sales@gulfmarine.ae", ["Spare Parts", "Safety Equipment"]),
            ("SafetyFirst Equipment Trading", "info@safetyfirst.ae", ["Safety Equipment"]),
            ("TechZone Computers", "orders@techzone.ae", ["IT Hardware"]),
            ("Al Futtaim Office Solutions", "contact@affice.ae", ["Office Furniture", "IT Hardware"]),
            ("Prime Catering Co.", "events@primecatering.ae", ["Catering Services"]),
            ("Gulf Advisory Partners", "engage@gulfadvisory.ae", ["Professional Services"]),
        ]
        for name, email, category_names in vendor_catalogue:
            vendor = Vendor(name=name, contact_email=email, contact_phone="+971-4-1234567")
            vendor.categories = [categories[c] for c in category_names]
            db.add(vendor)
        db.flush()

        db.add_all(
            [
                User(
                    name="Admin User",
                    email="admin@procureflow.com",
                    password_hash=hash_password("Admin@123"),
                    role=UserRole.ADMIN,
                    department_id=departments["Administration"].id,
                ),
                User(
                    name="Rohan Sharma",
                    email="rohan.sharma@procureflow.com",
                    password_hash=hash_password("Requester@123"),
                    role=UserRole.REQUESTER,
                    department_id=departments["Operations"].id,
                ),
                User(
                    name="Priya Nair",
                    email="priya.nair@procureflow.com",
                    password_hash=hash_password("Requester@123"),
                    role=UserRole.REQUESTER,
                    department_id=departments["HSSE"].id,
                ),
                User(
                    name="Sameer Khan",
                    email="sameer.khan@procureflow.com",
                    password_hash=hash_password("Approver@123"),
                    role=UserRole.APPROVER,
                    department_id=departments["IT"].id,
                ),
                User(
                    name="Amit Patel",
                    email="amit.patel@procureflow.com",
                    password_hash=hash_password("Approver@123"),
                    role=UserRole.APPROVER,
                    department_id=departments["Marine"].id,
                ),
            ]
        )

        db.commit()
        print("Database seeded successfully.")
        print("Login accounts (password shown next to each):")
        print("  Admin:     admin@procureflow.com / Admin@123")
        print("  Requester: rohan.sharma@procureflow.com / Requester@123")
        print("  Requester: priya.nair@procureflow.com / Requester@123")
        print("  Approver:  sameer.khan@procureflow.com / Approver@123")
        print("  Approver:  amit.patel@procureflow.com / Approver@123")
finally:
    db.close()
