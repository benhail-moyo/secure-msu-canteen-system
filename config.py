import os


class Config:
    """Base configuration class."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "msu-canteen-secret-key-2026")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///canteen.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ITEMS_PER_PAGE = 12
    MAX_ORDER_ITEMS = 20

    ADMIN_KEY = os.environ.get("ADMIN_KEY", "MSUadminSpecial")
    MANAGER_KEY = os.environ.get("MANAGER_KEY", "MSUmanagerSpecial")
    STAFF_KEY = os.environ.get("STAFF_KEY", "MSUstaffSpecial")

    # Email configuration for 2FA
    # Port 465 uses implicit SSL (MAIL_USE_SSL=True).
    # Port 587 uses STARTTLS (MAIL_USE_TLS=True). Never mix the two.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "False").lower() == "true"   # port 465 = SSL
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"  # port 587 = TLS
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "benhailelpadrey@gmail.com")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "tnqa hesa livx bjxu")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}