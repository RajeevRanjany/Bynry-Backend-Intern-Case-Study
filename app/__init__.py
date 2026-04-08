from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')

    db.init_app(app)

    # Register blueprints
    from .routes.products import products_bp
    from .routes.alerts import alerts_bp

    app.register_blueprint(products_bp)
    app.register_blueprint(alerts_bp)

    return app
