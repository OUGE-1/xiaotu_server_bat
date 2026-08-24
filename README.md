# 🐰 小兔服务器启动器 · `server_bat.exe`

[![GitHub release](https://img.shields.io/github/v/release/OUGE-1/xiaotu_server_bat_exe?style=flat-square)](https://github.com/OUGE-1/xiaotu_server_bat_exe/releases)
[![GitHub license](https://img.shields.io/github/license/OUGE-1/xiaotu_server_bat_exe?style=flat-square)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/OUGE-1/xiaotu_server_bat_exe?style=flat-square)](https://github.com/OUGE-1/xiaotu_server_bat_exe/stargazers)

**一键启动你的 Minecraft 服务器，轻松开启联机功能！**

---

## 📖 项目简介

`server_bat.exe` 是一个图形化 Minecraft 服务器启动器，将复杂的命令行操作封装为简单的点击交互，让你无需记忆任何指令就能轻松管理服务器。

只需将服务器核心文件（如 `server.jar`）与程序放在同一目录，即可通过图形界面完成服务器的启动、管理、备份与联机等操作。

### ✨ 主要功能

- 🚀 **一键启动/停止/重启**服务器
- 📋 **实时日志**查看与控制台交互
- 💾 **一键备份与恢复**世界数据
- 🔌 **插件管理**（添加/删除插件）
- 👥 **玩家管理**（踢出/封禁/授予 OP）
- ⚡ **快速命令**预设与一键执行
- 🌐 **联机辅助**（配合 EnderLink 实现内网穿透）

---

## 📥 下载

### 方式一：GitHub Releases（推荐）

从 [Releases](https://github.com/OUGE-1/xiaotu_server_bat_exe/releases) 页面下载最新版本的 `server_bat.exe`。

### 方式二：备用网盘

如果 GitHub 访问较慢，可使用蓝奏云备用链接：

| 渠道 | 链接 |
|---|---|
| 蓝奏云 | https://wwapl.lanzout.com/b016kvs33e |
密码：1234
---

## 🚀 快速开始

### 1️⃣ 放置文件

将 `server_bat.exe` 与你的 **服务器核心文件**（例如 `server.jar`）放在 **同一个文件夹** 内。

```text
你的服务器文件夹/
├── server_bat.exe # 启动器主程序
├── server.jar # 你的服务端核心文件
├── server.properties # 服务器配置文件（自动生成）
├── world/ # 世界数据文件夹（自动生成）
├── plugins/ # 插件目录（自动生成）
├── backups/ # 备份目录（自动生成）
└── quick_commands.json # 快速命令配置文件（可选）
```

### 2️⃣ 启动程序

双击 `server_bat.exe` 运行，在图形界面中点击 **「启动」** 按钮即可开启服务器。

### 3️⃣ 管理服务器

- **控制台**：查看实时日志，输入命令与服务器交互
- **备份管理**：创建、恢复或删除备份
- **插件管理**：添加或删除插件
- **玩家管理**：踢出、封禁或给予 OP

---

## 🌐 联机辅助功能

本程序支持配合 **EnderLink**（原 Teft）联机平台，实现内网穿透/端口映射，方便你与好友远程联机。

### 使用步骤

1. **下载 EnderLink**：访问联机官网 [www.teft.cn](https://www.teft.cn) 下载最新版本。
   - 夸克网盘：https://pan.quark.cn/s/42b298c44e9c
   - 蓝奏云：https://liuyvetong.lanzoub.com/b00g45ca8h（密码：1234）
   - QQ 群：https://qm.qq.com/cgi-bin/qm/qr?k=-LlckSeA5LtOHyuUETMDjd91xAOO7v-2

2. **放置文件**：将下载的 EnderLink 解压到 **与 `server_bat.exe` 相同的目录** 下。

3. **路径检查**：确保 EnderLink 的目标文件夹路径正确，程序才能正常调用联机功能。

4. **启动联机**：打开 EnderLink，按照软件提示完成端口映射配置，即可生成联机地址分享给好友。

> ⚠️ **提示**：联机功能由 EnderLink 独立提供，如需帮助请查阅其官方文档或加入用户群。

---

## 📦 仓库文件说明

| 文件/目录 | 说明 |
|---|---|
| `server_bat.exe` | 主程序，图形化服务器管理工具 |
| `quick_commands.json` | 快速命令配置文件（可自定义） |
| `Plugins_xiaotu/` | 插件存放目录 |
| `路径.txt` | 路径信息记录文件 |

---

## 🖥️ 系统支持

- ✅ Windows 7 及以上版本
- ❌ 暂不支持 Linux / macOS

---

## 🔧 高级功能

### 快速命令配置

编辑 `quick_commands.json` 文件，可以自定义快捷按钮：

```json
{
    "重启": "restart",
    "保存": "save-all",
    "玩家列表": "list"
}
```
保存后重启程序，在界面中点击对应按钮即可一键发送命令。

### 服务器设置
点击菜单栏 「设置 → 服务器设置」，可以配置：


| 选项 | 说明 |
|---|---|
| Java 路径 | 指定 Java 安装路径（默认使用系统 PATH 中的 java） |
| JVM 参数 | 自定义内存分配等参数（如 -Xmx4G -Xms2G） |
| 自动重启 | 服务器崩溃后自动重启 |
| 最大备份数 | 保留的备份数量上限（默认 10 个） |

### 备份管理
程序会自动备份以下内容：

` world、world_nether、world_the_end ` 等世界文件夹

` server.properties、bukkit.yml、spigot.yml、paper.yml ` 等配置文件

# 在 「备份管理」 标签页中，你可以：

创建新备份

恢复选中的备份

删除旧备份

查看备份详情

## ❓ 常见问题

Q：启动时提示找不到 server.jar 怎么办？

确保 server_bat.exe 与你的服务端核心文件放在同一目录。如果文件名不是 server.jar，点击 「文件 → 选择服务端 JAR」 手动选择即可。

Q：服务器无法启动怎么办？

检查 Java 是否正确安装（命令行运行 java -version 测试）

检查 JVM 参数中的内存分配是否合理（不超过物理内存）

查看程序日志中的错误信息

Q：备份恢复后数据不对？

恢复备份前请 先停止服务器，否则可能导致数据不一致。程序会在恢复前自动检查服务器状态。

Q：联机功能无法使用？

确认已从 www.teft.cn 下载 EnderLink 并解压

确认目录路径中 不含中文或特殊字符

确认防火墙未拦截 EnderLink 的网络访问

Q：杀毒软件报毒？

本程序为开源项目，代码完全公开透明。报毒属于误报（因打包为 exe 且涉及进程操作），请添加信任或查看源码自行编译。

## 📥 获取项目

如果你想在本地修改源码或自行编译，请克隆源代码仓库：

```bash
git clone https://github.com/OUGE-1/xiaotu_server_bat.git
cd xiaotu_server_bat
```
> 💡 **只想开服，不想折腾？**  
> 直接前往 [Releases](https://github.com/OUGE-1/xiaotu_server_bat_exe/releases) 下载 `server_bat.exe` 即可使用，无需克隆仓库。
📝 从源码构建
源码仓库： [OUGE-1/xiaotu_server_bat](https://github.com/OUGE-1/xiaotu_server_bat) 
```bash
pip install psutil pyinstaller
pyinstaller --onefile --windowed --name server_bat a8.py
```
🤝 贡献与反馈
提交 Bug 或建议：[Issues](https://github.com/OUGE-1/xiaotu_server_bat/issues)

点个 ⭐ 是对项目最大的支持！
