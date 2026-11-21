# CourseFlow for DeepSeek Harness 0.3.0

迭代 12 新增课表助手，统一导航与待办。

## 本次更新

- 侧栏导航调整为「课表」「助手」「常用功能」。输入 `/courseflow 助手` 可打开助手，输入 `/courseflow 帮助` 可查看完整使用指引。
- 助手可切换聊天和课表操作。可以请它查指定周或下周的整周课表、处理附件、查共同空档，并接着准备小组日程或导出壁纸。
- 用自己的话给已保存的课表新增一堂课或一次活动。冲突时可选备选空档，核对后确认保存。再次打开原回复可直接查看保存记录。
- 待办可随桌面版共用。两端使用同一数据目录时，确认保存的安排可在同一份课表中查看。

## Windows 安装与升级

1. 安装并打开一次 Windows x64 版 DeepSeek Harness。插件支持 `>=0.2.2-rc.3 <0.3.0`，本轮已在 `0.2.2-rc.5` 验收。
2. 下载 `CourseFlow-Harness-0.3.0-windows-x64.zip`，用同页的 `SHA256SUMS.txt` 校验。将 ZIP 完整解压到准备长期保留的目录。
3. 退出 Harness，在解压后的 `CourseFlow-Harness` 目录打开 PowerShell。把占位路径换成 Harness 的安装位置，再运行下面的命令。

   ```powershell
   .\Start-CourseFlow-Harness.ps1 -InstallDesktop -HarnessExe "<Harness 安装目录>\DeepSeek Harness.exe"
   ```

4. 重开 Harness，通过聊天框下方的日历图标打开课表侧栏。首次试用可导入随包提供的 `插件示例课表.yaml`。打开助手即可查看本地指引。要用自由聊天、截图识别或 AI 拟稿，请设置兼容的多模态 AI 接口并完成自检。

插件通过目录链接加载，安装后请保留解压目录。升级或与桌面版共用已有课表和待办时，给安装命令加上 `-DataDir "<原来使用的 CourseFlow 数据目录>"`。独立使用时，默认数据目录是解压目录里的 `data`。更多操作见随包附带的《使用说明》。
