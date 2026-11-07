# 第三方组件

CourseFlow 自有代码使用 MIT。以下组件由各自许可证覆盖；项目没有内置 AI 模型或将第三方课表图片作为公开素材。

| 组件 | 用途 | 当前本地构建版本 / 许可 |
|---|---|---|
| CPython | Python 运行时 | 3.14.6 / PSF 与随附历史许可 |
| Tcl / Tk | 桌面窗口 | 8.6.15 / 包内 license.terms |
| OpenSSL、libffi、libmpdec、libexpat、zlib、bzip2、xz、zstd 与 Microsoft 运行库 | 标准库网络、数值、压缩、字符与系统支持 | 按实际打入的二进制匹配安装包，完整许可见 `licenses/runtime-*` |
| Pillow | 图片与图像 PDF | 13.0.0 / MIT-CMU；内含图像库许可随组件保留 |
| openpyxl | Excel 解析 | 3.1.5 / MIT |
| et_xmlfile | Excel XML 支持 | 2.0.0 / MIT |
| PyYAML | 课表读写 | 6.0.3 / MIT |
| CustomTkinter | GUI 控件 | 6.0.0 / CC0-1.0，以该版本包内 LICENSE 为准 |
| darkdetect | 系统主题检测 | 0.8.0 / BSD-3-Clause |
| packaging | 版本信息 | 26.3 / Apache-2.0 或 BSD-2-Clause |
| pypdf | 可选文字 PDF 解析 | 7.0.0 / BSD-3-Clause |
| PyInstaller | 构建工具与启动程序 | 6.22.3 / GPL，包含包内说明的分发例外 |
| holiday-cn | 2026 节假日数据 | MIT，完整来源与许可见 `courseflow/data/README.md` |

表中版本是本次便携包使用的版本，不是源码安装的锁定版本。源码安装会按 Python 版本选择满足依赖约束的兼容包；实际目录包记录在构建清单中。

`scripts/build_release.py` 会复制已安装依赖的许可证及运行时许可到包内 `licenses`，并随包附上本文件。图标和背景为项目代码生成；中文字体运行时读取系统字体，未打包分发 Windows 字体文件。

分发时需要保留整个目录包及其中许可。实际发布状态和可下载文件以 Releases 页面为准。
