from flask import Flask

import db
from flask_cors import CORS
from config import Config
from errors import register_error_handlers
from routes.health import health_bp
from routes.auth import auth_bp
from routes.students import students_bp
from routes.leaves import leaves_bp
from routes.attendance import attendance_bp
from routes.notifications import notifications_bp
from routes.class_attendance import class_attendance_bp
from routes.faculty import faculty_bp
from routes.analytics import analytics_bp
from routes.reports import reports_bp
from routes.maintenance import maintenance_bp
from routes.holidays import holidays_bp


def create_app():
    Config.validate()

    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ]}})

    db.init_app(app)
    register_error_handlers(app)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(students_bp, url_prefix="/api/students")
    app.register_blueprint(leaves_bp, url_prefix="/api/leaves")
    app.register_blueprint(attendance_bp, url_prefix="/api/attendance")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(faculty_bp, url_prefix="/api/faculty")
    app.register_blueprint(class_attendance_bp, url_prefix="/api/class-attendance")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(maintenance_bp, url_prefix="/api/maintenance")
    app.register_blueprint(holidays_bp, url_prefix="/api/holidays")

    return app


app = create_app()

if __name__ == "__main__":
    # debug=True is for development only. Turn it off in production.
    app.run(host="127.0.0.1", port=5000, debug=True)