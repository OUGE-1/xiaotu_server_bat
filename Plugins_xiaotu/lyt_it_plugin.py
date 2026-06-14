#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
插件名称: LYT IT - 联机房间创建器
功能: 点击按钮后进入 "lyt it" 目录并运行 main.exe --create，开放公网联机
"""

import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox


class LYTItPlugin:
    def __init__(self, app=None):
        self.app = app
        self.name = "LYT IT 联机房间"
        self.version = "1.0"

        # 获取主程序所在目录（兼容打包和未打包）
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path.cwd()

        self.lyt_dir = base_dir / "lyt it"
        self.exe_path = self.lyt_dir / "main.exe"

    def create_gui(self, parent):
        """在主界面中创建按钮（会被主程序自动调用）"""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=5)

        self.btn = ttk.Button(frame, text="🏠 创建房间", command=self.create_room, width=15)
        self.btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(frame, text="", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # 检查环境
        if not self.lyt_dir.exists():
            self.status_label.config(text="❌ 未找到 'lyt it' 目录", foreground="red")
        elif not self.exe_path.exists():
            self.status_label.config(text="❌ 未找到 main.exe", foreground="red")
        else:
            self.status_label.config(text="✅ 就绪")

        return frame

    def create_room(self):
        if not self.lyt_dir.exists():
            messagebox.showerror("错误", f"目录不存在:\n{self.lyt_dir}")
            return
        if not self.exe_path.exists():
            messagebox.showerror("错误", f"文件不存在:\n{self.exe_path}")
            return

        self.btn.config(state="disabled", text="⏳ 创建中...")
        self.status_label.config(text="正在创建房间...", foreground="orange")

        try:
            # Windows 命令: cd /d "lyt it" && main.exe --create
            cmd = f'cd /d "{self.lyt_dir}" && main.exe --create'
            subprocess.Popen(cmd, shell=True)
            self.status_label.config(text="✅ 房间已创建！", foreground="green")
            if self.app:
                self.app.log_message("LYT IT: 已执行创建房间命令", "success")
        except Exception as e:
            self.status_label.config(text="❌ 创建失败", foreground="red")
            messagebox.showerror("错误", f"执行失败:\n{e}")
        finally:
            # 3秒后恢复按钮
            def reset():
                self.btn.config(state="normal", text="🏠 创建房间")
                if self.status_label.cget("text") == "✅ 房间已创建！":
                    self.status_label.config(text="✅ 就绪")
            if self.app:
                self.app.root.after(3000, reset)
            else:
                import threading
                threading.Timer(3, reset).start()


def load_plugin(app):
    """主程序调用此函数加载插件"""
    plugin = LYTItPlugin(app)
    return plugin.create_gui