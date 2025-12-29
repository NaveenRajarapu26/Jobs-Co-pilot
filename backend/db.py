
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    # By now, app.config["SQLALCHEMY_DATABASE_URI"] must already be set in app.py
    db.init_app(app)
    migrate.init_app(app, db)
