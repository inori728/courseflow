# CourseFlow for DeepSeek Harness 0.1.1

CourseFlow 的 Windows x64 插件包。桌面版和插件在同一个 CourseFlow 仓库维护，各自提供下载包。插件使用 DeepSeek Harness 桌面版和随包附带的 CourseFlow 运行环境。

## 在聊天里用命令调课

首次试跑时，在侧栏「导入」选择解压目录里的 `插件示例课表.yaml`。这份虚构示例可直接导入。依次点击「读取课表」「预览导入」「确认导入」，再在 Harness 的聊天输入框输入下面的命令。

```text
/courseflow 把第7周周二的体育课调到周五第4大节，地点不变
```

1. 右侧栏显示匹配到的课次。有多节同名课时，可以选一节或勾选多节。
2. 校对课程、原时间、新时间、地点和冲突提示。上面命令里的「第 4 大节」对应第 7–8 小节。
3. 点击「确认调课」写回当前课表。调错时点「撤销上一步」，即可恢复这次保存前的课表。

在输入框开头选中 `@CourseFlow` 候选，可自动带入 `/courseflow`。使用普通对话时，执行取决于 Harness 当前模型是否调用 CourseFlow 工具。

## 本版功能

- 点击聊天输入框下方的日历图标，打开或收起右侧课表。可查看今天和指定周课程，设置当前周次后按课表时区更新。
- 在侧栏或通过 `/courseflow` 查课、导入、调课、组队和导出。修改课表前先校对并确认。
- 根据课表和忙闲卡查询共同空闲，点击绿色区域把活动写入自己的课表，也能导出会议日历。
- 导出电脑或手机壁纸时可选内置背景或本地图片，侧栏随选择预览背景。也可导出 YAML、ICS、PDF 和挂图。
- 截图识别和通知解析共用多模态接口配置，使用前在侧栏设置中完成自检。

## 安装

1. 安装 Windows x64 版 DeepSeek Harness，至少打开一次，让它生成桌面配置。插件清单要求 `>=0.2.2-rc.3 <0.3.0`，本机验收使用 `0.2.2-rc.3`。
2. 下载 `CourseFlow-Harness-0.1.1-windows-x64.zip`，可用 `Get-FileHash -Algorithm SHA256` 与随附的 `SHA256SUMS.txt` 核对。将整个 ZIP 解压到准备长期存放插件的目录。
3. 退出 DeepSeek Harness，在解压后的 `CourseFlow-Harness` 目录打开 PowerShell。把下面的路径替换为你电脑上的 Harness 程序路径，再运行命令。

   ```powershell
   .\Start-CourseFlow-Harness.ps1 -InstallDesktop -HarnessExe "<Harness 安装目录>\DeepSeek Harness.exe"
   ```

4. 重新打开 DeepSeek Harness，在「插件 → 已安装」查看「CourseFlow 课表」，用聊天输入框下方的日历图标打开侧栏。首次使用时在「导入」选课表。插件通过目录链接加载，安装后请保留完整的解压目录。

## 与 CourseFlow 桌面版联动

单独使用插件时，初始课表为空，数据保存在解压目录的 `data` 下。发布包只含运行文件、使用说明、许可证和虚构示例。

如果也使用 CourseFlow 桌面版，可以在安装命令中加 `-DataDir`，传入桌面版正在使用的数据目录。桌面便携版通常用 `CourseFlow.exe` 同目录的 `data`。

```powershell
.\Start-CourseFlow-Harness.ps1 -InstallDesktop -HarnessExe "<Harness 安装目录>\DeepSeek Harness.exe" -DataDir "<CourseFlow 桌面版数据目录>"
```

两边读取同一个目录里的课表和多模态接口配置。桌面端保存后，可在 Harness 侧栏点「刷新课表」。插件保存后，使用已发布的桌面版 `v1.0.0` 时，可通过「打开课表」重新打开同一份课表。

## 验证范围

插件包已在本机的独立空白数据目录验证示例导入、命令调课、撤销和导出。真实多模态接口、Harness 模型通过普通对话调用插件工具，以及另一台 Windows 电脑上的完整流程仍待验收。
