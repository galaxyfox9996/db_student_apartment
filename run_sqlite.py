import os

os.environ["DB_MODE"] = "sqlite"

from app import start_app


if __name__ == "__main__":
    start_app()
