"""Database seed utilities."""

import os

from smartcare.extensions import db
from smartcare.models.department import Department
from smartcare.models.medicine import Medicine, MedicineInventory
from smartcare.models.user import RoleEnum, User

DEFAULT_DEPARTMENTS = [
    ("General Medicine", "bi-heart-pulse"),
    ("Cardiology", "bi-activity"),
    ("Orthopedics", "bi-bandaid"),
    ("Pediatrics", "bi-emoji-smile"),
    ("Dermatology", "bi-droplet"),
    ("Neurology", "bi-lightning"),
]

DEFAULT_MEDICINES = [
    ("Paracetamol 500mg", "Analgesic", "Generic Pharma", 2.50, 200),
    ("Amoxicillin 250mg", "Antibiotic", "Generic Pharma", 5.00, 150),
    ("Cetirizine 10mg", "Antihistamine", "Generic Pharma", 1.50, 100),
    ("Ibuprofen 400mg", "Analgesic", "Generic Pharma", 3.00, 150),
    ("Omeprazole 20mg", "Antacid", "Generic Pharma", 4.00, 100),
]


def run_seed():
    _seed_admin()
    _seed_departments()
    _seed_medicines()
    db.session.commit()


def _seed_admin():
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@smartcarex.com")
    if User.query.filter_by(email=admin_email).first():
        return

    admin = User(
        full_name="SmartCare X Admin",
        email=admin_email,
        role=RoleEnum.ADMIN,
        is_email_verified=True,
        is_active=True,
    )
    admin.set_password(os.environ.get("SEED_ADMIN_PASSWORD", "smartcarex@7777"))
    db.session.add(admin)


def _seed_departments():
    for name, icon in DEFAULT_DEPARTMENTS:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name, icon=icon))


def _seed_medicines():
    for name, category, manufacturer, price, stock in DEFAULT_MEDICINES:
        medicine = Medicine.query.filter_by(name=name).first()
        if medicine:
            continue
        medicine = Medicine(name=name, category=category, manufacturer=manufacturer, unit_price=price)
        db.session.add(medicine)
        db.session.flush()
        db.session.add(MedicineInventory(medicine_id=medicine.id, quantity_in_stock=stock, reorder_level=20))