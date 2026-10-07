from smartcare.models.appointment import Appointment
from smartcare.models.doctor import Doctor
from smartcare.models.medicine import Medicine
from smartcare.models.patient import Patient
from smartcare.models.user import User


def search_patients(term, limit=25):
    like = f"%{term}%"
    return (
        Patient.query.join(User)
        .filter(db_or(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
        .limit(limit)
        .all()
    )


def search_doctors(term, limit=25):
    like = f"%{term}%"
    return (
        Doctor.query.join(User)
        .filter(
            db_or(
                User.full_name.ilike(like),
                Doctor.specialization.ilike(like),
                Doctor.qualification.ilike(like),
            )
        )
        .limit(limit)
        .all()
    )


def search_medicines(term, limit=25):
    like = f"%{term}%"
    return Medicine.query.filter(
        db_or(Medicine.name.ilike(like), Medicine.category.ilike(like), Medicine.manufacturer.ilike(like))
    ).limit(limit).all()


def search_appointments(term, limit=25):
    """Search appointments by patient, doctor, or reason."""
    like = f"%{term}%"
    patient_user = db_alias(User)
    doctor_user = db_alias(User)

    return (
        Appointment.query.join(Patient, Appointment.patient_id == Patient.id)
        .join(patient_user, Patient.user_id == patient_user.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(doctor_user, Doctor.user_id == doctor_user.id)
        .filter(
            db_or(
                patient_user.full_name.ilike(like),
                doctor_user.full_name.ilike(like),
                Appointment.reason.ilike(like),
            )
        )
        .limit(limit)
        .all()
    )


def global_search(term, limit_per_entity=10):
    """Search across all supported entities."""
    return {
        "patients": search_patients(term, limit_per_entity),
        "doctors": search_doctors(term, limit_per_entity),
        "medicines": search_medicines(term, limit_per_entity),
        "appointments": search_appointments(term, limit_per_entity),
    }


def db_or(*args):
    from sqlalchemy import or_

    return or_(*args)


def db_alias(model):
    from sqlalchemy.orm import aliased

    return aliased(model)