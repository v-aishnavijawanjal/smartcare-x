import os

from flask import Flask, render_template

from config import config_by_name
from smartcare.extensions import csrf, db, login_manager, mail, migrate


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True)
    config_class = config_by_name[config_name]
    config_class.validate()
    app.config.from_object(config_class)

    _ensure_instance_and_upload_dirs(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)
    _register_cli_commands(app)
    _init_scheduler(app)

    return app


def _ensure_instance_and_upload_dirs(app):
    os.makedirs(app.instance_path, exist_ok=True)
    upload_root = app.config["UPLOAD_FOLDER"]
    os.makedirs(os.path.join(upload_root, app.config["PROFILE_PHOTO_SUBDIR"]), exist_ok=True)
    os.makedirs(os.path.join(upload_root, app.config["LAB_REPORT_SUBDIR"]), exist_ok=True)


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        from smartcare.models.user import User

        return User.query.get(int(user_id))


def _register_blueprints(app):
    from smartcare.admin import admin_bp
    from smartcare.auth import auth_bp
    from smartcare.doctor import doctor_bp
    from smartcare.main import main_bp
    from smartcare.patient import patient_bp
    from smartcare.reception import reception_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(patient_bp, url_prefix="/patient")
    app.register_blueprint(doctor_bp, url_prefix="/doctor")
    app.register_blueprint(reception_bp, url_prefix="/reception")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/404.html"), 403


def _register_context_processors(app):
    @app.context_processor
    def inject_globals():
        from datetime import datetime

        return {"current_year": datetime.utcnow().year, "app_name": "SmartCare X"}


def _register_cli_commands(app):
    @app.cli.command("seed-db")
    def seed_db():
        """Seed the database."""
        from smartcare.services.seed_service import run_seed

        run_seed()
        print("Database seeded successfully.")


def _init_scheduler(app):
    """Initialize the background scheduler."""
    if app.config.get("TESTING"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    from smartcare.services.scheduler_service import init_scheduler

    init_scheduler(app)