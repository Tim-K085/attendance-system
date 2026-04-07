from flask import Flask
from .config import Config
from .extensions import db, migrate

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from . import models
    migrate.init_app(app, db)

    from .admin import admin_bp
    from .checkin import checkin_bp

    app.register_blueprint(admin_bp)
    app.register_blueprint(checkin_bp)

    return app