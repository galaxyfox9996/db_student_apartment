import os

os.environ["DB_MODE"] = "mysql"

from app import start_app


if __name__ == "__main__":
    start_app()
