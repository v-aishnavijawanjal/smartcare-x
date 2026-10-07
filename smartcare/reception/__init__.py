from flask import Blueprint

reception_bp = Blueprint("reception", __name__, template_folder="../templates/reception")

from smartcare.reception import routes  # noqa: E402,F401
