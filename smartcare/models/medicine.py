from datetime import datetime

from smartcare.extensions import db


class Medicine(db.Model):
    __tablename__ = "medicines"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False, index=True)
    category = db.Column(db.String(80))
    manufacturer = db.Column(db.String(120))
    unit_price = db.Column(db.Numeric(10, 2), default=0, nullable=False)

    inventory = db.relationship("MedicineInventory", back_populates="medicine", uselist=False, cascade="all, delete-orphan")
    prescription_items = db.relationship("PrescriptionItem", back_populates="medicine")

    def __repr__(self):
        return f"<Medicine {self.name}>"


class MedicineInventory(db.Model):
    __tablename__ = "medicine_inventory"

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), unique=True, nullable=False)

    quantity_in_stock = db.Column(db.Integer, default=0, nullable=False)
    reorder_level = db.Column(db.Integer, default=10, nullable=False)
    last_restocked_at = db.Column(db.DateTime, default=datetime.utcnow)

    medicine = db.relationship("Medicine", back_populates="inventory")

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.reorder_level

    def __repr__(self):
        return f"<Inventory {self.medicine_id} qty={self.quantity_in_stock}>"
