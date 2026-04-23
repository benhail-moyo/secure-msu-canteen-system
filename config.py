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