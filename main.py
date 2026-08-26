#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minecraft 服务器管理器 - PySide6 版本
功能源自 a8.py，使用 PySide6 重构
改进点：
- 合并 stderr 到 stdout，彻底解决日志重复问题
- 在服务器控制页面增加命令输入框
- 联机环境检测嵌入主窗口
- 从 GitHub 下载插件（读取 plugins.json）
- 从蓝奏云引导下载
- 本地安装插件
- 参数启动校验 (--run_plugin)
- 修复信号源删除错误
- Java 版本检测
- 自定义 Java 路径选择
"""

import sys
import os
import json
import re
import shutil
import subprocess
import threading
import time
import socket
import webbrowser
from pathlib import Path
from datetime import datetime

import psutil

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QObject, QSize, QUrl
)
from PySide6.QtGui import (
    QFont, QColor, QIcon, QAction, QKeySequence, QDesktopServices
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QStackedWidget, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QInputDialog, QListWidgetItem, QSplitter,
    QFrame, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QGridLayout, QScrollArea
)


# ===================== 日志信号发射器（跨线程安全） =====================
class LogEmitter(QObject):
    """用于从子线程安全地发送日志到主线程"""
    log_signal = Signal(str, str)  # (message, level)


# ===================== 服务器输出读取线程 =====================
class ServerOutputReader(QThread):
    """读取服务器进程的 stdout（包含 stderr），通过信号发送到主线程"""
    log_emitter = LogEmitter()

    def __init__(self, process):
        super().__init__()
        self.process = process
        self._stop = False

    def stop(self):
        """停止读取线程，并断开信号连接（不销毁 emitter）"""
        self._stop = True
        self.quit()
        if not self.wait(1000):
            self.terminate()
        # 断开信号连接，防止残留
        if self.log_emitter:
            try:
                self.log_emitter.log_signal.disconnect()
            except Exception:
                pass

    def run(self):
        stream = self.process.stdout
        try:
            while not self._stop and self.process and self.process.poll() is None:
                line = stream.readline()
                if not line:
                    break
                line = line.strip()
                if line and self.log_emitter is not None:
                    self.log_emitter.log_signal.emit(line, "info")
        except Exception as e:
            if self.log_emitter is not None:
                self.log_emitter.log_signal.emit(f"读取 stdout 异常: {e}", "error")
        finally:
            # 线程结束时断开信号
            if self.log_emitter:
                try:
                    self.log_emitter.log_signal.disconnect()
                except Exception:
                    pass


# ===================== 控制台组件（带颜色） =====================
class ConsoleTextEdit(QTextEdit):
    """带颜色标签的控制台输出组件"""

    COLORS = {
        "error": "#f48771",
        "success": "#6a9955",
        "warning": "#dcdcaa",
        "info": "#9cdcfe",
        "default": "#d4d4d4",
        "timestamp": "#808080"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.max_lines = 10000

    def append_colored(self, text, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(level, self.COLORS["default"])
        html = (
            f'<span style="color:{self.COLORS["timestamp"]};">[{timestamp}]</span> '
            f'<span style="color:{color};">{text}</span><br>'
        )
        self.append(html)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

        doc = self.document()
        if doc.lineCount() > self.max_lines:
            cursor = doc.begin()
            for _ in range(doc.lineCount() - self.max_lines):
                cursor.movePosition(cursor.NextBlock)
            doc.remove(cursor, doc.end())


# ===================== 主窗口 =====================
class ServerManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minecraft 服务器管理器 - PySide6")
        self.resize(960, 600)

        # 服务器进程相关
        self.process = None
        self.server_running = False
        self.stdout_reader = None
        self.server_start_time = None

        # 联机状态
        self.online_active = False

        # 配置文件路径
        self.server_path = Path.cwd()
        self.jar_file = self.server_path / "server.jar"
        self.config_file = self.server_path / "quick_commands.json"
        self.properties_file = self.server_path / "server.properties"
        self.plugins_dir = self.server_path / "Plugins_xiaotu"
        self.launch_config_file = self.server_path / "launch_config.json"
        self.java_config_file = self.server_path / "java_config.json"

        # 加载快捷命令
        self.quick_commands = self.load_quick_commands()

        # 启动脚本路径
        self.launch_script_path = ""

        # 设置 UI
        self.setup_ui()

        # 定时检查进程状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_process_status)
        self.status_timer.start(500)

        # 加载启动配置
        self.load_launch_config()

        # 加载 Java 配置
        self.load_java_config()

        # 检查 EULA
        self.check_eula()

    # ===================== UI 构建 =====================
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧导航
        nav_frame = QFrame()
        nav_frame.setFixedWidth(200)
        nav_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-right: 1px solid #3c3c3c;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                color: #d4d4d4;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px 20px;
                border-left: 4px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #3c3c3c;
                border-left: 4px solid #007acc;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QLabel {
                color: #d4d4d4;
                font-size: 16px;
                font-weight: bold;
                padding: 20px 20px 10px 20px;
            }
        """)
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        title = QLabel("⛏️ 服务器管理")
        nav_layout.addWidget(title)

        self.nav_list = QListWidget()
        self.nav_list.addItems(["服务器控制", "控制台", "快捷命令", "插件管理", "玩家&玩具", "更多工具"])
        self.nav_list.currentRowChanged.connect(self.switch_page)
        nav_layout.addWidget(self.nav_list)
        nav_layout.addStretch()

        self.status_label = QLabel("● 服务器未运行")
        self.status_label.setStyleSheet("color: #f48771; padding: 10px 20px;")
        nav_layout.addWidget(self.status_label)

        main_layout.addWidget(nav_frame)

        # 右侧堆叠页面
        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QGroupBox {
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #d4d4d4;
            }
            QLineEdit, QComboBox, QPushButton {
                background-color: #2d2d2d;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #007acc;
                border: none;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1a8cff;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #808080;
            }
            QTableWidget {
                background-color: #252525;
                alternate-background-color: #2d2d2d;
                color: #d4d4d4;
                gridline-color: #3c3c3c;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 4px;
                border: none;
            }
        """)

        self.page_control = self.create_control_page()
        self.page_console = self.create_console_page()
        self.page_commands = self.create_commands_page()
        self.page_plugins = self.create_plugins_page()
        self.page_players = self.create_players_page()
        self.page_tools = self.create_tools_page()

        self.stacked.addWidget(self.page_control)
        self.stacked.addWidget(self.page_console)
        self.stacked.addWidget(self.page_commands)
        self.stacked.addWidget(self.page_plugins)
        self.stacked.addWidget(self.page_players)
        self.stacked.addWidget(self.page_tools)

        main_layout.addWidget(self.stacked)
        self.nav_list.setCurrentRow(0)

    # ---------- 各页面创建方法 ----------
    def create_control_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        # 服务端文件
        group = QGroupBox("服务端文件")
        g_layout = QHBoxLayout()
        self.jar_path_edit = QLineEdit(str(self.jar_file))
        self.jar_path_edit.setReadOnly(True)
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(self.browse_jar)
        g_layout.addWidget(QLabel("JAR 文件:"))
        g_layout.addWidget(self.jar_path_edit)
        g_layout.addWidget(browse_btn)
        group.setLayout(g_layout)
        layout.addWidget(group)

        # 启动设置（包含 Java 路径选择）
        group2 = QGroupBox("启动设置")
        g2_layout = QVBoxLayout()

        # Java 路径行
        java_row = QHBoxLayout()
        java_row.addWidget(QLabel("Java 路径:"))
        self.java_path_edit = QLineEdit()
        self.java_path_edit.setPlaceholderText("留空则使用系统 PATH 中的 java")
        java_row.addWidget(self.java_path_edit)
        java_browse_btn = QPushButton("浏览")
        java_browse_btn.clicked.connect(self.browse_java)
        java_row.addWidget(java_browse_btn)
        g2_layout.addLayout(java_row)

        # 内存设置和按钮行
        mem_row = QHBoxLayout()
        mem_row.addWidget(QLabel("最小内存:"))
        self.ram_min_combo = QComboBox()
        self.ram_min_combo.addItems(["512M", "1G", "2G", "4G", "8G"])
        self.ram_min_combo.setCurrentText("1G")
        mem_row.addWidget(self.ram_min_combo)

        mem_row.addWidget(QLabel("最大内存:"))
        self.ram_max_combo = QComboBox()
        self.ram_max_combo.addItems(["1G", "2G", "4G", "8G", "16G"])
        self.ram_max_combo.setCurrentText("2G")
        mem_row.addWidget(self.ram_max_combo)

        self.start_btn = QPushButton("启动服务器")
        self.start_btn.clicked.connect(self.start_server)
        mem_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止服务器")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        mem_row.addWidget(self.stop_btn)

        self.save_btn = QPushButton("保存世界")
        self.save_btn.clicked.connect(self.save_world)
        self.save_btn.setEnabled(False)
        mem_row.addWidget(self.save_btn)

        g2_layout.addLayout(mem_row)
        group2.setLayout(g2_layout)
        layout.addWidget(group2)

        # 客户端启动
        group3 = QGroupBox("客户端启动")
        g3_layout = QHBoxLayout()
        g3_layout.addWidget(QLabel("启动脚本:"))
        self.launch_script_edit = QLineEdit()
        self.launch_script_edit.setReadOnly(True)
        self.launch_script_edit.setPlaceholderText("请选择 .bat 或 .sh 文件")
        g3_layout.addWidget(self.launch_script_edit)
        browse_script_btn = QPushButton("浏览")
        browse_script_btn.clicked.connect(self.browse_launch_script)
        g3_layout.addWidget(browse_script_btn)
        self.launch_btn = QPushButton("启动游戏")
        self.launch_btn.clicked.connect(self.launch_client)
        g3_layout.addWidget(self.launch_btn)
        group3.setLayout(g3_layout)
        layout.addWidget(group3)

        # 状态信息
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout()
        self.status_info = QLabel("就绪")
        status_layout.addWidget(self.status_info)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ===== 命令输入框 =====
        cmd_group = QGroupBox("命令输入")
        cmd_layout = QHBoxLayout()
        cmd_layout.addWidget(QLabel("命令:"))
        self.control_cmd_input = QLineEdit()
        self.control_cmd_input.returnPressed.connect(self.send_control_command)
        cmd_layout.addWidget(self.control_cmd_input)
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_control_command)
        cmd_layout.addWidget(send_btn)
        cmd_group.setLayout(cmd_layout)
        layout.addWidget(cmd_group)

        layout.addStretch()
        return page

    def create_console_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.console = ConsoleTextEdit()
        layout.addWidget(self.console)

        cmd_layout = QHBoxLayout()
        cmd_layout.addWidget(QLabel("命令:"))
        self.cmd_input = QLineEdit()
        self.cmd_input.returnPressed.connect(self.send_command)
        cmd_layout.addWidget(self.cmd_input)
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_command)
        cmd_layout.addWidget(send_btn)
        layout.addLayout(cmd_layout)
        return page

    def create_commands_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.cmd_button_layout = QGridLayout(container)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        refresh_btn = QPushButton("🔄 刷新快捷命令")
        refresh_btn.clicked.connect(self.refresh_quick_commands_ui)
        layout.addWidget(refresh_btn)

        self.refresh_quick_commands_ui()
        return page

    def create_plugins_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        tool_layout = QHBoxLayout()
        tool_layout.addWidget(QLabel(f"插件目录: {self.plugins_dir}"))
        tool_layout.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_plugin_table)
        tool_layout.addWidget(refresh_btn)

        install_btn = QPushButton("📂 选择本地插件安装")
        install_btn.clicked.connect(self.install_plugin)
        tool_layout.addWidget(install_btn)

        lanzou_btn = QPushButton("🌐 从蓝奏云下载插件")
        lanzou_btn.clicked.connect(self.guide_download_from_lanzou)
        tool_layout.addWidget(lanzou_btn)

        github_btn = QPushButton("🐙 从GitHub下载插件")
        github_btn.clicked.connect(self.download_from_github)
        tool_layout.addWidget(github_btn)

        open_btn = QPushButton("打开目录")
        open_btn.clicked.connect(self.open_plugins_folder)
        tool_layout.addWidget(open_btn)

        layout.addLayout(tool_layout)

        self.plugin_table = QTableWidget()
        self.plugin_table.setColumnCount(5)
        self.plugin_table.setHorizontalHeaderLabels(["文件名", "类型", "大小", "修改时间", "操作"])
        self.plugin_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.plugin_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.plugin_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.plugin_table.setAlternatingRowColors(True)
        self.plugin_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plugin_table.customContextMenuRequested.connect(self.show_plugin_context_menu)
        self.plugin_table.doubleClicked.connect(self.on_plugin_double_click)
        layout.addWidget(self.plugin_table)

        self.refresh_plugin_table()
        return page

    def create_players_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QGroupBox("在线玩家")
        left_layout = QVBoxLayout()
        self.player_list = QListWidget()
        left_layout.addWidget(self.player_list)
        btn_layout = QHBoxLayout()
        refresh_player_btn = QPushButton("刷新玩家列表")
        refresh_player_btn.clicked.connect(self.refresh_player_list)
        btn_layout.addWidget(refresh_player_btn)
        show_name_btn = QPushButton("显示玩家名")
        show_name_btn.clicked.connect(self.show_player_name)
        btn_layout.addWidget(show_name_btn)
        left_layout.addLayout(btn_layout)
        left.setLayout(left_layout)
        layout.addWidget(left, 1)

        right = QGroupBox("玩具列表")
        right_layout = QVBoxLayout()
        self.toy_list = QListWidget()
        toys = ["钻石剑", "三叉戟", "烟花火箭", "鞘翅", "不死图腾", "附魔金苹果"]
        for toy in toys:
            self.toy_list.addItem(toy)
        right_layout.addWidget(self.toy_list)
        give_btn = QPushButton("给予选中玩具")
        give_btn.clicked.connect(self.give_selected_toy)
        right_layout.addWidget(give_btn)
        right.setLayout(right_layout)
        layout.addWidget(right, 1)

        self.refresh_player_list()
        return page

    def create_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # 联机环境面板
        online_group = QGroupBox("🌐 联机环境")
        online_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px;
            }
        """)
        online_layout = QVBoxLayout(online_group)

        status_row = QHBoxLayout()
        self.online_status_indicator = QLabel("●")
        self.online_status_indicator.setStyleSheet("color: #808080; font-size: 18px;")
        self.online_status_label = QLabel("未检测")
        self.online_status_label.setStyleSheet("color: #808080;")
        status_row.addWidget(self.online_status_indicator)
        status_row.addWidget(self.online_status_label)
        status_row.addStretch()
        refresh_online_btn = QPushButton("🔄 检测环境")
        refresh_online_btn.clicked.connect(self.check_online_environment)
        status_row.addWidget(refresh_online_btn)
        online_layout.addLayout(status_row)

        self.env_check_list = QListWidget()
        self.env_check_list.setMaximumHeight(120)
        self.env_check_list.setStyleSheet("""
            QListWidget {
                background-color: #252525;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
            }
        """)
        online_layout.addWidget(self.env_check_list)

        addr_row = QHBoxLayout()
        addr_row.addWidget(QLabel("联机地址:"))
        self.online_address_edit = QLineEdit()
        self.online_address_edit.setReadOnly(True)
        self.online_address_edit.setPlaceholderText("点击「启动联机」生成地址")
        self.online_address_edit.setStyleSheet("color: #6a9955;")
        addr_row.addWidget(self.online_address_edit)
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self.copy_online_address)
        addr_row.addWidget(copy_btn)
        online_layout.addLayout(addr_row)

        btn_row = QHBoxLayout()
        self.start_online_btn = QPushButton("▶ 启动联机")
        self.start_online_btn.clicked.connect(self.start_online)
        self.start_online_btn.setEnabled(False)
        btn_row.addWidget(self.start_online_btn)
        self.stop_online_btn = QPushButton("⏹ 停止联机")
        self.stop_online_btn.clicked.connect(self.stop_online)
        self.stop_online_btn.setEnabled(False)
        btn_row.addWidget(self.stop_online_btn)
        btn_row.addStretch()
        online_layout.addLayout(btn_row)
        layout.addWidget(online_group)

        # 原工具按钮
        btn_layout = QGridLayout()
        actions = [
            ("清除控制台", self.clear_console),
            ("编辑快捷命令", self.edit_commands),
            ("服务器配置", self.edit_server_properties),
            ("打开插件目录", self.open_plugins_folder),
        ]
        for i, (text, func) in enumerate(actions):
            btn = QPushButton(text)
            btn.clicked.connect(func)
            btn_layout.addWidget(btn, i // 2, i % 2)

        layout.addLayout(btn_layout)
        layout.addStretch()

        QTimer.singleShot(500, self.check_online_environment)
        return page

    # ===================== 页面切换 =====================
    def switch_page(self, index):
        self.stacked.setCurrentIndex(index)
        if index == 3:
            self.refresh_plugin_table()
        elif index == 4:
            self.refresh_player_list()

    # ===================== 日志 =====================
    def log(self, msg, level="info"):
        self.console.append_colored(msg, level)

    def log_safe(self, msg, level="info"):
        QTimer.singleShot(0, lambda: self.log(msg, level))

    # ===================== 专用槽函数（用于信号连接，便于断开） =====================
    def on_stdout_log(self, msg):
        self.log(msg, "info")

    # ===================== 服务器控制 =====================
    def browse_jar(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择服务端 JAR", str(self.server_path), "JAR 文件 (*.jar)"
        )
        if path:
            self.jar_path_edit.setText(path)
            self.jar_file = Path(path)

    def browse_java(self):
        """选择 Java 可执行文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Java 可执行文件",
            "C:\\Program Files",
            "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if path:
            self.java_path_edit.setText(path)
            self.log(f"已选择 Java: {path}", "info")
            self.save_java_config(path)

    def save_java_config(self, java_path):
        """保存 Java 路径配置"""
        try:
            with open(self.java_config_file, 'w', encoding='utf-8') as f:
                json.dump({"java_path": java_path}, f, indent=2)
        except Exception as e:
            self.log(f"保存 Java 配置失败: {e}", "error")

    def load_java_config(self):
        """加载 Java 路径配置"""
        if self.java_config_file.exists():
            try:
                with open(self.java_config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    java_path = data.get("java_path", "")
                    if java_path and Path(java_path).exists():
                        self.java_path_edit.setText(java_path)
                        return java_path
            except Exception as e:
                self.log(f"加载 Java 配置失败: {e}", "error")
        return ""

    def check_eula(self):
        eula = Path(self.jar_path_edit.text()).parent / "eula.txt"
        if not eula.exists():
            return
        try:
            content = eula.read_text().strip().lower()
            if "eula=false" in content:
                reply = QMessageBox.question(
                    self, "接受 EULA",
                    "需要接受 Minecraft EULA 才能启动。\n是否接受？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    eula.write_text("eula=true")
                    self.log("已接受 EULA", "success")
        except Exception:
            pass

    def check_java_version(self, java_path="java"):
        """检查 Java 版本是否满足要求（至少 Java 21）"""
        try:
            result = subprocess.run(
                [java_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version_output = result.stderr.strip() if result.stderr else result.stdout.strip()
            import re
            match = re.search(r'version "(\d+)', version_output)
            if match:
                major_version = int(match.group(1))
                if major_version < 21:
                    return False, f"当前 Java 版本为 {major_version}，需要 Java 21 或更高版本。"
                return True, f"Java 版本 {major_version} 符合要求"
            else:
                return False, "无法解析 Java 版本"
        except FileNotFoundError:
            return False, f"找不到 Java 可执行文件: {java_path}"
        except Exception as e:
            return False, f"检查 Java 版本失败: {e}"

    def start_server(self):
        if self.server_running:
            QMessageBox.warning(self, "警告", "服务器已在运行")
            return

        jar = Path(self.jar_path_edit.text())
        if not jar.exists():
            QMessageBox.critical(self, "错误", f"找不到服务端文件: {jar}")
            return

        # ===== 获取 Java 路径 =====
        java_path = self.java_path_edit.text().strip()
        if not java_path:
            java_path = "java"  # 使用系统 PATH
        elif not Path(java_path).exists():
            QMessageBox.critical(self, "错误", f"找不到 Java 可执行文件:\n{java_path}")
            return

        # ===== 检查 Java 版本 =====
        ok, msg = self.check_java_version(java_path)
        if not ok:
            QMessageBox.critical(
                self,
                "Java 版本过低",
                f"{msg}\n\n"
                "请安装 Java 21 或更高版本。\n"
                "下载地址: https://adoptium.net/\n\n"
                "或在「启动设置」中指定正确的 Java 路径。"
            )
            return

        eula = jar.parent / "eula.txt"
        if not eula.exists() or ("eula=false" in eula.read_text().lower()):
            reply = QMessageBox.question(
                self, "接受 EULA",
                "需要接受 Minecraft EULA 才能启动。\n是否接受？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                eula.write_text("eula=true")
                self.log("已接受 EULA", "success")
            else:
                return

        cmd = [
            java_path,
            f"-Xms{self.ram_min_combo.currentText()}",
            f"-Xmx{self.ram_max_combo.currentText()}",
            "-jar", str(jar), "nogui"
        ]
        self.log(f"启动命令: {' '.join(cmd)}", "info")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(jar.parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )
        except Exception as e:
            self.log(f"启动失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")
            return

        self.server_running = True
        self.server_start_time = time.time()
        self.update_server_status(True)
        self.log("服务器启动成功！", "success")

        # ===== 清理旧的 reader =====
        if self.stdout_reader:
            self.stdout_reader.stop()
            self.stdout_reader.wait()
            self.stdout_reader = None

        # ===== 创建新的 reader =====
        self.stdout_reader = ServerOutputReader(self.process)
        self.stdout_reader.log_emitter.log_signal.connect(
            self.on_stdout_log,
            Qt.ConnectionType.UniqueConnection
        )
        self.stdout_reader.start()

    def check_process_status(self):
        if self.process is not None:
            poll = self.process.poll()
            if poll is not None and self.server_running:
                self.server_running = False
                self.update_server_status(False)
                self.log(f"服务器进程意外结束，退出码: {poll}", "error")
                self.process = None

        if self.server_running and self.server_start_time:
            elapsed = int(time.time() - self.server_start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            self.status_info.setText(f"运行中 | 已运行: {hours}h {minutes}m")

    # ---------------------- 命令发送（统一入口） ----------------------
    def send_command(self):
        """控制台页面的发送命令"""
        cmd = self.cmd_input.text().strip()
        if cmd:
            self.cmd_input.clear()
            self._process_command(cmd)

    def send_control_command(self):
        """服务器控制页面的发送命令"""
        cmd = self.control_cmd_input.text().strip()
        if cmd:
            self.control_cmd_input.clear()
            self._process_command(cmd)

    def _process_command(self, cmd):
        """统一处理命令（支持 /快捷命令 或 直接发送）"""
        if not self.server_running:
            QMessageBox.warning(self, "警告", "服务器未运行")
            return
        if cmd.startswith('/'):
            parts = cmd[1:].split(maxsplit=1)
            name = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            self.execute_quick_command(name, arg)
        else:
            self.send_to_server(cmd)

    def send_to_server(self, cmd):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                self.log(f">>> {cmd}", "info")
            except Exception as e:
                self.log(f"发送命令失败: {e}", "error")
        else:
            self.log("无法发送命令：进程未运行", "error")

    def stop_server(self):
        if not self.server_running:
            return
        reply = QMessageBox.question(
            self, "确认", "确定要停止服务器吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.log("正在停止服务器...", "warning")
            self.send_to_server("stop")
            QTimer.singleShot(30000, self.force_stop)

    def force_stop(self):
        if self.process and self.process.poll() is None:
            self.log("服务器未响应，强制终止", "error")
            self.process.terminate()
            self.process.kill()
            if self.stdout_reader:
                self.stdout_reader.stop()

    def save_world(self):
        if self.server_running:
            self.send_to_server("save-all")
            self.log("正在保存世界...", "info")
        else:
            QMessageBox.warning(self, "警告", "服务器未运行")

    def update_server_status(self, running):
        self.server_running = running
        if running:
            self.status_label.setText("● 服务器运行中")
            self.status_label.setStyleSheet("color: #6a9955; padding: 10px 20px;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.status_info.setText("运行中...")
        else:
            self.status_label.setText("● 服务器未运行")
            self.status_label.setStyleSheet("color: #f48771; padding: 10px 20px;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_info.setText("已停止")
            self.server_start_time = None

    # ===================== 客户端启动脚本 =====================
    def browse_launch_script(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择启动脚本", str(self.server_path),
            "批处理文件 (*.bat);;Shell脚本 (*.sh);;所有文件 (*.*)"
        )
        if path:
            self.launch_script_path = path
            self.launch_script_edit.setText(path)
            self.save_launch_config()
            self.log(f"已选择启动脚本: {path}", "info")

    def launch_client(self):
        script = self.launch_script_path
        if not script or not Path(script).exists():
            QMessageBox.warning(self, "提示", "请先选择有效的启动脚本（点击“浏览...”按钮）")
            return
        script_path = Path(script)
        self.log(f"正在启动客户端: {script_path.name}", "info")
        try:
            if sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", str(script_path)], cwd=str(script_path.parent))
            else:
                subprocess.Popen([str(script_path)], cwd=str(script_path.parent))
            self.log("✅ 客户端已启动", "success")
            QMessageBox.information(self, "提示", "游戏已启动，请查看游戏窗口。")
        except Exception as e:
            self.log(f"启动失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"启动失败: {e}")

    def load_launch_config(self):
        if self.launch_config_file.exists():
            try:
                with open(self.launch_config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.launch_script_path = data.get("script", "")
                    self.launch_script_edit.setText(self.launch_script_path)
            except Exception as e:
                self.log(f"加载启动配置失败: {e}", "error")

    def save_launch_config(self):
        data = {"script": self.launch_script_path}
        try:
            with open(self.launch_config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log(f"保存启动配置失败: {e}", "error")

    # ===================== 联机环境检测 =====================
    def check_online_environment(self):
        self.env_check_list.clear()

        checks = [
            ("🔍 Lyt it 目录存在", self.check_lyt_dir),
            ("🔍 末影联机 (main.exe) 已安装", self.check_enderlink_main),
            ("🔍 端口 25565 可用", self.check_port_available),
            ("🔍 服务器已启动", self.check_server_running_for_online),
        ]

        all_passed = True
        for label, check_func in checks:
            item = QListWidgetItem(label)
            try:
                passed, detail = check_func()
                if passed:
                    item.setText(f"✅ {label} - {detail if detail else '正常'}")
                    item.setForeground(QColor("#6a9955"))
                else:
                    item.setText(f"❌ {label} - {detail if detail else '未通过'}")
                    item.setForeground(QColor("#f48771"))
                    all_passed = False
            except Exception as e:
                item.setText(f"⚠️ {label} - 检测异常: {e}")
                item.setForeground(QColor("#dcdcaa"))
                all_passed = False
            self.env_check_list.addItem(item)

        if all_passed:
            self.online_status_indicator.setStyleSheet("color: #6a9955; font-size: 18px;")
            self.online_status_label.setText("环境就绪")
            self.online_status_label.setStyleSheet("color: #6a9955;")
            self.start_online_btn.setEnabled(True)
            self.online_address_edit.setText("✅ 环境就绪，点击「启动联机」")
            self.online_address_edit.setStyleSheet("color: #6a9955;")
        else:
            self.online_status_indicator.setStyleSheet("color: #f48771; font-size: 18px;")
            self.online_status_label.setText("环境不完整")
            self.online_status_label.setStyleSheet("color: #f48771;")
            self.start_online_btn.setEnabled(False)
            self.online_address_edit.clear()
            self.online_address_edit.setPlaceholderText("请解决上述问题后重新检测")
            self.online_address_edit.setStyleSheet("color: #808080;")

        self.log("联机环境检测完成", "info")

    def check_lyt_dir(self):
        lyt_dir = self.server_path / "Lyt it"
        if not lyt_dir.exists():
            try:
                lyt_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"已创建 Lyt it 目录: {lyt_dir}", "info")
                return True, "已自动创建"
            except Exception as e:
                return False, f"创建失败: {e}"
        return True, "目录存在"

    def check_enderlink_main(self):
        main_exe = self.server_path / "Lyt it" / "main.exe"
        if main_exe.exists():
            return True, "已安装"
        else:
            return False, "请从 www.teft.cn 下载 EnderLink 并解压到 Lyt it 目录"

    def check_port_available(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', 25565))
            sock.close()
            if result == 0:
                return True, "端口已被占用（服务器可能已运行）"
            else:
                return True, "端口 25565 可用"
        except Exception as e:
            return False, f"检测异常: {e}"

    def check_server_running_for_online(self):
        if self.server_running:
            return True, f"PID: {self.process.pid if self.process else '运行中'}"
        else:
            return False, "请先启动服务器"

    def start_online(self):
        main_exe = self.server_path / "Lyt it" / "main.exe"
        lyt_dir = self.server_path / "Lyt it"

        if not main_exe.exists():
            QMessageBox.warning(
                self,
                "提示",
                f"未找到末影联机主程序:\n{main_exe}\n"
                "请从 www.teft.cn 下载 EnderLink 并解压到 Lyt it 目录。"
            )
            return

        if not self.server_running:
            reply = QMessageBox.question(
                self, "提示",
                "服务器未启动，联机需要服务器先运行。\n是否先启动服务器？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.start_server()
                QTimer.singleShot(3000, self._do_start_online)
            return

        self._do_start_online()

    def _do_start_online(self):
        main_exe = self.server_path / "Lyt it" / "main.exe"
        lyt_dir = self.server_path / "Lyt it"

        if not main_exe.exists():
            self.log("末影联机主程序不存在，无法启动", "error")
            return

        self.log(f"正在启动末影联机: {main_exe}", "info")
        try:
            if sys.platform == "win32":
                cmd = f'cd /d "{lyt_dir}" && main.exe --create'
                subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f'cd "{lyt_dir}" && ./main.exe --create'])

            self.log("✅ 末影联机已启动", "success")
            self.online_active = True
            self.stop_online_btn.setEnabled(True)
            self.online_address_edit.setText("🌐 联机已启动，请查看弹出的终端窗口")
            self.online_address_edit.setStyleSheet("color: #4FC3F7;")
        except Exception as e:
            self.log(f"启动联机失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"启动联机失败:\n{e}")

    def stop_online(self):
        try:
            killed = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = proc.info['name'] or ''
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if ('main.exe' in name.lower() or
                        'enderlink' in name.lower() or
                        ('main' in cmdline.lower() and '--create' in cmdline.lower())):
                        proc.terminate()
                        killed += 1
                        self.log(f"已终止联机进程 (PID: {proc.info['pid']})", "info")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed > 0:
                self.log(f"已终止 {killed} 个联机进程", "info")
            else:
                self.log("没有找到正在运行的联机进程", "info")

            self.stop_online_btn.setEnabled(False)
            self.online_active = False
            self.online_address_edit.clear()
            self.online_address_edit.setPlaceholderText("联机已停止")
            self.online_address_edit.setStyleSheet("color: #808080;")
        except Exception as e:
            self.log(f"停止联机失败: {e}", "error")

    def copy_online_address(self):
        address = self.online_address_edit.text()
        if address and address not in ("✅ 环境就绪，点击「启动联机」", "联机已停止"):
            clipboard = QApplication.clipboard()
            clipboard.setText(address)
            self.log("✅ 联机地址已复制到剪贴板", "success")
            QMessageBox.information(self, "提示", "联机地址已复制到剪贴板")
        else:
            QMessageBox.warning(self, "提示", "没有可复制的地址，请先启动联机")

    # ===================== 插件下载与安装 =====================
    def guide_download_from_lanzou(self):
        """引导用户从蓝奏云手动下载插件"""
        url = "https://wwapl.lanzout.com/igFFb44iaw8h"
        password = "1234"
        target_dir = self.plugins_dir

        msg = (
            f"📥 请按以下步骤从蓝奏云下载并安装插件:\n\n"
            f"1. 点击「确定」后，浏览器将打开下载页面\n"
            f"2. 输入密码: {password}\n"
            f"3. 点击下载 .exe 文件\n"
            f"4. 将下载的文件移动到:\n"
            f"   {target_dir}\n"
            f"5. 回到本程序，点击「刷新」即可看到新插件\n\n"
            f"🔗 下载链接: {url}"
        )

        reply = QMessageBox.question(
            self, "蓝奏云下载引导",
            msg,
            QMessageBox.Ok | QMessageBox.Cancel
        )
        if reply != QMessageBox.Ok:
            return

        try:
            webbrowser.open(url)
            self.log(f"已打开蓝奏云下载页面: {url}", "info")
        except Exception as e:
            self.log(f"打开网页失败: {e}", "error")
            QMessageBox.warning(self, "错误", f"无法打开网页: {e}")
            return

        self.open_plugins_folder()

        QMessageBox.information(
            self, "提示",
            f"✅ 已打开下载页面和插件目录\n\n"
            f"请完成以下操作:\n"
            f"1. 输入密码: {password}\n"
            f"2. 下载 .exe 文件\n"
            f"3. 将文件拖入打开的插件目录\n"
            f"4. 回到本程序点击「刷新」\n\n"
            f"📂 插件目录: {target_dir}"
        )

    def download_from_github(self):
        """从 GitHub 仓库下载插件，读取 plugins.json 清单"""
        import requests

        # 检查依赖
        try:
            import requests
        except ImportError:
            QMessageBox.warning(
                self, "缺少依赖",
                "需要安装 requests 库才能从GitHub下载。\n\n请执行: pip install requests"
            )
            return

        manifest_url = "https://raw.githubusercontent.com/OUGE-1/1/main/plugins.json"

        # 获取插件清单
        try:
            response = requests.get(manifest_url, timeout=10)
            response.raise_for_status()
            manifest = response.json()
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(
                self, "获取清单失败",
                f"无法获取插件清单:\n{e}\n\n"
                f"请检查网络连接或稍后重试。"
            )
            return
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self, "清单格式错误",
                f"插件清单格式无效:\n{e}\n\n"
                f"请联系开发者检查 plugins.json 文件。"
            )
            return

        # 解析插件列表
        plugins = manifest.get("plugins", [])
        if not plugins:
            QMessageBox.warning(
                self, "没有插件",
                "清单中没有可用的插件。"
            )
            return

        # 构建选择列表
        choices = []
        for p in plugins:
            name = p.get("name", "未知插件")
            desc = p.get("description", "")
            version = p.get("version", "")
            size = p.get("size", "")
            label = f"{name}"
            if desc:
                label += f" - {desc}"
            if version:
                label += f" (v{version})"
            if size:
                label += f" [{size}]"
            choices.append(label)

        # 让用户选择
        selected, ok = QInputDialog.getItem(
            self,
            "选择要下载的插件",
            "请选择要从 GitHub 下载的插件:",
            choices,
            0,
            False
        )
        if not ok or not selected:
            return

        # 找到选中的插件
        selected_plugin = None
        for idx, p in enumerate(plugins):
            label = choices[idx]
            if label == selected:
                selected_plugin = p
                break

        if not selected_plugin:
            return

        file_name = selected_plugin.get("file")
        if not file_name:
            QMessageBox.warning(self, "错误", "插件信息缺少文件名")
            return

        # 构建下载 URL
        base_url = "https://raw.githubusercontent.com/OUGE-1/1/main"
        download_url = f"{base_url}/{file_name}"

        # 确认下载
        target_path = self.plugins_dir / file_name
        if target_path.exists():
            reply = QMessageBox.question(
                self, "文件已存在",
                f"插件目录中已存在同名文件:\n{file_name}\n\n是否覆盖?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        # 确保目录存在
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # 下载文件
        self.log(f"正在从 GitHub 下载: {file_name}", "info")
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            self.log(f"⏳ 下载进度: {percent:.1f}%", "info")

            self.log(f"✅ 下载完成: {file_name}", "success")
            self.refresh_plugin_table()

            QMessageBox.information(
                self, "下载成功",
                f"✅ 插件已成功下载!\n\n"
                f"📎 文件名: {file_name}\n"
                f"📁 位置: {target_path}\n"
                f"📦 大小: {downloaded / 1024:.2f} KB\n\n"
                f"请点击「刷新」查看新插件。"
            )

        except Exception as e:
            self.log(f"下载失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"下载失败:\n{e}")

    # ===================== 本地插件安装 =====================
    def install_plugin(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择插件文件", str(self.server_path),
            "可执行文件 (*.exe);;Python脚本 (*.py);;所有文件 (*.*)"
        )
        if not file_path:
            return
        src = Path(file_path)
        if src.suffix.lower() not in ('.exe', '.py'):
            QMessageBox.warning(self, "警告", "请选择 .exe 或 .py 文件")
            return
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        dst = self.plugins_dir / src.name
        if dst.exists():
            reply = QMessageBox.question(
                self, "确认", f"文件 {src.name} 已存在，覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        try:
            shutil.copy2(src, dst)
            self.log(f"已安装插件: {src.name}", "success")
            self.refresh_plugin_table()
        except Exception as e:
            self.log(f"安装失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"安装失败: {e}")

    # ===================== 插件管理 =====================
    def refresh_plugin_table(self):
        self.plugin_table.setRowCount(0)
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

        exe_files = list(self.plugins_dir.glob("*.exe"))
        py_files = list(self.plugins_dir.glob("*.py"))
        all_plugins = [(f, "EXE") for f in exe_files] + [(f, "PY") for f in py_files]

        for path, ptype in sorted(all_plugins, key=lambda x: x[0].name):
            row = self.plugin_table.rowCount()
            self.plugin_table.insertRow(row)
            self.plugin_table.setItem(row, 0, QTableWidgetItem(path.name))
            self.plugin_table.setItem(row, 1, QTableWidgetItem(ptype))

            size = self.get_file_size(path)
            self.plugin_table.setItem(row, 2, QTableWidgetItem(size))

            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            self.plugin_table.setItem(row, 3, QTableWidgetItem(mtime))

            run_btn = QPushButton("▶ 运行")
            run_btn.clicked.connect(lambda checked, p=path: self.run_plugin(p))
            self.plugin_table.setCellWidget(row, 4, run_btn)

            self.plugin_table.item(row, 0).setData(Qt.UserRole, str(path))

    def get_file_size(self, path):
        sz = path.stat().st_size
        for u in ['B', 'KB', 'MB', 'GB']:
            if sz < 1024.0:
                return f"{sz:.1f} {u}"
            sz /= 1024.0
        return f"{sz:.1f} TB"

    def open_plugins_folder(self):
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.plugins_dir)))

    def run_plugin(self, path):
        ptype = path.suffix.lower()
        self.log(f"运行插件: {path.name} (类型: {ptype})", "info")
        try:
            if ptype == ".exe":
                if sys.platform == "win32":
                    subprocess.Popen(
                        [str(path), "--run_plugin"],
                        cwd=str(self.plugins_dir),
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    subprocess.Popen([str(path), "--run_plugin"], cwd=str(self.plugins_dir))
                self.log(f"插件 {path.name} 已在后台启动", "success")
            else:  # .py
                python_exe = sys.executable

                def run_py():
                    try:
                        result = subprocess.run(
                            [python_exe, str(path), "--run_plugin"],
                            cwd=str(self.plugins_dir),
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.stdout:
                            self.log_safe(f"[插件输出]\n{result.stdout}", "info")
                        if result.stderr:
                            self.log_safe(f"[插件错误]\n{result.stderr}", "error")
                        if result.returncode == 0:
                            self.log_safe(f"插件 {path.name} 执行完成", "success")
                        else:
                            self.log_safe(f"插件 {path.name} 返回非零代码: {result.returncode}", "warning")
                    except subprocess.TimeoutExpired:
                        self.log_safe(f"插件 {path.name} 执行超时（60秒）", "error")
                    except Exception as e:
                        self.log_safe(f"执行插件异常: {e}", "error")

                threading.Thread(target=run_py, daemon=True).start()
        except Exception as e:
            self.log(f"运行失败: {e}", "error")
            QMessageBox.critical(self, "错误", f"运行失败:\n{e}")

    def on_plugin_double_click(self, index):
        row = index.row()
        widget = self.plugin_table.cellWidget(row, 4)
        if widget:
            widget.click()

    def show_plugin_context_menu(self, pos):
        row = self.plugin_table.rowAt(pos.y())
        if row < 0:
            return
        self.plugin_table.selectRow(row)

        menu = QMenu(self)
        menu.addAction("▶ 运行", lambda: self.run_selected_plugin())
        menu.addSeparator()
        menu.addAction("🗑 删除", self.delete_selected_plugin)
        menu.addAction("✏️ 重命名", self.rename_selected_plugin)
        menu.addSeparator()
        menu.addAction("📁 在文件管理器中显示", self.open_selected_plugin_location)
        menu.exec(self.plugin_table.mapToGlobal(pos))

    def run_selected_plugin(self):
        row = self.plugin_table.currentRow()
        if row < 0:
            return
        path = self.plugin_table.item(row, 0).data(Qt.UserRole)
        if path:
            self.run_plugin(Path(path))

    def delete_selected_plugin(self):
        row = self.plugin_table.currentRow()
        if row < 0:
            return
        name = self.plugin_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除 {name} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                (self.plugins_dir / name).unlink()
                self.log(f"已删除插件: {name}", "success")
                self.refresh_plugin_table()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def rename_selected_plugin(self):
        row = self.plugin_table.currentRow()
        if row < 0:
            return
        old_name = self.plugin_table.item(row, 0).text()
        new_name, ok = QInputDialog.getText(self, "重命名", "新文件名:", text=old_name)
        if ok and new_name.strip():
            new_name = new_name.strip()
            old_ext = Path(old_name).suffix
            new_ext = Path(new_name).suffix
            if not new_ext and old_ext:
                new_name += old_ext

            if new_name == old_name:
                return

            old_path = self.plugins_dir / old_name
            new_path = self.plugins_dir / new_name
            if new_path.exists():
                QMessageBox.warning(self, "警告", "目标文件已存在")
                return
            try:
                old_path.rename(new_path)
                self.log(f"重命名: {old_name} -> {new_name}", "success")
                self.refresh_plugin_table()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名失败: {e}")

    def open_selected_plugin_location(self):
        row = self.plugin_table.currentRow()
        if row >= 0:
            path = self.plugin_table.item(row, 0).data(Qt.UserRole)
            if path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))
                return
        self.open_plugins_folder()

    # ===================== 快捷命令 =====================
    def load_quick_commands(self):
        default = {
            "help": {"description": "显示帮助", "command": None},
            "stop": {"description": "停止服务器", "command": "stop"},
            "save": {"description": "保存世界", "command": "save-all"},
            "list": {"description": "在线玩家", "command": "list"},
            "say": {"description": "广播消息", "command": "say {args}"},
            "kick": {"description": "踢出玩家", "command": "kick {args}"},
            "ban": {"description": "封禁玩家", "command": "ban {args}"},
            "op": {"description": "给予管理员", "command": "op {args}"},
            "gamemode": {"description": "游戏模式", "command": "gamemode {args}"},
            "time": {"description": "设置时间", "command": "time {args}"},
            "weather": {"description": "设置天气", "command": "weather {args}"},
            "tp": {"description": "传送", "command": "tp {args}"},
            "give": {"description": "给予物品", "command": "give {args}"},
            "seed": {"description": "世界种子", "command": "seed"}
        }
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user = json.load(f)
                    default.update(user)
            except Exception:
                pass
        else:
            self.save_quick_commands(default)
        return default

    def save_quick_commands(self, cmds):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(cmds, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"保存配置失败: {e}", "error")

    def refresh_quick_commands_ui(self):
        layout = self.cmd_button_layout
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        row, col = 0, 0
        for name, info in self.quick_commands.items():
            if name == "help":
                continue
            btn = QPushButton(f"/{name}")
            btn.setToolTip(info.get('description', ''))
            btn.clicked.connect(lambda checked, n=name: self.show_command_dialog(n))
            layout.addWidget(btn, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1

    def show_command_dialog(self, cmd_name):
        if not self.server_running:
            QMessageBox.warning(self, "警告", "服务器未运行")
            return
        info = self.quick_commands.get(cmd_name)
        if not info:
            return
        if info.get('command') and '{args}' in info['command']:
            args, ok = QInputDialog.getText(
                self, "执行命令",
                f"{info['description']}\n格式: {info['command'].replace('{args}', '<参数>')}\n请输入参数:"
            )
            if ok and args.strip():
                self.execute_quick_command(cmd_name, args.strip())
        else:
            self.execute_quick_command(cmd_name)

    def execute_quick_command(self, cmd_name, args=""):
        info = self.quick_commands.get(cmd_name)
        if not info or not info['command']:
            return
        if '{args}' in info['command']:
            if not args:
                QMessageBox.information(self, "提示", f"命令 /{cmd_name} 需要参数")
                return
            full = info['command'].format(args=args)
        else:
            full = info['command']
        self.send_to_server(full)

    def edit_commands(self):
        if self.config_file.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config_file)))
        else:
            self.save_quick_commands(self.quick_commands)

    # ===================== 玩家 & 玩具 =====================
    def refresh_player_list(self):
        if not self.server_running:
            self.player_list.clear()
            self.player_list.addItem("（服务器未运行）")
            return
        self.send_to_server("list")
        QTimer.singleShot(800, self.parse_player_list)

    def parse_player_list(self):
        content = self.console.toPlainText()
        lines = content.splitlines()
        pattern = re.compile(r"There are \d+ of a max of \d+ players online: (.*)")
        players = []
        for line in reversed(lines):
            m = pattern.search(line)
            if m and m.group(1).strip():
                players = [p.strip() for p in m.group(1).split(',')]
                break
        self.player_list.clear()
        if players:
            self.player_list.addItems(players)
        else:
            self.player_list.addItem("（暂无玩家在线）")

    def show_player_name(self):
        item = self.player_list.currentItem()
        if item:
            player = item.text()
            if player not in ("（服务器未运行）", "（暂无玩家在线）"):
                QMessageBox.information(self, "玩家名", f"玩家：{player}")

    def give_selected_toy(self):
        player_item = self.player_list.currentItem()
        toy_item = self.toy_list.currentItem()
        if not player_item or not toy_item:
            QMessageBox.warning(self, "提示", "请选择一个玩家和一个玩具")
            return
        player = player_item.text()
        toy = toy_item.text()
        if player in ("（服务器未运行）", "（暂无玩家在线）"):
            QMessageBox.warning(self, "提示", "请选择有效的玩家")
            return
        self.send_to_server(f"say 给予 {player} 一个 {toy}")
        self.log(f"已尝试给予玩家 {player} 玩具：{toy}", "info")

    # ===================== server.properties 编辑器 =====================
    PROPERTY_TRANSLATIONS = {
        "server-port": "服务器端口",
        "server-ip": "服务器IP地址",
        "online-mode": "正版验证",
        "max-players": "最大玩家数",
        "view-distance": "视野距离",
        "gamemode": "默认游戏模式",
        "difficulty": "游戏难度",
        "level-name": "世界名称",
        "level-seed": "世界种子",
        "allow-flight": "允许飞行",
        "enable-command-block": "启用命令方块",
        "motd": "服务器欢迎语",
        "white-list": "白名单",
        "pvp": "PVP",
        "hardcore": "极限模式"
    }

    def edit_server_properties(self):
        if not self.properties_file.exists():
            self.properties_file.write_text("#Minecraft server properties\n", encoding='utf-8')

        props = self.load_properties_file()
        dialog = QDialog(self)
        dialog.setWindowTitle("服务器配置编辑")
        dialog.resize(900, 700)

        layout = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.prop_edits = {}
        row = 0
        for key, val in sorted(props.items()):
            cn = self.PROPERTY_TRANSLATIONS.get(key, key)
            label = QLabel(f"{cn}\n({key})")
            grid.addWidget(label, row, 0, Qt.AlignLeft)
            edit = QLineEdit(val)
            grid.addWidget(edit, row, 1)
            self.prop_edits[key] = edit
            row += 1

        add_group = QGroupBox("添加新配置项")
        add_layout = QHBoxLayout()
        self.new_key = QLineEdit()
        self.new_key.setPlaceholderText("配置键")
        self.new_val = QLineEdit()
        self.new_val.setPlaceholderText("值")
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(lambda: self.add_new_property(grid, add_group))
        add_layout.addWidget(QLabel("键:"))
        add_layout.addWidget(self.new_key)
        add_layout.addWidget(QLabel("值:"))
        add_layout.addWidget(self.new_val)
        add_layout.addWidget(add_btn)
        add_group.setLayout(add_layout)
        grid.addWidget(add_group, row, 0, 1, 2)

        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(lambda: self.save_properties_file(dialog))
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        dialog.exec()

    def load_properties_file(self):
        props = {}
        if self.properties_file.exists():
            with open(self.properties_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        props[k.strip()] = v.strip()
        return props

    def add_new_property(self, grid, add_group):
        key = self.new_key.text().strip()
        val = self.new_val.text().strip()
        if key and val:
            if key in self.prop_edits:
                QMessageBox.warning(self, "提示", "配置项已存在")
                return
            row = grid.rowCount()
            cn = self.PROPERTY_TRANSLATIONS.get(key, key)
            label = QLabel(f"{cn}\n({key})")
            grid.addWidget(label, row, 0, Qt.AlignLeft)
            edit = QLineEdit(val)
            grid.addWidget(edit, row, 1)
            self.prop_edits[key] = edit
            grid.removeWidget(add_group)
            grid.addWidget(add_group, row + 1, 0, 1, 2)
            self.new_key.clear()
            self.new_val.clear()
            self.log(f"已添加配置项: {key}", "info")
        else:
            QMessageBox.warning(self, "提示", "请填写键和值")

    def save_properties_file(self, dialog):
        try:
            new_props = {k: edit.text().strip() for k, edit in self.prop_edits.items()}
            with open(self.properties_file, 'w', encoding='utf-8') as f:
                f.write("#Minecraft server properties\n")
                f.write(f"#{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for k, v in sorted(new_props.items()):
                    f.write(f"{k}={v}\n")
            self.log("server.properties 已更新", "success")
            dialog.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    # ===================== 工具 =====================
    def clear_console(self):
        self.console.clear()

    # ===================== 关闭事件 =====================
    def closeEvent(self, event):
        if self.server_running:
            reply = QMessageBox.question(
                self, "确认退出",
                "服务器正在运行，确定退出？\n退出前会自动保存并停止。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.stop_server()
                QTimer.singleShot(2000, self.close)
                event.ignore()
            else:
                event.ignore()
        else:
            if self.stdout_reader:
                self.stdout_reader.stop()
                self.stdout_reader.wait()
            event.accept()


# ===================== 启动 =====================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QMainWindow { background-color: #1e1e1e; }
        QDialog { background-color: #1e1e1e; color: #d4d4d4; }
    """)
    window = ServerManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()