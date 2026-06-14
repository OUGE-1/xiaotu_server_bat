#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import json
import os
import sys
import threading
import queue
import re
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import shutil


class MinecraftServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft 服务器管理器")
        self.root.geometry("1000x800")
        self.root.resizable(True, True)

        # 服务器进程相关
        self.process = None
        self.server_running = False
        self.output_queue = queue.Queue()

        # 配置文件路径
        self.server_path = Path.cwd()
        self.jar_file = self.server_path / "server.jar"
        self.config_file = self.server_path / "quick_commands.json"
        self.properties_file = self.server_path / "server.properties"
        self.plugins_dir = self.server_path / "Plugins_xiaotu"

        # 加载配置
        self.quick_commands = self.load_quick_commands()

        # UI 组件
        self.player_listbox = None
        self.toy_listbox = None
        self.plugin_tree = None          # 统一插件树（支持 .exe 和 .py）
        self.player_window = None
        self.plugin_window = None

        self.setup_styles()
        self.create_widgets()
        self.process_output_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        self.colors = {
            'bg': '#2b2b2b',
            'fg': '#ffffff',
            'console_bg': '#1e1e1e',
            'console_fg': '#d4d4d4',
            'button_bg': '#3c3c3c',
            'button_fg': '#ffffff',
            'error': '#f48771',
            'success': '#6a9955',
            'warning': '#dcdcaa',
            'info': '#9cdcfe'
        }
        self.root.configure(bg=self.colors['bg'])

    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.create_control_panel(main_frame)
        self.create_console_panel(main_frame)
        self.create_quick_commands_panel(main_frame)
        self.create_status_bar()

    def create_control_panel(self, parent):
        control_frame = ttk.LabelFrame(parent, text="服务器控制", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 5))

        # 第一行：服务器设置
        settings_frame = ttk.Frame(control_frame)
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_frame, text="服务端文件:").pack(side=tk.LEFT, padx=(0, 5))
        self.jar_path_var = tk.StringVar(value=str(self.jar_file))
        ttk.Entry(settings_frame, textvariable=self.jar_path_var, width=40).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(settings_frame, text="浏览", command=self.browse_jar).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(settings_frame, text="最小内存:").pack(side=tk.LEFT, padx=(0, 5))
        self.ram_min_var = tk.StringVar(value="1G")
        ttk.Combobox(settings_frame, textvariable=self.ram_min_var, values=["512M", "1G", "2G", "4G", "8G"], width=6).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(settings_frame, text="最大内存:").pack(side=tk.LEFT, padx=(0, 5))
        self.ram_max_var = tk.StringVar(value="2G")
        ttk.Combobox(settings_frame, textvariable=self.ram_max_var, values=["1G", "2G", "4G", "8G", "16G"], width=6).pack(side=tk.LEFT)

        # 第二行：控制按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(button_frame, text="启动服务器", command=self.start_server, width=12)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(button_frame, text="停止服务器", command=self.stop_server, state=tk.DISABLED, width=12)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))

        self.save_button = ttk.Button(button_frame, text="保存世界", command=self.save_world, state=tk.DISABLED, width=12)
        self.save_button.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="清除控制台", command=self.clear_console, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="编辑快捷命令", command=self.edit_commands, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="⚙️ 服务器配置", command=self.edit_server_properties, width=12).pack(side=tk.LEFT, padx=(0, 5))

        # 独立窗口按钮
        ttk.Button(button_frame, text="🎮 玩家&玩具", command=self.open_player_window, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="📦 插件管理", command=self.open_plugin_window, width=12).pack(side=tk.LEFT)

    def create_console_panel(self, parent):
        console_frame = ttk.LabelFrame(parent, text="服务器控制台", padding=10)
        console_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.console_text = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD,
            bg=self.colors['console_bg'], fg=self.colors['console_fg'], font=("Consolas", 10), height=18)
        self.console_text.pack(fill=tk.BOTH, expand=True)

        self.console_text.tag_config("error", foreground=self.colors['error'])
        self.console_text.tag_config("success", foreground=self.colors['success'])
        self.console_text.tag_config("warning", foreground=self.colors['warning'])
        self.console_text.tag_config("info", foreground=self.colors['info'])

        input_frame = ttk.Frame(console_frame)
        input_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(input_frame, text="命令:").pack(side=tk.LEFT, padx=(0, 5))
        self.command_var = tk.StringVar()
        self.command_entry = ttk.Entry(input_frame, textvariable=self.command_var)
        self.command_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.command_entry.bind("<Return>", self.send_command)
        ttk.Button(input_frame, text="发送", command=self.send_command, width=10).pack(side=tk.RIGHT)

    def create_quick_commands_panel(self, parent):
        commands_frame = ttk.LabelFrame(parent, text="快捷命令", padding=10)
        commands_frame.pack(fill=tk.X)

        button_frame = ttk.Frame(commands_frame)
        button_frame.pack(fill=tk.X)

        self.command_buttons = {}
        self.refresh_quick_commands(button_frame)
        ttk.Button(button_frame, text="🔄 刷新", command=lambda: self.refresh_quick_commands(button_frame), width=10).pack(side=tk.RIGHT, padx=(5, 0))

    # ==================== 独立窗口：玩家&玩具 ====================
    def open_player_window(self):
        if self.player_window is not None and self.player_window.winfo_exists():
            self.player_window.lift()
            return
        self.player_window = tk.Toplevel(self.root)
        self.player_window.title("玩家 & 玩具")
        self.player_window.geometry("700x500")
        self.player_window.configure(bg=self.colors['bg'])
        self.player_window.protocol("WM_DELETE_WINDOW", self.close_player_window)

        main_frame = ttk.Frame(self.player_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 左侧：玩家列表
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        ttk.Label(left, text="在线玩家", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0,5))
        player_frame = ttk.Frame(left)
        player_frame.pack(fill=tk.BOTH, expand=True)
        self.player_listbox = tk.Listbox(player_frame, bg=self.colors['console_bg'], fg=self.colors['console_fg'])
        self.player_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(player_frame, orient=tk.VERTICAL, command=self.player_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.player_listbox['yscrollcommand'] = sb.set
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(btn_frame, text="刷新玩家列表", command=self.refresh_player_list).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="显示玩家名", command=self.show_player_name).pack(side=tk.LEFT, padx=5)

        # 右侧：玩具列表
        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        ttk.Label(right, text="玩具列表", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0,5))
        toy_frame = ttk.Frame(right)
        toy_frame.pack(fill=tk.BOTH, expand=True)
        self.toy_listbox = tk.Listbox(toy_frame, bg=self.colors['console_bg'], fg=self.colors['console_fg'])
        self.toy_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb2 = ttk.Scrollbar(toy_frame, orient=tk.VERTICAL, command=self.toy_listbox.yview)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.toy_listbox['yscrollcommand'] = sb2.set
        self.toys = ["钻石剑", "三叉戟", "烟花火箭", "鞘翅", "不死图腾", "附魔金苹果"]
        for toy in self.toys:
            self.toy_listbox.insert(tk.END, toy)
        toy_btn_frame = ttk.Frame(right)
        toy_btn_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(toy_btn_frame, text="给予选中玩具", command=self.give_selected_toy).pack(side=tk.LEFT)

        # 右键菜单
        self.player_context_menu = tk.Menu(self.player_window, tearoff=0)
        self.player_context_menu.add_command(label="显示玩家名", command=self.show_player_name)
        self.player_listbox.bind("<Button-3>", self.show_player_context_menu)

        self.refresh_player_list()

    def close_player_window(self):
        if self.player_window:
            self.player_window.destroy()
            self.player_window = None

    def show_player_context_menu(self, event):
        idx = self.player_listbox.nearest(event.y)
        if idx >= 0:
            self.player_listbox.selection_clear(0, tk.END)
            self.player_listbox.selection_set(idx)
            self.player_context_menu.post(event.x_root, event.y_root)

    def show_player_name(self):
        sel = self.player_listbox.curselection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个玩家")
            return
        name = self.player_listbox.get(sel[0])
        messagebox.showinfo("玩家名", f"玩家：{name}")

    def refresh_player_list(self):
        if not self.server_running:
            self.player_listbox.delete(0, tk.END)
            self.player_listbox.insert(tk.END, "（服务器未运行）")
            return
        self.player_listbox.delete(0, tk.END)
        def fetch():
            if self.process and self.process.poll() is None:
                self.send_to_server("list")
                self.root.after(500, self._parse_player_list)
        threading.Thread(target=fetch, daemon=True).start()

    def _parse_player_list(self):
        content = self.console_text.get("end-10l", tk.END)
        m = re.search(r"There are \d+ of a max of \d+ players online: (.*)", content)
        if m and m.group(1).strip():
            players = [p.strip() for p in m.group(1).split(',')]
            self.player_listbox.delete(0, tk.END)
            for p in players:
                self.player_listbox.insert(tk.END, p)
        else:
            self.player_listbox.delete(0, tk.END)
            self.player_listbox.insert(tk.END, "（暂无玩家在线）")

    def give_selected_toy(self):
        player_sel = self.player_listbox.curselection()
        toy_sel = self.toy_listbox.curselection()
        if not player_sel or not toy_sel:
            messagebox.showwarning("提示", "请选择一个玩家和一个玩具")
            return
        player = self.player_listbox.get(player_sel[0])
        toy = self.toy_listbox.get(toy_sel[0])
        self.send_to_server(f"say 给予 {player} 一个 {toy}")
        self.log_message(f"已尝试给予玩家 {player} 玩具：{toy}", "info")

    # ==================== 独立窗口：插件管理（支持 .exe 和 .py） ====================
    def open_plugin_window(self):
        if self.plugin_window is not None and self.plugin_window.winfo_exists():
            self.plugin_window.lift()
            return
        self.plugin_window = tk.Toplevel(self.root)
        self.plugin_window.title("插件管理 (EXE + PY)")
        self.plugin_window.geometry("850x550")
        self.plugin_window.configure(bg=self.colors['bg'])
        self.plugin_window.protocol("WM_DELETE_WINDOW", self.close_plugin_window)

        main = ttk.Frame(self.plugin_window)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        toolbar = ttk.Frame(main)
        toolbar.pack(fill=tk.X, pady=(0,5))
        ttk.Label(toolbar, text=f"插件目录: {self.plugins_dir}", foreground=self.colors['info']).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="🔄 刷新", command=self.refresh_plugin_list, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="📁 打开目录", command=self.open_plugins_folder, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="📥 安装插件", command=self.install_plugin, width=10).pack(side=tk.RIGHT, padx=5)

        # 表格框架
        table_frame = ttk.Frame(main)
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.create_plugin_table(table_frame)

        tip = ttk.Label(main, text="💡 提示：支持 .exe 和 .py 插件 | 双击运行 | 右键管理", foreground=self.colors['info'])
        tip.pack(pady=(5,0))

        self.refresh_plugin_list()

    def close_plugin_window(self):
        if self.plugin_window:
            self.plugin_window.destroy()
            self.plugin_window = None
            self.plugin_tree = None

    def create_plugin_table(self, parent):
        columns = ("文件名", "类型", "大小", "修改时间", "操作")
        self.plugin_tree = ttk.Treeview(parent, columns=columns, show="tree headings", height=18)
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.plugin_tree.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.plugin_tree.xview)
        self.plugin_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 正确：heading 中不加 width
        self.plugin_tree.heading("#0", text="📦", anchor=tk.W)
        self.plugin_tree.heading("文件名", text="文件名", anchor=tk.W)
        self.plugin_tree.heading("类型", text="类型", anchor=tk.CENTER)
        self.plugin_tree.heading("大小", text="大小", anchor=tk.CENTER)
        self.plugin_tree.heading("修改时间", text="修改时间", anchor=tk.W)
        self.plugin_tree.heading("操作", text="操作", anchor=tk.CENTER)

    # 宽度在 column 中设置
        self.plugin_tree.column("#0", width=40, minwidth=40, anchor=tk.CENTER)
        self.plugin_tree.column("文件名", width=300, minwidth=200, anchor=tk.W)
        self.plugin_tree.column("类型", width=60, minwidth=60, anchor=tk.CENTER)
        self.plugin_tree.column("大小", width=80, minwidth=80, anchor=tk.CENTER)
        self.plugin_tree.column("修改时间", width=150, minwidth=150, anchor=tk.W)
        self.plugin_tree.column("操作", width=80, minwidth=80, anchor=tk.CENTER)

        self.plugin_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # 右键菜单
        self.plugin_ctx_menu = tk.Menu(self.plugin_window, tearoff=0)
        self.plugin_ctx_menu.add_command(label="运行插件", command=self.run_selected_plugin)
        self.plugin_ctx_menu.add_separator()
        self.plugin_ctx_menu.add_command(label="删除插件", command=self.delete_selected_plugin)
        self.plugin_ctx_menu.add_command(label="重命名", command=self.rename_selected_plugin)
        self.plugin_ctx_menu.add_separator()
        self.plugin_ctx_menu.add_command(label="在文件管理器中显示", command=self.open_selected_plugin_location)
        self.plugin_tree.bind("<Button-3>", self.show_plugin_context_menu)
        self.plugin_tree.bind("<Double-1>", lambda e: self.run_selected_plugin())

    def refresh_plugin_list(self):
        if self.plugin_tree is None:
            return
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # 获取所有 .exe 和 .py 文件
        exe_files = list(self.plugins_dir.glob("*.exe"))
        py_files = list(self.plugins_dir.glob("*.py"))

        all_plugins = []
        for f in exe_files:
            all_plugins.append((f, "EXE"))
        for f in py_files:
            all_plugins.append((f, "PY"))

        if not all_plugins:
            self.plugin_tree.insert("", tk.END, text="📁", values=("暂无插件", "", "", "", ""))
            return

        for path, ptype in sorted(all_plugins, key=lambda x: x[0].name):
            size = self.get_file_size(path)
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            icon = "⚡" if ptype == "EXE" else "🐍"
            self.plugin_tree.insert("", tk.END, text=icon, values=(path.name, ptype, size, mtime, "▶ 运行"))

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
        if dst.exists() and not messagebox.askyesno("确认", f"文件 {src.name} 已存在，覆盖？"):
            return
        try:
            shutil.copy2(src, dst)
            self.log_message(f"已安装插件: {src.name}", "success")
            self.refresh_plugin_list()
            messagebox.showinfo("成功", f"插件 {src.name} 已安装")
        except Exception as e:
            messagebox.showerror("错误", f"安装失败: {e}")

    def delete_selected_plugin(self):
        sel = self.plugin_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        values = self.plugin_tree.item(sel[0], "values")
        if not values or values[0] == "暂无插件":
            return
        name = values[0]
        if not messagebox.askyesno("确认删除", f"确定删除 {name} 吗？"):
            return
        try:
            (self.plugins_dir / name).unlink()
            self.log_message(f"已删除插件: {name}", "success")
            self.refresh_plugin_list()
        except Exception as e:
            messagebox.showerror("错误", f"删除失败: {e}")

    def rename_selected_plugin(self):
        sel = self.plugin_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        values = self.plugin_tree.item(sel[0], "values")
        if not values or values[0] == "暂无插件":
            return
        old = values[0]
        dlg = tk.Toplevel(self.plugin_window)
        dlg.title("重命名")
        dlg.geometry("400x150")
        dlg.configure(bg=self.colors['bg'])
        dlg.transient(self.plugin_window)
        dlg.grab_set()
        ttk.Label(dlg, text="新文件名:").pack(pady=(20,5))
        var = tk.StringVar(value=old)
        entry = ttk.Entry(dlg, textvariable=var, width=40)
        entry.pack(pady=5, padx=20, fill=tk.X)
        entry.select_range(0, tk.END)
        entry.focus()
        def do_rename():
            new = var.get().strip()
            if not new:
                return
            # 保留原扩展名（如果用户没写则自动添加）
            old_ext = Path(old).suffix
            new_ext = Path(new).suffix
            if not new_ext and old_ext:
                new += old_ext
            old_path = self.plugins_dir / old
            new_path = self.plugins_dir / new
            if new_path.exists():
                messagebox.showwarning("警告", "目标文件已存在")
                return
            try:
                old_path.rename(new_path)
                self.log_message(f"重命名: {old} -> {new}", "success")
                self.refresh_plugin_list()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"重命名失败: {e}")
        btnf = ttk.Frame(dlg)
        btnf.pack(pady=20)
        ttk.Button(btnf, text="确定", command=do_rename, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btnf, text="取消", command=dlg.destroy, width=10).pack(side=tk.LEFT, padx=5)

    def run_selected_plugin(self):
        sel = self.plugin_tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个插件")
            return
        values = self.plugin_tree.item(sel[0], "values")
        if not values or values[0] == "暂无插件":
            return
        name = values[0]
        ptype = values[1]
        path = self.plugins_dir / name
        if not path.exists():
            messagebox.showerror("错误", "文件不存在")
            return
        try:
            self.log_message(f"运行插件: {name} (类型: {ptype})", "info")
            if ptype == "EXE":
                if sys.platform == "win32":
                    subprocess.Popen([str(path)], shell=True, cwd=str(self.plugins_dir))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(path)])
                else:
                    subprocess.Popen([str(path)], cwd=str(self.plugins_dir))
            else:  # PY
                # 使用当前 Python 解释器运行 .py 脚本
                python_exe = sys.executable
                subprocess.Popen([python_exe, str(path)], cwd=str(self.plugins_dir))
            self.log_message(f"插件 {name} 已启动", "success")
            messagebox.showinfo("提示", f"插件 {name} 已在后台运行")
        except Exception as e:
            self.log_message(f"运行失败: {e}", "error")
            messagebox.showerror("错误", f"运行失败: {e}")

    def open_selected_plugin_location(self):
        sel = self.plugin_tree.selection()
        if sel:
            values = self.plugin_tree.item(sel[0], "values")
            if values and values[0] != "暂无插件":
                p = self.plugins_dir / values[0]
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
        if item:
            self.plugin_tree.selection_set(item)
            vals = self.plugin_tree.item(item, "values")
            if vals and vals[0] != "暂无插件":
                self.plugin_ctx_menu.post(event.x_root, event.y_root)

    # ==================== server.properties 编辑器（中文） ====================
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
            with open(self.properties_file, 'w', encoding='utf-8') as f:
                f.write("#Minecraft server properties\n")
            self.log_message("已创建默认 server.properties", "info")

        props = self.load_properties_file()
        editor = tk.Toplevel(self.root)
        editor.title("服务器配置编辑")
        editor.geometry("800x650")
        editor.configure(bg=self.colors['bg'])

        main = ttk.Frame(editor)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(main, bg=self.colors['bg'], highlightthickness=0)
        vbar = ttk.Scrollbar(main, orient=tk.VERTICAL, command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)

        entry_vars = {}
        header = ttk.Frame(scrollable)
        header.pack(fill=tk.X, pady=(0,10))
        ttk.Label(header, text="配置项（中文）", font=("Arial",11,"bold"), width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text="值", font=("Arial",11,"bold"), width=40).pack(side=tk.LEFT, padx=5)

        ttk.Separator(scrollable, orient='horizontal').pack(fill=tk.X, pady=5)

        for key, val in sorted(props.items()):
            row = ttk.Frame(scrollable)
            row.pack(fill=tk.X, pady=3)
            cn = self.get_chinese_property_name(key)
            text = cn if cn==key else f"{cn}\n({key})"
            ttk.Label(row, text=text, wraplength=250, justify=tk.LEFT).pack(side=tk.LEFT, padx=5)
            var = tk.StringVar(value=val)
            entry_vars[key] = var
            ttk.Entry(row, textvariable=var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Separator(scrollable, orient='horizontal').pack(fill=tk.X, pady=10)
        add_frame = ttk.LabelFrame(scrollable, text="添加新配置项", padding=5)
        add_frame.pack(fill=tk.X, pady=5)
        add_key_var, add_val_var = tk.StringVar(), tk.StringVar()
        ttk.Label(add_frame, text="配置键:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(add_frame, textvariable=add_key_var, width=25).pack(side=tk.LEFT, padx=5)
        ttk.Label(add_frame, text="值:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(add_frame, textvariable=add_val_var, width=25).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0,10))

        def add_new():
            k = add_key_var.get().strip()
            v = add_val_var.get().strip()
            if k and v:
                row = ttk.Frame(scrollable)
                row.pack(fill=tk.X, pady=3, before=add_frame)
                cn = self.get_chinese_property_name(k)
                text = cn if cn==k else f"{cn}\n({k})"
                ttk.Label(row, text=text, wraplength=250).pack(side=tk.LEFT, padx=5)
                var = tk.StringVar(value=v)
                entry_vars[k] = var
                ttk.Entry(row, textvariable=var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
                add_key_var.set("")
                add_val_var.set("")
                self.log_message(f"已添加配置项: {k}", "info")
            else:
                messagebox.showwarning("提示", "请填写键和值")

        def save():
            try:
                new_props = {k: v.get().strip() for k,v in entry_vars.items()}
                self.save_properties_file(new_props)
                messagebox.showinfo("成功", "已保存，重启服务器后生效")
                editor.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")

        ttk.Button(btn_frame, text="➕ 添加配置", command=add_new, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="💾 保存", command=save, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=editor.destroy, width=10).pack(side=tk.RIGHT, padx=5)

        tip = ttk.Label(editor, text="💡 提示：修改后需重启服务器", foreground=self.colors['info'], background=self.colors['bg'])
        tip.pack(pady=(0,10))

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

    def save_properties_file(self, props_dict):
        with open(self.properties_file, 'w', encoding='utf-8') as f:
            f.write("#Minecraft server properties\n")
            f.write(f"#{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for k, v in sorted(props_dict.items()):
                f.write(f"{k}={v}\n")
        self.log_message("server.properties 已更新", "success")

    # ==================== 快捷命令相关 ====================
    def refresh_quick_commands(self, parent):
        for w in parent.winfo_children():
            if w not in [self.command_buttons.get('refresh')]:
                w.destroy()
        row = None
        for i, (name, info) in enumerate(self.quick_commands.items()):
            if i % 5 == 0:
                row = ttk.Frame(parent)
                row.pack(fill=tk.X, pady=2)
            btn = ttk.Button(row, text=f"/{name}", command=lambda n=name: self.show_command_dialog(n), width=12)
            btn.pack(side=tk.LEFT, padx=2)
            tip = info['description']
            if info.get('command') and '{args}' in info['command']:
                tip += "\n支持参数输入"
            self.create_tooltip(btn, tip)

    def create_tooltip(self, w, text):
        def show(e):
            tip = tk.Toplevel()
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{e.x_root+10}+{e.y_root+10}")
            ttk.Label(tip, text=text, background="#ffffe0", relief="solid", borderwidth=1).pack()
            w.tip = tip
        def hide(e):
            if hasattr(w, 'tip'):
                w.tip.destroy()
        w.bind('<Enter>', show)
        w.bind('<Leave>', hide)

    def show_command_dialog(self, cmd_name):
        if not self.server_running:
            messagebox.showwarning("警告", "服务器未运行")
            return
        info = self.quick_commands[cmd_name]
        if info.get('command') and '{args}' in info['command']:
            dlg = tk.Toplevel(self.root)
            dlg.title(f"执行 /{cmd_name}")
            dlg.geometry("500x200")
            dlg.configure(bg=self.colors['bg'])
            ttk.Label(dlg, text=info['description'], font=("Arial",10,"bold")).pack(pady=10)
            ttk.Label(dlg, text=f"格式: {info['command'].replace('{args}','<参数>')}", foreground=self.colors['info']).pack(pady=5)
            ttk.Label(dlg, text="参数:").pack(pady=(10,0))
            entry = ttk.Entry(dlg, width=50)
            entry.pack(pady=5, padx=20, fill=tk.X)
            btnf = ttk.Frame(dlg)
            btnf.pack(pady=20)
            def do():
                args = entry.get().strip()
                if args:
                    self.execute_quick_command(cmd_name, args)
                    dlg.destroy()
                else:
                    messagebox.showwarning("警告", "请输入参数")
            ttk.Button(btnf, text="执行", command=do, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(btnf, text="取消", command=dlg.destroy, width=10).pack(side=tk.LEFT, padx=5)
            entry.focus()
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

    # ==================== 服务器控制 ====================
    def browse_jar(self):
        fn = filedialog.askopenfilename(title="选择服务端 JAR", filetypes=[("Java文件","*.jar")], initialdir=str(self.server_path))
        if fn:
            self.jar_path_var.set(fn)
            self.jar_file = Path(fn)

    def start_server(self):
        if self.server_running:
            messagebox.showwarning("警告", "服务器已在运行")
            return
        jar = Path(self.jar_path_var.get())
        if not jar.exists():
            messagebox.showerror("错误", f"找不到服务端文件: {jar}")
            return
        eula = jar.parent / "eula.txt"
        if not eula.exists() or "eula=false" in open(eula).read().lower():
            if not messagebox.askyesno("接受 EULA", "需要接受 Minecraft EULA 才能启动。\n是否接受？"):
                return
            with open(eula, 'w') as f:
                f.write("eula=true")
            self.log_message("已接受 EULA", "success")
        cmd = ["java", f"-Xms{self.ram_min_var.get()}", f"-Xmx{self.ram_max_var.get()}", "-jar", str(jar), "nogui"]
        self.log_message(f"启动命令: {' '.join(cmd)}", "info")
        try:
            self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            universal_newlines=True, bufsize=1, cwd=str(jar.parent))
            self.server_running = True
            self.update_server_status(True)
            threading.Thread(target=self.handle_output, daemon=True).start()
            self.log_message("服务器启动成功！", "success")
        except Exception as e:
            self.log_message(f"启动失败: {e}", "error")
            messagebox.showerror("错误", f"启动失败: {e}")

    def handle_output(self):
        if self.process:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output_queue.put(line.strip())
            self.output_queue.put("__SERVER_STOPPED__")

    def process_output_queue(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line == "__SERVER_STOPPED__":
                    self.server_running = False
                    self.update_server_status(False)
                    self.log_message("服务器进程已结束", "warning")
                else:
                    self.log_message(line)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_output_queue)

    def log_message(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.console_text.insert(tk.END, f"[{ts}] {msg}\n", level)
        self.console_text.see(tk.END)

    def send_command(self, event=None):
        if not self.server_running:
            messagebox.showwarning("警告", "服务器未运行")
            return
        cmd = self.command_var.get().strip()
        if not cmd:
            return
        if cmd.startswith('/'):
            parts = cmd[1:].split(maxsplit=1)
            name = parts[0].lower()
            arg = parts[1] if len(parts)>1 else ""
            self.execute_quick_command(name, arg)
        else:
            self.send_to_server(cmd)
        self.command_var.set("")

    def send_to_server(self, cmd):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                self.log_message(f">>> {cmd}", "info")
            except Exception as e:
                self.log_message(f"发送失败: {e}", "error")

    def stop_server(self):
        if not self.server_running:
            return
        if messagebox.askyesno("确认", "确定要停止服务器吗？"):
            self.log_message("正在停止服务器...", "warning")
            self.send_to_server("stop")
            def force():
                if self.process and self.process.poll() is None:
                    self.log_message("服务器未响应，强制终止", "error")
                    self.process.terminate()
                    self.server_running = False
                    self.update_server_status(False)
            self.root.after(30000, force)

    def save_world(self):
        if self.server_running:
            self.send_to_server("save-all")
            self.log_message("正在保存世界...", "info")
        else:
            messagebox.showwarning("警告", "服务器未运行")

    def clear_console(self):
        self.console_text.delete(1.0, tk.END)

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

    def create_status_bar(self):
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(self.status_bar, text="就绪", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.server_status_label = ttk.Label(self.status_bar, text="● 服务器未运行", foreground="red", relief=tk.SUNKEN)
        self.server_status_label.pack(side=tk.RIGHT)

    def update_server_status(self, running):
        if running:
            self.server_status_label.config(text="● 服务器运行中", foreground="green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
        else:
            self.server_status_label.config(text="● 服务器未运行", foreground="red")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)

    def on_closing(self):
        if self.server_running:
            if messagebox.askyesno("确认", "服务器正在运行，确定退出？\n退出前会自动保存并停止。"):
                self.stop_server()
                self.root.after(2000, self.root.destroy)
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = MinecraftServerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()