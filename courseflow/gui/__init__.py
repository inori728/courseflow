"""Desktop UI; all timetable operations go through the service layer."""


def main(source=None):
    try:
        from .app import CourseFlowApp
    except ImportError as exc:
        raise ValueError("图形界面需要 CustomTkinter, 请安装 requirements.txt 中的依赖.") from exc
    app = CourseFlowApp(source)
    app.mainloop()
