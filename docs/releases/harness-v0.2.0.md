# CourseFlow for DeepSeek Harness 0.2.0

迭代11：新增小组日程卡和待办，优化了用户体验

## 本次更新

- 新增待办清单，可添加截止日期、勾选完成，或通过「留出时间」把任务排到个人课表。
- 组队可逐份追加忙闲卡和 CF1 短码。选绿色空闲格可打开小组日程，也可切换为添加个人课表活动。切换栏目时保留本次组队结果和日程草稿。
- 输入一段描述即可拟定小组事项、议程和分工。核对后应用，可预览并导出日程卡。
- 查课支持日卡片、周网格和按课名查找下一次实际课次。电脑和手机壁纸可在确认导出前预览合成效果。
- 输入 `/courseflow 帮助` 查看查课、待办、组队、日程、确认和撤销的命令。AI 拟稿使用插件内已自检的多模态接口配置。

## Windows 安装与升级

1. 安装并打开一次兼容的 Windows x64 版 DeepSeek Harness。插件支持 `>=0.2.2-rc.3 <0.3.0`。
2. 下载 `CourseFlow-Harness-0.2.0-windows-x64.zip`，用同页的 `SHA256SUMS.txt` 核对文件。将 ZIP 完整解压到准备长期保留的目录。
3. 退出 Harness，在解压后的 `CourseFlow-Harness` 目录打开 PowerShell，把命令中的安装位置换成实际路径再运行。

   ```powershell
   .\Start-CourseFlow-Harness.ps1 -InstallDesktop -HarnessExe "<Harness 安装目录>\DeepSeek Harness.exe"
   ```

4. 重新打开 Harness，在「插件 → 已安装」查看「CourseFlow 课表」，通过聊天框下方的日历图标打开侧栏。首次试用可导入随包提供的 `插件示例课表.yaml`。

插件通过目录链接加载，安装后请保留完整的解压目录。升级或继续与桌面版共用课表时，在安装命令后加 `-DataDir "<原来使用的 CourseFlow 数据目录>"`。独立插件的默认数据目录是解压目录里的 `data`。
