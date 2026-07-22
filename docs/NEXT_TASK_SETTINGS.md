# NEXT_TASK_SETTINGS.md — v0.6 Settings 任务

## 目标

实现墨灵 App 的设置能力，让用户可以调整：
- AI 回复字体大小
- AI 回复字体
- 纸张背景
- 墨色
- 动画速度
- 残影强度
- 调试信息显示开关

第一版只做本地设置，不做账号，不做云同步。

## 需求优先级

### P0 必做

1. 增加设置入口
- 在主页面底部或右上角增加“设置”入口
- 不要破坏笔记本氛围
- 可以是一个小的文字按钮或齿轮图标

2. 设置面板
- 使用 Compose ModalBottomSheet 或独立 SettingsScreen
- 第一版推荐 ModalBottomSheet，轻量

3. 字号设置
- 小 / 中 / 大 / 超大
- 默认：大
- 影响 InkReplyOverlay 的 AI 回复字号
- 也可以影响 recognizedText 调试行字号，但不是必须

建议映射：
- 小：22sp
- 中：28sp
- 大：36sp
- 超大：44sp

4. 背景设置
- 羊皮纸
- 米白纸
- 纯白调试纸
- 暗色纸

设置应影响 PaperCanvas / NotebookPageScreen 的纸张背景。

5. 调试信息开关
- 开：显示 识别(mlkit)：xxx
- 关：隐藏识别调试行
- 默认：开，当前开发阶段需要

6. 设置持久化
- 使用 DataStore Preferences
- 保存用户选择
- App 重启后仍保留设置

### P1 可做

7. 墨色设置
- 墨黑
- 深蓝黑
- 棕黑

影响用户笔迹和 AI 回复墨迹颜色。

8. 动画速度
- 慢 / 中 / 快
- 影响 InkReplyOverlay 每字出现间隔

9. 残影强度
- 无
- 淡
- 中

影响回复淡出后的 alpha。

### P2 暂不做

- 字体文件选择器
- 用户导入字体
- 云同步设置
- 多主题市场
- 账户系统
- 订阅支付

## 技术建议

新增文件：
- app/src/main/java/com/moling/livingnotebook/settings/MolingSettings.kt
- app/src/main/java/com/moling/livingnotebook/settings/SettingsRepository.kt
- app/src/main/java/com/moling/livingnotebook/ui/components/SettingsSheet.kt

可能修改：
- app/build.gradle.kts：添加 DataStore Preferences 依赖
- NotebookViewModel.kt：持有 settings state
- NotebookPageScreen.kt：传 settings 给 PaperCanvas / InkReplyOverlay / 调试行
- PaperCanvas.kt：接受背景和墨色参数
- InkReplyOverlay.kt：接受 fontSize、inkColor、animationSpeed、residualAlpha 参数

DataStore 依赖：
implementation("androidx.datastore:datastore-preferences:1.1.1")

## UI 风格

设置不能像普通系统表单太突兀。
要保持“笔记本 / 墨 / 纸”的氛围。

文案建议：
- 字号：墨字大小
- 背景：纸色
- 墨色：墨色
- 动画速度：显字速度
- 残影：残墨
- 调试信息：识别痕迹

## 验收标准

1. App 有设置入口。
2. 可以打开设置面板。
3. 调整字号后，AI 回复明显变大/变小。
4. 调整背景后，纸面背景改变。
5. 调试信息开关生效。
6. 设置重启后保留。
7. 不影响：显字速度
- 残影：残墨
- 调试信息：识别痕迹

## 验收标准

1. App 有设置入口。
2. 可以打开设置面板。
3. 调整字号后，AI 回复手写、识别、吸墨、AI 回复。
8. 不改 OpenAI API Key 逻辑。
9. 不把界面变成聊天 App。