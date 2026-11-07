# 参与 CourseFlow

欢迎报告实际课表格式、导入错误和排版问题。提交示例前请删除姓名、学号、教师信息、真实地点和 API Key；用虚构课程即可复现。

## 开发环境

需要 Python 3.9+。Windows 可复用已有 Anaconda，按 README 的 `scripts/bootstrap.ps1` 创建项目独立环境，不要向 base 安装项目依赖。普通开发只需 `python -m pip install -e .`；文字 PDF 可加 `[documents]`，本地打包可加 `[documents,build]`。

```bash
python -m unittest discover -s tests -v
python scripts/check_source.py
python -m courseflow --help
```

自动化测试不需要 API Key 或联网。Node 可选，仅用于点格页与 Python 忙闲卡协议互通测试。PDF 可选依赖未装时会跳过 PDF 结构检查，正常测试结果中会明确显示。

## 改动约定

- 先给出具体触发条件、预期和实际结果。新功能先讨论范围，再修改代码。
- CLI / GUI 共享 `service.py`，周次只由 `weeks.py` 解析，实际课程由 `schedule.py` 展开。
- AI 只能产生可校对草稿；保存、时间换算和冲突检查由本地代码控制。
- 保留旧源文件兼容性和未知字段；涉及 `skip` / `changes` 时验证实际发生的课次，不能只检查文件生成。
- 代码和配置中的标点用英文半角。解析功能字符用 Unicode 转义保留，`parsing._EDGE` 字符表例外；中文内容文档和示例不受此限。
- 不提交 API 配置、个人课表、草稿、忙闲卡、环境、缓存和构建目录。公开文件不写本机用户目录或开发工具私有路径。
- 测试覆盖真实边界和已有失败场景；不为低影响的外观修改堆叠与实现完全相同的测试。

本项目维护者约定：提交前先提供本次所有文件、完整 diff、新文件全文、二进制预览、测试结果和拟定说明，经审查明确放行后再暂存、提交或上传。标题采用 `迭代 N：新增 / 优化 / 修复...` 的简短格式，不制造无意义提交。

GitHub 与 Gitee 以本地仓库为唯一内容源；批准后由维护者正常双推并核对指针。不要在平台网页直接改代码，也不要高频批量操作、刷量或绕过平台验证。

## Windows 本地构建

```powershell
.\scripts\bootstrap.ps1 -AnacondaPython "<Anaconda安装目录>\python.exe" -Build
.\.dev\venv\Scripts\python.exe scripts\build_release.py
```

构建使用项目 `.dev` 保存缓存和临时文件，输出在 `dist`。它不提交、不打 tag、不上传。构建目录应位于目标工作盘，尽量使用 D 盘；如果软件必须写 C 盘或从 D 盘还需指回 C 盘，则直接使用 C 盘。

已有便携版正在使用时，可加 `--output-dir dist/preview` 构建到另一个项目内目录，保留旧程序和数据。不要在使用中的目录内覆盖构建。

本地包是 Windows 目录包，保留整个目录。构建清单记录依赖版本、组件体积和 SHA-256。分发前须检查第三方许可证、实际启动和资源完整性；不同操作系统需在相应系统重新构建。当前仓库 CI 只自动运行测试，不发布 exe 或点格页。

Anaconda 派生环境的运行库通过构建进程自己的搜索路径和 `--add-binary` 明确收集，避免依赖本机全局 PATH。相关机制见 [PyInstaller 官方文档](https://www.pyinstaller.org/en/stable/feature-notes.html#ctypes-dependencies)。构建后应在不带 Anaconda 路径的进程环境中运行 `CourseFlow.exe --self-check 报告.json`，验证窗口、网络运行库、Excel、PDF、绘图与组队资源。

贡献内容沿用项目 [MIT](LICENSE) 许可。引用第三方代码或素材时保留来源和许可证。
