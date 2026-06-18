#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog, filedialog

# -------------------------- 控制台高亮 (Tkinter Text 标签) --------------------------
def setup_console_tags(console_widget):
    """为控制台 Text 组件配置颜色标签"""
    console_widget.tag_configure("error", foreground="#f48771")
    console_widget.tag_configure("success", foreground="#6a9955")
    console_widget.tag_configure("warning", foreground="#dcdcaa")
    console_widget.tag_configure("info", foreground="#9cdcfe")
    console_widget.tag_configure("default", foreground="#d4d4d4")
    console_widget.tag_configure("timestamp", foreground="gray")


# -------------------------- 更多工具窗口 --------------------------
class ToolsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("更多工具")
        self.geometry("400x350")
        self.resizable(False, False)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        btn_clear = ttk.Button(frame, text="清除控制台", command=self.parent.clear_console)
        btn_clear.pack(fill="x", pady=2)

        btn_edit_cmd = ttk.Button(frame, text="编辑快捷命令", command=self.parent.edit_commands)
        btn_edit_cmd.pack(fill="x", pady=2)

        btn_props = ttk.Button(frame, text="⚙️ 服务器配置", command=self.parent.edit_server_properties)
        btn_props.pack(fill="x", pady=2)

        btn_player = ttk.Button(frame, text="🎮 玩家&玩具", command=self.parent.open_player_window)
        btn_player.pack(fill="x", pady=2)

        btn_plugin = ttk.Button(frame, text="📦 插件管理", command=self.parent.open_plugin_window)
        btn_plugin.pack(fill="x", pady=2)

        btn_lyt = ttk.Button(frame, text="🎮 LYT IT 联机房间", command=self.parent.run_lyt_it_plugin)
        btn_lyt.pack(fill="x", pady=2)


# -------------------------- 主窗口 --------------------------
class MinecraftServerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Minecraft 服务器管理器")
        self.geometry("1200x800")

        # 服务器进程相关
        self.process = None
        self.server_running = False
        self.process_stdout_thread = None
        self.process_stderr_thread = None
        self.stop_event = threading.Event()

        # 配置文件路径
        self.server_path = Path.cwd()
        self.jar_file = self.server_path / "server.jar"
        self.config_file = self.server_path / "quick_commands.json"
        self.properties_file = self.server_path / "server.properties"
        self.plugins_dir = self.server_path / "Plugins_xiaotu"

        # 加载快捷命令
        self.quick_commands = self.load_quick_commands()

        # 子窗口引用
        self.player_window = None
        self.plugin_window = None
        self.tools_window = None

        # 创建 UI
        self.setup_ui()

        # 定时检查进程状态
        self.after(500, self.check_process_status)

    # -------------------------- UI 构建 --------------------------
    def setup_ui(self):
        # 主框架，分为三部分：控制栏、控制台区域、快捷命令面板
        main_panel = ttk.Frame(self)
        main_panel.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- 控制栏 ----
        control_frame = ttk.LabelFrame(main_panel, text="服务器控制")
        control_frame.pack(fill="x", pady=(0, 5))

        # 第一行：服务端文件选择
        row1 = ttk.Frame(control_frame)
        row1.pack(fill="x", padx=5, pady=2)
        ttk.Label(row1, text="服务端文件:").pack(side="left")
        self.jar_path_var = tk.StringVar(value=str(self.jar_file))
        jar_entry = ttk.Entry(row1, textvariable=self.jar_path_var, width=40)
        jar_entry.pack(side="left", padx=5)
        ttk.Button(row1, text="浏览", command=self.browse_jar).pack(side="left")

        # 第二行：内存设置 + 按钮
        row2 = ttk.Frame(control_frame)
        row2.pack(fill="x", padx=5, pady=2)
        ttk.Label(row2, text="最小内存:").pack(side="left")
        self.ram_min_combo = ttk.Combobox(row2, values=["512M", "1G", "2G", "4G", "8G"], width=5)
        self.ram_min_combo.set("1G")
        self.ram_min_combo.pack(side="left", padx=(0, 10))

        ttk.Label(row2, text="最大内存:").pack(side="left")
        self.ram_max_combo = ttk.Combobox(row2, values=["1G", "2G", "4G", "8G", "16G"], width=5)
        self.ram_max_combo.set("2G")
        self.ram_max_combo.pack(side="left", padx=(0, 10))

        self.start_btn = ttk.Button(row2, text="启动服务器", command=self.start_server)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(row2, text="停止服务器", command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="left", padx=2)
        self.save_btn = ttk.Button(row2, text="保存世界", command=self.save_world, state="disabled")
        self.save_btn.pack(side="left", padx=2)
        ttk.Button(row2, text="🔧 更多工具", command=self.open_tools_window).pack(side="left", padx=2)

        # ---- 控制台区域 ----
        console_frame = ttk.LabelFrame(main_panel, text="服务器控制台")
        console_frame.pack(fill="both", expand=True, pady=5)

        self.console = scrolledtext.ScrolledText(console_frame, font=("Consolas", 10), wrap="word")
        self.console.pack(fill="both", expand=True)
        self.console.config(state="normal")
        setup_console_tags(self.console)

        # 命令输入行
        cmd_frame = ttk.Frame(console_frame)
        cmd_frame.pack(fill="x", pady=(2, 0))
        ttk.Label(cmd_frame, text="命令:").pack(side="left")
        self.cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_var)
        cmd_entry.pack(side="left", fill="x", expand=True, padx=5)
        cmd_entry.bind("<Return>", lambda e: self.send_command())
        ttk.Button(cmd_frame, text="发送", command=self.send_command).pack(side="left")

        # ---- 快捷命令面板 ----
        cmd_panel_frame = ttk.LabelFrame(main_panel, text="快捷命令")
        cmd_panel_frame.pack(fill="x", pady=(5, 0))
        self.cmd_panel_inner = ttk.Frame(cmd_panel_frame)
        self.cmd_panel_inner.pack(fill="x", padx=5, pady=2)
        self.refresh_quick_commands()

        # ---- 状态栏 ----
        status_frame = ttk.Frame(self)
        status_frame.pack(side="bottom", fill="x")
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side="left")
        self.server_status_label = ttk.Label(status_frame, text="● 服务器未运行", foreground="red")
        self.server_status_label.pack(side="right")
        self.update_server_status(False)

    # -------------------------- 更多工具窗口 --------------------------
    def open_tools_window(self):
        if self.tools_window is not None and self.tools_window.winfo_exists():
            self.tools_window.lift()
            return
        self.tools_window = ToolsWindow(self)

    # -------------------------- 运行 LYT IT 插件 --------------------------
    def run_lyt_it_plugin(self):
        plugin_path = self.plugins_dir / "lyt_it_plugin_GUI.py"
        if not plugin_path.exists():
            messagebox.showwarning("提示", f"未找到 LYT IT 插件:\n{plugin_path}\n请确保文件在 Plugins_xiaotu 目录下。")
            return
        self.log_message(f"正在启动 LYT IT 联机房间创建器: {plugin_path}", "info")
        try:
            python_exe = sys.executable
            subprocess.Popen([python_exe, str(plugin_path)], cwd=str(self.plugins_dir))
            self.log_message("LYT IT 联机房间创建器已启动", "success")
        except Exception as e:
            self.log_message(f"启动失败: {e}", "error")
            messagebox.showerror("错误", f"启动 LYT IT 插件失败:\n{e}")

    # -------------------------- 快捷命令 --------------------------
    def refresh_quick_commands(self):
        # 清空现有按钮
        for child in self.cmd_panel_inner.winfo_children():
            child.destroy()

        refresh_btn = ttk.Button(self.cmd_panel_inner, text="🔄 刷新", command=self.refresh_quick_commands)
        refresh_btn.pack(side="left", padx=2)

        for name, info in self.quick_commands.items():
            if name == "help":
                continue
            btn = ttk.Button(self.cmd_panel_inner, text=f"/{name}", command=lambda n=name: self.show_command_dialog(n))
            btn.pack(side="left", padx=2)

    def show_command_dialog(self, cmd_name):
        if not self.server_running:
            messagebox.showwarning("警告", "服务器未运行")
            return
        info = self.quick_commands[cmd_name]
        if info.get('command') and '{args}' in info['command']:
            args = simpledialog.askstring(
                "执行命令",
                f"{info['description']}\n格式: {info['command'].replace('{args}', '<参数>')}\n请输入参数:",
                parent=self
            )
            if args is not None:
                args = args.strip()
                if args:
                    self.execute_quick_command(cmd_name, args)
                else:
                    messagebox.showwarning("警告", "请输入参数")
        else:
            self.execute_quick_command(cmd_name)

    def execute_quick_command(self, cmd_name, args=""):
        if cmd_name not in self.quick_commands:
            self.log_message(f"未知命令: {cmd_name}", "error")
            return
        info = self.quick_commands[cmd_name]
        if info['command']:
            if '{args}' in info['command']:
                if not args:
                    messagebox.showinfo("提示", f"命令 /{cmd_name} 需要参数")
                    return
                full = info['command'].format(args=args)
            else:
                full = info['command']
            self.send_to_server(full)
        elif cmd_name == "help":
            self.show_help()

    def show_help(self):
        txt = "\n=== 快捷命令 ===\n"
        for n, i in self.quick_commands.items():
            if n != "help":
                txt += f"/{n:<12} - {i['description']}\n"
        self.log_message(txt, "info")

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
            except:
                pass
        else:
            self.save_quick_commands(default)
        return default

    def save_quick_commands(self, cmds):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(cmds, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log_message(f"保存配置失败: {e}", "error")

    def edit_commands(self):
        if self.config_file.exists():
            if sys.platform == "win32":
                os.startfile(str(self.config_file))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.config_file)])
            else:
                subprocess.run(["xdg-open", str(self.config_file)])
        else:
            self.save_quick_commands(self.quick_commands)
            self.edit_commands()

    # -------------------------- 服务器控制 --------------------------
    def browse_jar(self):
        path = filedialog.askopenfilename(
            title="选择服务端 JAR",
            initialdir=str(self.server_path),
            filetypes=[("Java文件", "*.jar")]
        )
        if path:
            self.jar_path_var.set(path)
            self.jar_file = Path(path)

    def start_server(self):
        if self.server_running:
            messagebox.showwarning("警告", "服务器已在运行")
            return
        jar = Path(self.jar_path_var.get())
        if not jar.exists():
            messagebox.showerror("错误", f"找不到服务端文件: {jar}")
            return
        eula = jar.parent / "eula.txt"
        if not eula.exists() or "eula=false" in eula.read_text().lower():
            ret = messagebox.askquestion("接受 EULA", "需要接受 Minecraft EULA 才能启动。\n是否接受？")
            if ret != "yes":
                return
            eula.write_text("eula=true")
            self.log_message("已接受 EULA", "success")

        cmd = [
            "java",
            f"-Xms{self.ram_min_combo.get()}",
            f"-Xmx{self.ram_max_combo.get()}",
            "-jar", str(jar), "nogui"
        ]

        self.log_message(f"启动命令: {' '.join(cmd)}", "info")
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(jar.parent),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
        except Exception as e:
            self.log_message(f"启动失败: {e}", "error")
            return

        self.server_running = True
        self.update_server_status(True)
        self.log_message("服务器启动成功！", "success")

        # 启动读取线程
        self.stop_event.clear()
        self.process_stdout_thread = threading.Thread(target=self.read_stdout, daemon=True)
        self.process_stderr_thread = threading.Thread(target=self.read_stderr, daemon=True)
        self.process_stdout_thread.start()
        self.process_stderr_thread.start()

    def read_stdout(self):
        while not self.stop_event.is_set() and self.process and self.process.poll() is None:
            line = self.process.stdout.readline()
            if not line:
                break
            if line.strip():
                self.after(0, lambda l=line: self.log_message(l.strip()))
        # 进程结束处理
        self.after(0, self.process_finished)

    def read_stderr(self):
        while not self.stop_event.is_set() and self.process and self.process.poll() is None:
            line = self.process.stderr.readline()
            if not line:
                break
            if line.strip():
                self.after(0, lambda l=line: self.log_message(l.strip(), "error"))

    def process_finished(self):
        if self.process is not None:
            exit_code = self.process.poll()
            if exit_code is not None:
                self.server_running = False
                self.update_server_status(False)
                self.log_message(f"服务器进程已结束，退出码: {exit_code}", "warning")
                self.process = None

    def check_process_status(self):
        # 定期检查进程是否还在运行
        if self.process is not None:
            poll = self.process.poll()
            if poll is not None and self.server_running:
                self.server_running = False
                self.update_server_status(False)
                self.log_message("服务器进程意外结束", "error")
                self.process = None
        self.after(500, self.check_process_status)

    def log_message(self, msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.config(state="normal")
        self.console.insert("end", f"[{timestamp}] ", ("timestamp",))
        tag = level if level in ("error", "success", "warning", "info") else "default"
        self.console.insert("end", msg + "\n", (tag,))
        self.console.see("end")
        self.console.config(state="disabled")

    def send_command(self):
        if not self.server_running:
            messagebox.showwarning("警告", "服务器未运行")
            return
        cmd = self.cmd_var.get().strip()
        if not cmd:
            return
        if cmd.startswith('/'):
            parts = cmd[1:].split(maxsplit=1)
            name = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            self.execute_quick_command(name, arg)
        else:
            self.send_to_server(cmd)
        self.cmd_var.set("")

    def send_to_server(self, cmd):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                self.log_message(f">>> {cmd}", "info")
            except Exception as e:
                self.log_message(f"发送命令失败: {e}", "error")
        else:
            self.log_message("无法发送命令：进程未运行", "error")

    def stop_server(self):
        if not self.server_running:
            return
        ret = messagebox.askquestion("确认", "确定要停止服务器吗？")
        if ret == "yes":
            self.log_message("正在停止服务器...", "warning")
            self.send_to_server("stop")
            # 30秒后强制终止
            self.after(30000, self.force_stop)

    def force_stop(self):
        if self.process and self.process.poll() is None:
            self.log_message("服务器未响应，强制终止", "error")
            self.process.terminate()
            self.process.kill()
            self.stop_event.set()

    def save_world(self):
        if self.server_running:
            self.send_to_server("save-all")
            self.log_message("正在保存世界...", "info")
        else:
            messagebox.showwarning("警告", "服务器未运行")

    def clear_console(self):
        self.console.config(state="normal")
        self.console.delete(1.0, "end")
        self.console.config(state="disabled")

    def update_server_status(self, running):
        self.server_running = running
        if running:
            self.server_status_label.config(text="● 服务器运行中", foreground="green")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.save_btn.config(state="normal")
        else:
            self.server_status_label.config(text="● 服务器未运行", foreground="red")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.save_btn.config(state="disabled")

    # -------------------------- 玩家&玩具窗口 --------------------------
    def open_player_window(self):
        if self.player_window is not None and self.player_window.winfo_exists():
            self.player_window.lift()
            return
        self.player_window = tk.Toplevel(self)
        self.player_window.title("玩家 & 玩具")
        self.player_window.geometry("700x500")

        main_frame = ttk.Frame(self.player_window)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 左右分割
        left_frame = ttk.LabelFrame(main_frame, text="在线玩家")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.player_listbox = tk.Listbox(left_frame)
        self.player_listbox.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="刷新玩家列表", command=self.refresh_player_list).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="显示玩家名", command=self.show_player_name).pack(side="left", padx=2)

        right_frame = ttk.LabelFrame(main_frame, text="玩具列表")
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.toy_listbox = tk.Listbox(right_frame)
        self.toy_listbox.pack(fill="both", expand=True)
        toys = ["钻石剑", "三叉戟", "烟花火箭", "鞘翅", "不死图腾", "附魔金苹果"]
        for toy in toys:
            self.toy_listbox.insert("end", toy)

        ttk.Button(right_frame, text="给予选中玩具", command=self.give_selected_toy).pack(pady=2)

        self.refresh_player_list()

    def refresh_player_list(self):
        if not self.server_running:
            self.player_listbox.delete(0, "end")
            self.player_listbox.insert("end", "（服务器未运行）")
            return
        self.send_to_server("list")
        # 延迟解析
        self.after(800, self.parse_player_list)

    def parse_player_list(self):
        content = self.console.get(1.0, "end")
        lines = content.splitlines()
        pattern = re.compile(r"There are \d+ of a max of \d+ players online: (.*)")
        players = []
        for line in reversed(lines):
            m = pattern.search(line)
            if m and m.group(1).strip():
                players = [p.strip() for p in m.group(1).split(',')]
                break
        self.player_listbox.delete(0, "end")
        if players:
            for p in players:
                self.player_listbox.insert("end", p)
        else:
            self.player_listbox.insert("end", "（暂无玩家在线）")

    def show_player_name(self):
        sel = self.player_listbox.curselection()
        if sel:
            player = self.player_listbox.get(sel[0])
            if player not in ("（服务器未运行）", "（暂无玩家在线）"):
                messagebox.showinfo("玩家名", f"玩家：{player}")
            else:
                messagebox.showwarning("提示", "请先选择一个玩家")
        else:
            messagebox.showwarning("提示", "请先选择一个玩家")

    def give_selected_toy(self):
        player_sel = self.player_listbox.curselection()
        toy_sel = self.toy_listbox.curselection()
        if not player_sel or not toy_sel:
            messagebox.showwarning("提示", "请选择一个玩家和一个玩具")
            return
        player = self.player_listbox.get(player_sel[0])
        toy = self.toy_listbox.get(toy_sel[0])
        if player in ("（服务器未运行）", "（暂无玩家在线）"):
            messagebox.showwarning("提示", "请选择有效的玩家")
            return
        self.send_to_server(f"say 给予 {player} 一个 {toy}")
        self.log_message(f"已尝试给予玩家 {player} 玩具：{toy}", "info")

    # -------------------------- 插件管理窗口 --------------------------
    def open_plugin_window(self):
        if self.plugin_window is not None and self.plugin_window.winfo_exists():
            self.plugin_window.lift()
            return
        self.plugin_window = tk.Toplevel(self)
        self.plugin_window.title("插件管理 (EXE + PY)")
        self.plugin_window.geometry("900x600")

        main_frame = ttk.Frame(self.plugin_window)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 工具栏
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        self.plugin_dir_label = ttk.Label(toolbar, text=f"插件目录: {self.plugins_dir}")
        self.plugin_dir_label.pack(side="left")
        ttk.Button(toolbar, text="🔄 刷新", command=self.refresh_plugin_list).pack(side="right", padx=2)
        ttk.Button(toolbar, text="📁 打开目录", command=self.open_plugins_folder).pack(side="right", padx=2)
        ttk.Button(toolbar, text="📥 安装插件", command=self.install_plugin).pack(side="right", padx=2)

        self.plugin_status_label = ttk.Label(main_frame, text="")
        self.plugin_status_label.pack(fill="x")

        # Treeview 显示插件
        self.plugin_tree = ttk.Treeview(main_frame, columns=("filename", "type", "size", "mtime", "action"), show="tree")
        self.plugin_tree.heading("#0", text="📦")
        self.plugin_tree.heading("filename", text="文件名")
        self.plugin_tree.heading("type", text="类型")
        self.plugin_tree.heading("size", text="大小")
        self.plugin_tree.heading("mtime", text="修改时间")
        self.plugin_tree.heading("action", text="操作")
        self.plugin_tree.column("#0", width=40)
        self.plugin_tree.column("filename", width=250)
        self.plugin_tree.column("type", width=60)
        self.plugin_tree.column("size", width=80)
        self.plugin_tree.column("mtime", width=150)
        self.plugin_tree.column("action", width=80)

        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.plugin_tree.yview)
        self.plugin_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.plugin_tree.pack(fill="both", expand=True)

        # 双击运行
        self.plugin_tree.bind("<Double-1>", self.run_selected_plugin)
        # 右键菜单
        self.plugin_tree.bind("<Button-3>", self.show_plugin_context_menu)

        # 底部提示
        tip_label = ttk.Label(main_frame, text="💡 提示：支持 .exe 和 .py 插件 | 双击运行 | 右键管理")
        tip_label.pack(fill="x", pady=(5, 0))

        self.refresh_plugin_list()

    def refresh_plugin_list(self):
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

        exe_files = list(self.plugins_dir.glob("*.exe"))
        py_files = list(self.plugins_dir.glob("*.py"))
        all_plugins = [(f, "EXE") for f in exe_files] + [(f, "PY") for f in py_files]
        if not all_plugins:
            self.plugin_tree.insert("", "end", text="📁", values=("暂无插件", "", "", "", ""))
            return

        for path, ptype in sorted(all_plugins, key=lambda x: x[0].name):
            size = self.get_file_size(path)
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            icon = "⚡" if ptype == "EXE" else "🐍"
            item_id = self.plugin_tree.insert("", "end", text=icon, values=(path.name, ptype, size, mtime, "▶ 运行"))
            # 存储路径
            self.plugin_tree.set(item_id, "filename", path.name)
            self.plugin_tree.set(item_id, "type", ptype)
            self.plugin_tree.set(item_id, "size", size)
            self.plugin_tree.set(item_id, "mtime", mtime)
            self.plugin_tree.set(item_id, "action", "▶ 运行")
            # 关联文件路径
            self.plugin_tree.item(item_id, tags=(str(path),))

        self.log_message(f"插件列表已刷新，共 {len(all_plugins)} 个插件", "info")

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
        if sys.platform == "win32":
            os.startfile(str(self.plugins_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(self.plugins_dir)])
        else:
            subprocess.run(["xdg-open", str(self.plugins_dir)])

    def install_plugin(self):
        fn = filedialog.askopenfilename(
            title="选择插件文件",
            initialdir=str(self.server_path),
            filetypes=[("可执行程序", "*.exe"), ("Python脚本", "*.py"), ("所有文件", "*.*")]
        )
        if not fn:
            return
        src = Path(fn)
        if src.suffix.lower() not in ('.exe', '.py'):
            messagebox.showwarning("警告", "请选择 .exe 或 .py 文件")
            return
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        dst = self.plugins_dir / src.name
        if dst.exists():
            ret = messagebox.askquestion("确认", f"文件 {src.name} 已存在，覆盖？")
            if ret != "yes":
                return
        try:
            shutil.copy2(src, dst)
            self.log_message(f"已安装插件: {src.name}", "success")
            self.refresh_plugin_list()
            messagebox.showinfo("成功", f"插件 {src.name} 已安装")
        except Exception as e:
            messagebox.showerror("错误", f"安装失败: {e}")

    def delete_selected_plugin(self):
        item = self.plugin_tree.selection()
        if not item:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        item = item[0]
        name = self.plugin_tree.item(item, "values")[0]
        if name == "暂无插件":
            return
        ret = messagebox.askquestion("确认删除", f"确定删除 {name} 吗？")
        if ret != "yes":
            return
        try:
            (self.plugins_dir / name).unlink()
            self.log_message(f"已删除插件: {name}", "success")
            self.refresh_plugin_list()
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")

    def rename_selected_plugin(self):
        item = self.plugin_tree.selection()
        if not item:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        item = item[0]
        old_name = self.plugin_tree.item(item, "values")[0]
        if old_name == "暂无插件":
            return
        new_name = simpledialog.askstring("重命名", "新文件名:", initialvalue=old_name)
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        old_ext = Path(old_name).suffix
        new_ext = Path(new_name).suffix
        if not new_ext and old_ext:
            new_name += old_ext
        old_path = self.plugins_dir / old_name
        new_path = self.plugins_dir / new_name
        if new_path.exists():
            messagebox.showwarning("警告", "目标文件已存在")
            return
        try:
            old_path.rename(new_path)
            self.log_message(f"重命名: {old_name} -> {new_name}", "success")
            self.refresh_plugin_list()
        except Exception as e:
            messagebox.showerror("错误", f"重命名失败: {e}")

    def run_selected_plugin(self, event=None):
        item = self.plugin_tree.selection()
        if not item:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        item = item[0]
        values = self.plugin_tree.item(item, "values")
        name = values[0]
        ptype = values[1]
        if name == "暂无插件":
            return
        path = self.plugins_dir / name
        if not path.exists():
            messagebox.showerror("错误", "文件不存在")
            return

        self.log_message(f"运行插件: {name} (类型: {ptype})", "info")
        try:
            if ptype == "EXE":
                if sys.platform == "win32":
                    subprocess.Popen([str(path)], shell=True, cwd=str(self.plugins_dir),
                                     creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen([str(path)], cwd=str(self.plugins_dir))
                self.log_message(f"插件 {name} 已在后台启动", "success")
            else:  # PY
                python_exe = sys.executable
                self.log_message(f"正在执行 Python 脚本: {name}", "info")
                def run_py():
                    try:
                        result = subprocess.run(
                            [python_exe, str(path)],
                            cwd=str(self.plugins_dir),
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.stdout:
                            self.after(0, lambda: self.log_message(f"[插件输出]\n{result.stdout}", "info"))
                        if result.stderr:
                            self.after(0, lambda: self.log_message(f"[插件错误]\n{result.stderr}", "error"))
                        if result.returncode == 0:
                            self.after(0, lambda: self.log_message(f"插件 {name} 执行完成", "success"))
                        else:
                            self.after(0, lambda: self.log_message(f"插件 {name} 返回非零代码: {result.returncode}", "warning"))
                    except subprocess.TimeoutExpired:
                        self.after(0, lambda: self.log_message(f"插件 {name} 执行超时（60秒）", "error"))
                threading.Thread(target=run_py, daemon=True).start()
            self.plugin_status_label.config(text=f"✅ 已启动: {name}")
            self.after(3000, lambda: self.plugin_status_label.config(text=""))
        except Exception as e:
            self.log_message(f"运行失败: {e}", "error")
            messagebox.showerror("错误", f"运行失败:\n{e}")

    def open_selected_plugin_location(self):
        item = self.plugin_tree.selection()
        if item:
            values = self.plugin_tree.item(item[0], "values")
            name = values[0]
            if name != "暂无插件":
                p = self.plugins_dir / name
                if p.exists():
                    if sys.platform == "win32":
                        os.startfile(str(p.parent))
                    elif sys.platform == "darwin":
                        subprocess.run(["open", str(p.parent)])
                    else:
                        subprocess.run(["xdg-open", str(p.parent)])
                    return
        self.open_plugins_folder()

    def show_plugin_context_menu(self, event):
        item = self.plugin_tree.identify_row(event.y)
        if not item:
            return
        self.plugin_tree.selection_set(item)
        menu = tk.Menu(self.plugin_window, tearoff=0)
        menu.add_command(label="运行插件", command=self.run_selected_plugin)
        menu.add_separator()
        menu.add_command(label="删除插件", command=self.delete_selected_plugin)
        menu.add_command(label="重命名", command=self.rename_selected_plugin)
        menu.add_separator()
        menu.add_command(label="在文件管理器中显示", command=self.open_selected_plugin_location)
        menu.post(event.x_root, event.y_root)

    # -------------------------- server.properties 编辑器 --------------------------
    PROPERTY_TRANSLATIONS = {
        "server-port": "服务器端口", "server-ip": "服务器IP地址", "online-mode": "正版验证",
        "max-players": "最大玩家数", "view-distance": "视野距离", "gamemode": "默认游戏模式",
        "difficulty": "游戏难度", "level-name": "世界名称", "level-seed": "世界种子",
        "allow-flight": "允许飞行", "enable-command-block": "启用命令方块", "motd": "服务器欢迎语",
        "white-list": "白名单", "pvp": "PVP", "hardcore": "极限模式"
    }

    def get_chinese_property_name(self, key):
        return self.PROPERTY_TRANSLATIONS.get(key, key)

    def edit_server_properties(self):
        if not self.properties_file.exists():
            self.properties_file.write_text("#Minecraft server properties\n", encoding='utf-8')
            self.log_message("已创建默认 server.properties", "info")

        props = self.load_properties_file()
        dlg = tk.Toplevel(self)
        dlg.title("服务器配置编辑")
        dlg.geometry("900x700")

        main_frame = ttk.Frame(dlg)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 保存所有编辑框
        self.prop_edits = {}

        # 填充配置项
        row = 0
        for key, val in sorted(props.items()):
            cn = self.get_chinese_property_name(key)
            label_text = f"{cn}\n({key})"
            ttk.Label(scrollable_frame, text=label_text).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            edit = ttk.Entry(scrollable_frame, width=40)
            edit.insert(0, val)
            edit.grid(row=row, column=1, padx=5, pady=2)
            self.prop_edits[key] = edit
            row += 1

        # 添加新配置项区域
        add_frame = ttk.LabelFrame(scrollable_frame, text="添加新配置项")
        add_frame.grid(row=row, column=0, columnspan=2, pady=10, sticky="ew")
        add_inner = ttk.Frame(add_frame)
        add_inner.pack(fill="x", padx=5, pady=5)
        ttk.Label(add_inner, text="配置键:").pack(side="left")
        self.new_key_entry = ttk.Entry(add_inner, width=15)
        self.new_key_entry.pack(side="left", padx=2)
        ttk.Label(add_inner, text="值:").pack(side="left")
        self.new_val_entry = ttk.Entry(add_inner, width=15)
        self.new_val_entry.pack(side="left", padx=2)
        ttk.Button(add_inner, text="➕ 添加", command=lambda: self.add_new_property(scrollable_frame)).pack(side="left", padx=2)

        # 底部按钮
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="保存", command=lambda: self.save_properties_file(dlg)).pack(side="right", padx=2)
        ttk.Button(btn_frame, text="取消", command=dlg.destroy).pack(side="right", padx=2)

        ttk.Label(dlg, text="💡 提示：修改后需重启服务器", foreground="#9cdcfe").pack(pady=(0, 5))

    def add_new_property(self, parent_frame):
        key = self.new_key_entry.get().strip()
        val = self.new_val_entry.get().strip()
        if key and val:
            if key in self.prop_edits:
                messagebox.showwarning("提示", "配置项已存在")
                return
            cn = self.get_chinese_property_name(key)
            label_text = f"{cn}\n({key})"
            # 在添加组之前插入新行
            add_group = parent_frame.grid_slaves(row=parent_frame.grid_size()[1]-1, column=0)[0]
            row = parent_frame.grid_size()[1] - 1  # 添加组所在行
            ttk.Label(parent_frame, text=label_text).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            edit = ttk.Entry(parent_frame, width=40)
            edit.grid(row=row, column=1, padx=5, pady=2)
            self.prop_edits[key] = edit
            # 将添加组下移一行
            add_group.grid(row=row+1, column=0, columnspan=2, pady=10, sticky="ew")
            self.new_key_entry.delete(0, "end")
            self.new_val_entry.delete(0, "end")
            self.log_message(f"已添加配置项: {key}", "info")
        else:
            messagebox.showwarning("提示", "请填写键和值")

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

    def save_properties_file(self, dlg):
        try:
            new_props = {k: edit.get().strip() for k, edit in self.prop_edits.items()}
            with open(self.properties_file, 'w', encoding='utf-8') as f:
                f.write("#Minecraft server properties\n")
                f.write(f"#{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for k, v in sorted(new_props.items()):
                    f.write(f"{k}={v}\n")
            self.log_message("server.properties 已更新", "success")
            dlg.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    # -------------------------- 关闭事件 --------------------------
    def on_closing(self):
        if self.server_running:
            ret = messagebox.askquestion("确认", "服务器正在运行，确定退出？\n退出前会自动保存并停止。")
            if ret == "yes":
                self.stop_server()
                self.after(2000, self.destroy)
            else:
                return
        else:
            self.destroy()


def main():
    app = MinecraftServerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
