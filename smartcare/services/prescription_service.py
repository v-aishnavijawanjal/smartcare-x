from smartcare.extensions import db
from smartcare.models.prescription import Prescription, PrescriptionItem
from smartcare.services.inventory_service import InsufficientStockError, deduct_stock


def create_prescription(appointment, doctor_id, patient_id, diagnosis, notes, items):
    """Create a prescription and update inventory."""
    prescription = Prescription(
        appointment_id=appointment.id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        diagnosis=diagnosis,
        notes=notes,
    )
    db.session.add(prescription)
    db.session.flush()  # Generate prescription ID before adding items.

    for item in items:
        prescription.items.append(
            PrescriptionItem(
                medicine_id=item["medicine_id"],
                dosage=item.get("dosage"),
                frequency=item.get("frequency"),
                duration_days=item.get("duration_days", 1),
            )
        )
        try:
            deduct_stock(item["medicine_id"], item.get("quantity_to_deduct", 1))
        except InsufficientStockError:
            db.session.rollback()
            raise

    db.session.commit()
    return prescription


def get_patient_prescription_history(patient_id):
    return (
        Prescription.query.filter_by(patient_id=patient_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )