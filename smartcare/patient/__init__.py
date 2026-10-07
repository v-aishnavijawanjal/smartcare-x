from flask import Blueprint

patient_bp = Blueprint("patient", __name__, template_folder="../templates/patient")

from smartcare.patient import routes  # noqa: E402,F401
