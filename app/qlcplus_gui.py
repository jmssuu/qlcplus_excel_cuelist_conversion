#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_all.py 的拖曳介面：把 .xlsx 拖進視窗，按一下就跑完整個轉換流程。

直接執行::

    python3 qlcplus_gui.py

打包成 macOS 的 .app（需要 PyInstaller）::

    ./build_app.sh

視窗上半部是拖曳區，把燈表 .xlsx 拖進去就會顯示完整路徑；
Music 資料夾預設抓 .xlsx 旁邊的 ``Music/``，底稿 .qxw 預設抓旁邊的 ``BaseStage.qxw``。
按「執行轉換」後會在下方的訊息區即時顯示 run_all 的輸出。
"""

from __future__ import annotations

import os
import json
import queue
import shutil
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 轉檔用的模組放在 ../scripts（打包後會一起被收進執行檔，這行只影響直接跑原始碼）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_all
import step3_cuelist_to_qxw as step3

try:  # 有裝 tkinterdnd2 才有真正的拖曳；沒有就退回「瀏覽…」按鈕
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:  # pragma: no cover - 只在缺套件時走到
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

APP_TITLE = "QLC+ 轉檔工具(.xlsx燈表轉換成.qxw專案檔)"
BASE_QXW_NAME = "BaseStage.qxw"      # 拖進 .xlsx 時預設抓同資料夾的這一份
DEFAULT_START_SHEET = 5              # 前面幾張通常是說明／下拉選單／空白模板／測試用
SHEET_SUFFIXES = (".xlsx", ".xlsm")

# Windows 沒有 Helvetica / Menlo，硬指定會退回醜醜的預設字體
if sys.platform == "win32":
    UI_FONT, MONO_FONT = "Microsoft JhengHei UI", "Consolas"
elif sys.platform == "darwin":
    UI_FONT, MONO_FONT = "Helvetica", "Menlo"
else:
    UI_FONT, MONO_FONT = "DejaVu Sans", "DejaVu Sans Mono"

BG = "#f4f4f6"
DROP_BG = "#ffffff"
DROP_BG_HOVER = "#e8f0fe"
ACCENT = "#2d6cdf"
MUTED = "#6b6f76"
OK = "#1a7f37"
ERR = "#c0392b"
# log 上色：只有真的出錯／衝突才用紅字，提醒類用黃字，成功用綠字
# 一定是錯誤，就算掛著提醒記號也一樣（例如「⚠ 轉換失敗 …」）
ERROR_MARKERS = ("Traceback", "[失敗]", "error:", "Error", "失敗", "錯誤", "衝突")
# 只有在沒有提醒記號時才算錯誤（「[提醒] … 裡找不到 …」只是提醒）
SOFT_ERROR_MARKERS = ("沒有權限", "無法", "找不到", "中止")
WARN_MARKERS = ("⚠", "[提醒]", "[跳過]", "警告", "warning", "Warning")
OK_MARKERS = ("[OK]", "✓", "★", "已輸出", "已更新", "已備份", "已加入",
              "完成", "成功")


def log_tag(line: str):
    """依內容決定這一行的顏色；認不出來就用預設的黑字。"""
    text = line.strip()
    if not text:
        return None
    if any(mark in text for mark in ERROR_MARKERS):
        return "err"
    if any(mark in text for mark in WARN_MARKERS):
        return "warn"
    if any(mark in text for mark in SOFT_ERROR_MARKERS):
        return "err"
    if any(mark in text for mark in OK_MARKERS):
        return "ok"
    return None


HELP_SHOW = "點我展開使用說明"
HELP_HIDE = "收合使用說明"
HELP_BG = "#eef2f8"
HELP_BORDER = "#c9d4e4"
HELP_FG = "#3d4450"
HELP_WRAP = 560           # 內容欄的換行寬度，換行會吊掛在編號右邊

# (標題, 前言, [(項目記號, 項目內容), …])
HELP_SECTIONS = (
    ("使用說明", "燈表 .xlsx 所在的資料夾裡，請先備妥這三樣", (
        ("1.", "Music/：音樂檔名要和燈表裡的工作表名稱一模一樣"
               "（工作表「XX組-表演名稱」→ XX組-表演名稱.mp3）"),
        ("2.", "Fixtures/：這場用到的燈具檔 .qxf。"
               "QLC+ 使用者燈具庫裡已經有這些燈具的話，就不需要這個資料夾"),
        ("3.", "底稿 .qxw（例如 BaseStage.qxw）：已經設好燈具數量、DMX 位址"
               "與舞台配置的檔案。放在別的路徑也可以，用下面的欄位拖曳或"
               "「瀏覽…」指定即可"),
    )),
    ("產出檔案", "", (
        ("→", "轉換後會在同一個資料夾產生「燈表名稱.qxw」。用 QLC+ 開啟後，"
              "到 Function Manager 的 Show 資料夾裡，就能找到正式表演要用的 Show"),
    )),
)

WARN_BG = "#fff4d6"
WARN_FG = "#8a5b00"


class QueueWriter:
    """把 print 的內容丟進 queue，讓主執行緒慢慢貼到畫面上。"""

    def __init__(self, sink: "queue.Queue[tuple[str, str]]", tag: str):
        self.sink = sink
        self.tag = tag

    def write(self, text):
        if text:
            self.sink.put((self.tag, text))
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


class App:
    def __init__(self, root):
        self.root = root
        self.source: Path | None = None
        self.music_var = tk.StringVar()
        self.base_var = tk.StringVar()
        self.cleanup_var = tk.BooleanVar(value=True)
        self.start_sheet_var = tk.StringVar(value=str(DEFAULT_START_SHEET))
        self._auto_filled = {}      # 欄位 -> 上次自動帶入的值
        self._fixture_todo = []     # 待複製到 QLC+ 使用者燈具庫的 .qxf
        self._fixture_dest = None
        self._log_pending = ""      # log_stream 還沒湊成整行的殘句
        self.log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.running = False

        root.title(APP_TITLE)
        root.configure(bg=BG)
        root.minsize(640, 600)
        root.geometry("720x720")

        self._build_widgets()
        self._poll_log()

        # 拖到 Dock 上的 app 圖示也能開檔
        try:
            root.createcommand("::tk::mac::OpenDocument", self._on_open_document)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ 版面
    def _build_widgets(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, font=(UI_FONT, 12))
        style.configure("Hint.TLabel", background=BG, foreground=MUTED,
                        font=(UI_FONT, 11))
        style.configure("Run.TButton", font=(UI_FONT, 15, "bold"), padding=10)

        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(7, weight=1)

        # --- 拖曳區 ---
        self.drop = tk.Label(
            outer,
            text=self._drop_hint(),
            justify="center",
            wraplength=620,
            bg=DROP_BG,
            fg=MUTED,
            font=(UI_FONT, 13),
            bd=2,
            relief="groove",
            padx=16,
            pady=28,
        )
        self.drop.grid(row=2, column=0, sticky="ew")
        self.drop.bind("<Button-1>", lambda _e: self.browse_source())
        self._register_drop(self.drop, self._on_drop_source)

        ttk.Label(outer, text="（也可以直接點一下這塊區域選檔）",
                  style="Hint.TLabel").grid(row=3, column=0, pady=(6, 12))

        # --- 使用說明（預設收起來，按按鈕才展開）---
        self.help_btn = ttk.Button(outer, text=HELP_SHOW,
                                   command=self.toggle_help)
        self.help_btn.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.help_box = tk.Frame(outer, bg=HELP_BG, highlightthickness=1,
                                 highlightbackground=HELP_BORDER)
        self.help_box.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.help_box.columnconfigure(1, weight=1)
        self._build_help(self.help_box)
        self.help_box.grid_remove()

        # --- 選項 ---
        opts = ttk.Frame(outer)
        opts.grid(row=4, column=0, sticky="ew")
        opts.columnconfigure(0, weight=1)

        # 兩個路徑欄位自成一個 grid：標籤欄的寬度只由這兩個標籤決定，
        # 不會被下面那個長標籤「從第幾張工作表開始：」推開。
        paths = ttk.Frame(opts)
        paths.grid(row=0, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)

        self._path_row(paths, 0, "Music 資料夾：", self.music_var,
                       self.browse_music, folder=True)
        self._path_row(paths, 1, "底稿 .qxw：", self.base_var,
                       self.browse_base, folder=False)

        start_row = ttk.Frame(opts)
        start_row.grid(row=1, column=0, sticky="ew", pady=4)
        # 數字框直接嵌在句子中間：Excel 轉換從第 [5] 張工作表開始轉換
        ttk.Label(start_row, text="Excel 轉換從第").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(start_row, from_=1, to=999, width=5, justify="center",
                    textvariable=self.start_sheet_var).grid(row=0, column=1,
                                                            sticky="w", padx=6)
        ttk.Label(start_row, text="張工作表開始轉換").grid(row=0, column=2, sticky="w")
        ttk.Label(start_row,
                  text=f"(這張之前的工作表都不轉換，如：說明／下拉選單／空白模板…，"
                       f"預設從第 {DEFAULT_START_SHEET} 張開始)",
                  style="Hint.TLabel").grid(row=0, column=3, sticky="w", padx=(8, 0))

        # 用原生的 tk.Checkbutton 而不是 ttk 版：clam 主題的勾選記號畫出來是叉。
        # 文字顏色要自己指定：系統若是深色模式，預設的標籤色是白的，
        # 配上這裡固定的淺色背景會看不見。
        tk.Checkbutton(opts, text="執行轉換結束後自動刪除temp檔",
                       variable=self.cleanup_var, background=BG,
                       activebackground=BG, foreground="#22252a",
                       activeforeground="#22252a", highlightthickness=0,
                       borderwidth=0, anchor="w",
                       font=(UI_FONT, 12)).grid(
            row=2, column=0, sticky="w", padx=6, pady=(6, 0))

        # --- 執行 ---
        bar = ttk.Frame(outer)
        bar.grid(row=5, column=0, sticky="ew", pady=(14, 8))
        bar.columnconfigure(1, weight=1)

        self.run_btn = ttk.Button(bar, text="執行轉換", style="Run.TButton",
                                  command=self.start_run, state="disabled")
        self.run_btn.grid(row=0, column=0, sticky="w")

        self.status = tk.Label(bar, text="請先拖入 .xlsx", bg=BG, fg=MUTED,
                               font=(UI_FONT, 12), anchor="w")
        self.status.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        ttk.Button(bar, text="複製訊息",
                   command=self.copy_all_log).grid(row=0, column=2, sticky="e")

        ttk.Button(bar, text="清除訊息",
                   command=self.clear_log).grid(row=0, column=3, sticky="e",
                                                padx=(6, 0))

        # --- 燈具庫警告列（平常收起來，缺燈具檔時才出現）---
        self.fixture_bar = tk.Frame(outer, bg=WARN_BG, highlightthickness=1,
                                    highlightbackground=WARN_FG)
        self.fixture_bar.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        self.fixture_bar.columnconfigure(0, weight=1)
        self.fixture_bar.grid_remove()

        self.fixture_msg = tk.Label(self.fixture_bar, text="", bg=WARN_BG,
                                    fg=WARN_FG, font=(UI_FONT, 12),
                                    anchor="w", justify="left")
        self.fixture_msg.grid(row=0, column=0, sticky="ew", padx=10, pady=8)

        self.fixture_btn = ttk.Button(self.fixture_bar, text="是否要幫你加入燈具檔？",
                                      command=self.install_fixtures)
        self.fixture_btn.grid(row=0, column=1, sticky="e", padx=10, pady=8)

        # --- 訊息區 ---
        logbox = ttk.Frame(outer)
        logbox.grid(row=7, column=0, sticky="nsew")
        logbox.columnconfigure(0, weight=1)
        logbox.rowconfigure(0, weight=1)

        # state 保持 normal 才能用滑鼠選取、Cmd+C 複製；改用按鍵攔截來擋住編輯
        self.log = tk.Text(logbox, wrap="word", height=14, bd=1, relief="solid",
                           bg="#ffffff", fg="#22252a", font=(MONO_FONT, 11),
                           undo=False, exportselection=True,
                           selectbackground="#b5d3ff",
                           inactiveselectbackground="#d8e6fb")
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.bind("<Key>", self._readonly_key)
        for virtual in ("<<Paste>>", "<<Cut>>", "<<Clear>>", "<<PasteSelection>>"):
            self.log.bind(virtual, lambda _e: "break")
        self.log.bind("<Button-2>", self._popup_menu)
        self.log.bind("<Button-3>", self._popup_menu)
        self.log.bind("<Control-Button-1>", self._popup_menu)
        self._build_log_menu()
        bar_y = ttk.Scrollbar(logbox, orient="vertical", command=self.log.yview)
        bar_y.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=bar_y.set)
        self.log.tag_configure("err", foreground=ERR)
        self.log.tag_configure("warn", foreground=WARN_FG)
        self.log.tag_configure("ok", foreground=OK)
        self.log.tag_configure("info", foreground=ACCENT)

    # 這些鍵不會改內容，放行（方向鍵配 Shift 就能用鍵盤選取）
    NAV_KEYS = {
        "Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End",
        "Shift_L", "Shift_R", "Control_L", "Control_R",
        "Meta_L", "Meta_R", "Alt_L", "Alt_R", "Caps_Lock",
    }

    def _readonly_key(self, event):
        """擋掉會改內容的按鍵，但保留 Cmd+C／Cmd+A 與游標移動。"""
        if event.state & 0x000c:  # Control(0x4) 或 Command(0x8)
            return None
        if event.keysym in self.NAV_KEYS:
            return None
        return "break"

    def _build_log_menu(self):
        self.log_menu = tk.Menu(self.root, tearoff=0)
        self.log_menu.add_command(label="複製", command=self.copy_selection)
        self.log_menu.add_command(label="全選", command=self.select_all_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="複製全部訊息", command=self.copy_all_log)

    def _popup_menu(self, event):
        self.log_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def copy_selection(self):
        self.log.event_generate("<<Copy>>")

    def select_all_log(self):
        self.log.tag_add("sel", "1.0", "end-1c")
        self.log.focus_set()

    def copy_all_log(self):
        text = self.log.get("1.0", "end-1c")
        if not text.strip():
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _build_help(self, box):
        """把說明排成「記號｜內容」兩欄，內容換行時會吊掛對齊，不會跑回最左邊。"""
        def line(row, text, *, column, columnspan=1, bold=False, pad_top=0):
            tk.Label(box, text=text, bg=HELP_BG, fg=HELP_FG,
                     font=(UI_FONT, 11, "bold") if bold else (UI_FONT, 11),
                     justify="left", anchor="nw",
                     wraplength=HELP_WRAP if column else 0).grid(
                row=row, column=column, columnspan=columnspan, sticky="nw",
                padx=(12 if column == 0 else 0, 12 if column else 0),
                pady=(pad_top, 2))

        row = 0
        for title, intro, items in HELP_SECTIONS:
            line(row, f"{title}：{intro}" if intro else f"{title}：",
                 column=0, columnspan=2, bold=True, pad_top=10)
            row += 1
            for mark, text in items:
                line(row, f"　{mark}", column=0)
                line(row, text, column=1)
                row += 1
        # 最後一列補一點底部留白
        tk.Frame(box, bg=HELP_BG, height=8).grid(row=row, column=0, columnspan=2)

    def toggle_help(self):
        """展開／收合使用說明。"""
        if self.help_box.winfo_manager():
            self.help_box.grid_remove()
            self.help_btn.configure(text=HELP_SHOW)
        else:
            self.help_box.grid()
            self.help_btn.configure(text=HELP_HIDE)
            # 視窗不夠高就長高一點，免得說明把訊息區壓扁（收合時不主動縮回去）
            self.root.update_idletasks()
            need = self.root.winfo_reqheight()
            if self.root.winfo_height() < need:
                limit = self.root.winfo_screenheight() - 120
                self.root.geometry(f"{self.root.winfo_width()}x{min(need, limit)}")

    def _path_row(self, parent, row, label, var, command, folder):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w",
                                          pady=4)
        entry = ttk.Entry(parent, textvariable=var, font=(UI_FONT, 12))
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        self._register_drop(entry, lambda paths, v=var, f=folder:
                            self._on_drop_path(paths, v, f))
        ttk.Button(parent, text="瀏覽…", command=command).grid(row=row, column=2,
                                                              sticky="e")

    def _drop_hint(self):
        verb = "拖曳" if HAS_DND else "選擇"
        return f"把燈表 .xlsx {verb}到這裡"

    # -------------------------------------------------------------- 拖曳處理
    def _register_drop(self, widget, handler):
        if not HAS_DND:
            return
        try:
            widget.drop_target_register(DND_FILES)
        except tk.TclError:
            return
        widget.dnd_bind("<<Drop>>", lambda e: handler(self._split(e.data)))
        if widget is getattr(self, "drop", None):
            widget.dnd_bind("<<DropEnter>>",
                            lambda _e: widget.configure(bg=DROP_BG_HOVER))
            widget.dnd_bind("<<DropLeave>>",
                            lambda _e: widget.configure(bg=DROP_BG))

    def _split(self, data):
        """拖進來的資料是 Tcl list，含空白的路徑會被大括號包起來。"""
        try:
            return [Path(p) for p in self.root.tk.splitlist(data)]
        except tk.TclError:
            return [Path(data)]

    def _on_drop_source(self, paths):
        self.drop.configure(bg=DROP_BG)
        for path in paths:
            if path.suffix.lower() in SHEET_SUFFIXES:
                self.set_source(path)
                return
        self.log_line("⚠ 請拖入 .xlsx 檔案\n", "err")

    def _on_drop_path(self, paths, var, folder):
        for path in paths:
            if folder and path.is_dir():
                var.set(str(path))
                return
            if not folder and path.suffix.lower() == ".qxw":
                var.set(str(path))
                return
        self.log_line("⚠ 這一格只接受 " + ("資料夾" if folder else ".qxw") + "\n",
                      "err")

    def _on_open_document(self, *paths):
        for path in paths:
            p = Path(path)
            if p.suffix.lower() in SHEET_SUFFIXES:
                self.set_source(p)
                return

    # ---------------------------------------------------------------- 選檔
    def browse_source(self):
        if self.running:
            return
        path = filedialog.askopenfilename(
            title="選擇要轉換的燈表",
            filetypes=[("Excel 活頁簿", "*.xlsx *.xlsm"), ("所有檔案", "*.*")])
        if path:
            self.set_source(Path(path))

    def browse_music(self):
        start = self.source.parent if self.source else None
        path = filedialog.askdirectory(title="選擇 Music 資料夾",
                                       initialdir=start)
        if path:
            self.music_var.set(path)

    def browse_base(self):
        start = self.source.parent if self.source else None
        path = filedialog.askopenfilename(title="選擇底稿 .qxw",
                                          initialdir=start,
                                          filetypes=[("QLC+ workspace", "*.qxw")])
        if path:
            self.base_var.set(path)

    def set_source(self, path: Path):
        path = path.expanduser()
        if not path.is_file():
            self.log_line(f"⚠ 找不到檔案：{path}\n", "err")
            return
        self.source = path
        self.drop.configure(text=str(path), fg="#22252a",
                            font=(UI_FONT, 13, "bold"))
        music = path.parent / "Music"
        if music.is_dir():
            self._autofill(self.music_var, music)
        # 底稿 .qxw 是必要的，優先抓同資料夾的 BaseStage.qxw
        base = self._find_base(path.parent)
        if base is not None:
            self._autofill(self.base_var, base)
        elif not self.base_var.get():
            self.log_line(f"⚠ {path.parent} 底下沒有 {BASE_QXW_NAME}，"
                          "請自己選一份底稿 .qxw\n", "err")
        self.run_btn.configure(state="normal")
        self.set_status(f"準備轉換：{path.name}", MUTED)

    def _autofill(self, var, value: Path):
        """欄位還空著、或裡面是上次自動帶入的值，就換成這次算出來的。"""
        current = var.get().strip()
        if current and current != self._auto_filled.get(id(var)):
            return
        var.set(str(value))
        self._auto_filled[id(var)] = str(value)

    @staticmethod
    def _find_base(folder: Path):
        """同資料夾裡的底稿 .qxw：先找 BaseStage.qxw，沒有就找唯一的一份。"""
        named = folder / BASE_QXW_NAME
        if named.is_file():
            return named
        try:
            found = [p for p in sorted(folder.glob("*.qxw"))
                     if not p.name.startswith((".", "~$"))
                     and ".autosave" not in p.name.lower()]
        except OSError:
            return None
        return found[0] if len(found) == 1 else None

    # ---------------------------------------------------------------- 執行
    def start_run(self):
        if self.running or self.source is None:
            return
        music = self.music_var.get().strip()
        base = self.base_var.get().strip()
        if music and not Path(music).is_dir():
            messagebox.showerror(APP_TITLE, f"找不到 Music 資料夾：\n{music}")
            return
        blocked = self.no_permission(Path(music) if music else self.source.parent)
        if blocked:
            messagebox.showerror(APP_TITLE, blocked)
            return
        if base and not Path(base).is_file():
            messagebox.showerror(APP_TITLE, f"找不到底稿 .qxw：\n{base}")
            return
        if not base:
            messagebox.showerror(
                APP_TITLE,
                "請指定底稿 .qxw。\n\n"
                "燈具有幾台、DMX 位址、模式與通道長度都是從底稿讀出來的，"
                f"少了它沒辦法轉換。\n把 {BASE_QXW_NAME} 放在燈表旁邊，"
                "或用「瀏覽…」選一份。")
            return
        start_sheet = self.start_sheet_var.get().strip()
        if not start_sheet.isdigit() or int(start_sheet) < 1:
            messagebox.showerror(
                APP_TITLE,
                f"「從第幾張工作表開始」要填 1 以上的整數，目前是「{start_sheet}」。")
            return

        self.running = True
        self.run_btn.configure(state="disabled")
        self.set_status("轉換中…", ACCENT)
        self.clear_log()

        args = [str(self.source), music or str(self.source.parent / "Music")]
        if base:
            args.append(base)
        args += ["--outdir", str(self.source.parent),
                 "--start-sheet", start_sheet]

        temp_dir = (self.source.parent / f"temp_{self.source.stem}"
                    if self.cleanup_var.get() else None)
        self.hide_fixture_bar()
        threading.Thread(target=self._worker, args=(args, temp_dir, Path(base)),
                         daemon=True).start()

    @staticmethod
    def no_permission(folder: Path):
        """macOS 會擋下 App 列出「文件 / 桌面 / 下載」裡的內容，先試一次給出說明。"""
        try:
            next(folder.iterdir(), None)
        except PermissionError:
            return (f"沒有權限讀取資料夾：\n{folder}\n\n"
                    "macOS 預設會擋下 App 列出「文件 / 桌面 / 下載 / iCloud 雲碟」裡的內容。\n"
                    "請到「系統設定 → 隱私權與安全性 → 檔案與資料夾」（或「完全取用磁碟」）"
                    f"把 {APP_TITLE} 打開後重新執行，\n"
                    "或把資料改放到不受保護的位置。")
        except OSError:
            pass
        return None

    def _worker(self, args, temp_dir=None, base=None):
        out = QueueWriter(self.log_queue, "out")
        err = QueueWriter(self.log_queue, "err")
        old_out, old_err, old_cwd = sys.stdout, sys.stderr, os.getcwd()
        sys.stdout, sys.stderr = out, err
        code = 1
        try:
            os.chdir(Path(args[0]).parent)
            code = run_all.main(args)
        except SystemExit as exc:  # take_option 會丟這個
            err.write(f"{exc}\n")
        except Exception:
            err.write(traceback.format_exc())
        finally:
            if base is not None:
                try:
                    self.check_fixture_library(base, out)
                except Exception:
                    err.write(traceback.format_exc())
            # 不論轉換成功或失敗都清掉中繼資料夾（勾選「自動刪除temp檔」時）
            if temp_dir is not None and temp_dir.is_dir():
                # step4 只改得動「在 Music 裡找得到」的音檔；找不到的仍指向 temp
                # 資料夾，這時候刪掉會讓 QLC+ 開起來播不出聲音，先提醒一聲。
                qxw = temp_dir.parent / f"{temp_dir.name[len('temp_'):]}.qxw"
                try:
                    stale = qxw.read_text(errors="replace").count(f"{temp_dir.name}/")
                except OSError:
                    stale = 0
                if stale:
                    err.write(f"[提醒] {qxw.name} 裡還有 {stale} 個音檔指向 "
                              f"{temp_dir.name}/，刪掉後這些音檔會失效；"
                              "請確認 Music 資料夾裡有同名的檔案。\n")
                try:
                    shutil.rmtree(temp_dir)
                    out.write(f"[清除] 已刪除中繼資料夾 {temp_dir.name}\n")
                except OSError as exc:
                    err.write(f"[提醒] 刪不掉 {temp_dir}：{exc}\n")
            sys.stdout, sys.stderr = old_out, old_err
            try:
                os.chdir(old_cwd)
            except OSError:
                pass
            self.log_queue.put(("done", str(code)))

    # ------------------------------------------------------- QLC+ 燈具庫
    def check_fixture_library(self, base: Path, out):
        """看 QLC+ 使用者燈具庫裡有沒有這份 .qxw 用到的燈具檔。

        在工作執行緒裡跑，結果丟回 queue 讓主執行緒去改畫面。
        """
        dest = step3.user_fixture_dir()
        try:
            fixtures = step3.workspace_fixtures(base)
        except Exception:
            return
        needed = {(step3.normalize(f.get("Manufacturer", "")),
                   step3.normalize(f.get("Model", ""))):
                  f"{f.get('Manufacturer', '')} {f.get('Model', '')}".strip()
                  for f in fixtures}
        if not needed:
            return

        installed = step3.collect_fixture_defs([dest])
        missing = {key: label for key, label in needed.items()
                   if key not in installed}
        if not missing:
            out.write(f"[OK] QLC+ 使用者燈具庫已有需要的燈具檔（{dest}）\n")
            return

        # 在本機其他位置（專案 Fixtures/、QLC+ 內建庫…）找得到的才有得複製
        extra = (self.source.parent,) if self.source else ()
        available = step3.load_fixture_defs(base, extra)
        todo, hopeless = [], []
        for key, label in sorted(missing.items()):
            found = available.get(key)
            if found is not None and found[1].parent != dest:
                todo.append(found[1])
            else:
                hopeless.append(label)
        self.log_queue.put(("fixtures", json.dumps({
            "dest": str(dest),
            "missing": sorted(missing.values()),
            "todo": [str(path) for path in dict.fromkeys(todo)],
            "hopeless": hopeless,
        })))

    def show_fixture_bar(self, info):
        self._fixture_dest = Path(info["dest"])
        self._fixture_todo = [Path(p) for p in info["todo"]]
        text = ("警告：本電腦QLC+ 使用者燈具庫未放入必要燈具檔\n"
                f"缺少：{'、'.join(info['missing'])}")
        if info["hopeless"]:
            text += f"\n（{'、'.join(info['hopeless'])} 在本機找不到定義檔，要自己補）"
        self.fixture_msg.configure(text=text)
        if self._fixture_todo:
            self.fixture_btn.configure(text="是否要幫你加入燈具檔？", state="normal")
            self.fixture_btn.grid()
        else:
            self.fixture_btn.grid_remove()
        self.fixture_bar.grid()

    def hide_fixture_bar(self):
        self.fixture_bar.grid_remove()
        self._fixture_todo = []
        self._fixture_dest = None

    def install_fixtures(self):
        """把用到的 .qxf 複製進 QLC+ 使用者燈具庫。"""
        dest, sources = self._fixture_dest, self._fixture_todo
        if dest is None or not sources:
            return
        copied, failed = [], []
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.log_line(f"⚠ 建不出資料夾 {dest}：{exc}\n", "err")
            return
        for src in sources:
            try:
                shutil.copy2(src, dest / src.name)
                copied.append(src)
            except OSError as exc:
                failed.append((src, exc))
        for src in copied:
            self.log_line(f"[OK] 已複製燈具檔 {src.name} -> {dest}\n")
        for src, exc in failed:
            self.log_line(f"⚠ 複製 {src.name} 失敗：{exc}\n", "err")
        if copied:
            self.log_line("　　QLC+ 要重新啟動才會讀到新的燈具檔。\n")
            self.fixture_msg.configure(
                text=f"已加入 {len(copied)} 個燈具檔到 {dest}（QLC+ 重開後生效）")
            self.fixture_btn.grid_remove()
            self._fixture_todo = []

    # ---------------------------------------------------------------- 畫面
    def _poll_log(self):
        while True:
            try:
                tag, text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if tag == "fixtures":
                self.show_fixture_bar(json.loads(text))
            elif tag == "done":
                self._finish(int(text))
            else:
                self.log_stream(text)
        self.root.after(80, self._poll_log)

    def _finish(self, code):
        self.flush_log_stream()
        self.running = False
        self.run_btn.configure(state="normal")
        if code == 0:
            out = self.source.parent / f"{self.source.stem}.qxw"
            self.set_status(f"完成：{out.name}", OK)
            self.log_line(f"\n✓ 完成，輸出：{out}\n", "info")
        else:
            self.set_status(f"失敗（代碼 {code}），詳見下方訊息", ERR)

    def set_status(self, text, color):
        self.status.configure(text=text, fg=color)

    def clear_log(self):
        self.log.delete("1.0", "end")
        self._log_pending = ""

    def log_line(self, text, tag=None):
        # 使用者捲上去看／選字時就不要硬拉回底部
        at_bottom = self.log.yview()[1] > 0.999
        if tag is None:
            for line in text.splitlines(keepends=True):
                self.log.insert("end", line, log_tag(line) or ())
        else:
            self.log.insert("end", text, tag)
        if at_bottom:
            self.log.see("end")

    def log_stream(self, text):
        """轉檔輸出是一段一段丟過來的，湊成整行才判斷顏色。"""
        self._log_pending += text
        while "\n" in self._log_pending:
            line, self._log_pending = self._log_pending.split("\n", 1)
            self.log_line(line + "\n")

    def flush_log_stream(self):
        if self._log_pending:
            self.log_line(self._log_pending)
            self._log_pending = ""


def main():
    # 打包成視窗程式後沒有主控台，stdout/stderr 會是 None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    # QLCPLUS_GUI_SELFTEST=1 只回報拖曳套件有沒有被打包進來，不開視窗
    if os.environ.get("QLCPLUS_GUI_SELFTEST"):
        root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
        root.withdraw()
        version = root.tk.call("package", "require", "tkdnd") if HAS_DND else "-"
        print(f"HAS_DND={HAS_DND} tkdnd={version} frozen={getattr(sys, 'frozen', False)}")
        root.destroy()
        return 0

    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    app = App(root)
    for arg in sys.argv[1:]:
        if Path(arg).suffix.lower() in SHEET_SUFFIXES:
            app.set_source(Path(arg))
            break
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
