"""Medicine inventory management."""

from datetime import datetime

from smartcare.extensions import db
from smartcare.models.medicine import Medicine, MedicineInventory


class InsufficientStockError(Exception):
    pass


def deduct_stock(medicine_id, quantity):
    inventory = MedicineInventory.query.filter_by(medicine_id=medicine_id).first()
    if inventory is None:
        raise InsufficientStockError("No inventory record found for this medicine.")

    # Update stock atomically to prevent overselling during concurrent requests.
    result = db.session.execute(
        db.update(MedicineInventory)
        .where(
            MedicineInventory.medicine_id == medicine_id,
            MedicineInventory.quantity_in_stock >= quantity,
        )
        .values(quantity_in_stock=MedicineInventory.quantity_in_stock - quantity)
    )

    if result.rowcount == 0:
        db.session.rollback()
        raise InsufficientStockError(
            f"Insufficient stock for {inventory.medicine.name}: "
            f"{inventory.quantity_in_stock} available, {quantity} requested."
        )

    db.session.commit()
    db.session.refresh(inventory)
    return inventory


def restock(medicine_id, quantity):
    inventory = MedicineInventory.query.filter_by(medicine_id=medicine_id).first()
    if inventory is None:
        inventory = MedicineInventory(medicine_id=medicine_id, quantity_in_stock=0)
        db.session.add(inventory)

    inventory.quantity_in_stock += quantity
    inventory.last_restocked_at = datetime.utcnow()
    db.session.commit()
    return inventory


def get_low_stock_items():
    return (
        MedicineInventory.query.join(Medicine)
        .filter(MedicineInventory.quantity_in_stock <= MedicineInventory.reorder_level)
        .order_by(MedicineInventory.quantity_in_stock.asc())
        .all()
    )