"""python -m courseflow 的入口."""
import sys

if __package__ in (None, ""):  # 被直接运行(比如编辑器里点"运行文件")时,给个友好提示
    sys.exit(
        "请从项目根目录用  python -m courseflow  来运行(例如:python -m courseflow demo)\n"
        "详见 README 的'怎么运行'一节."
    )

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
