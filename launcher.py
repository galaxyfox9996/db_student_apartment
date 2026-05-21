import ctypes
import os


APP_TITLE = "学生公寓管理系统启动器"


def show_message(text, title=APP_TITLE, flags=0):
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def launch_app(mode):
    os.environ["DB_MODE"] = mode
    os.environ.setdefault("APP_DEBUG", "0")

    from app import start_app

    start_app()


def choose_mode():
    guide_text = (
        "点击“是”：启动 MySQL 课程设计版\n"
        "点击“否”：启动 SQLite 便携演示版\n"
        "点击“取消”：退出\n\n"
        "建议：答辩展示用 MySQL，发给别人运行用 SQLite。"
    )

    result = show_message(guide_text, flags=0x3 | 0x40)

    if result == 6:
        launch_app("mysql")
    elif result == 7:
        launch_app("sqlite")


if __name__ == "__main__":
    choose_mode()
