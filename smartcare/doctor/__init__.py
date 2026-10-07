from flask import Blueprint

doctor_bp = Blueprint("doctor", __name__, template_folder="../templates/doctor")

from smartcare.doctor import routes  # noqa: E402,F401
