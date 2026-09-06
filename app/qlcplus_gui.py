#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_all.py 的拖曳介面：把 .xlsx 拖進視窗，按一下就跑完整個轉換流程。

直接執行::

    python3 qlcplus_gui.py

打包成 macOS 的 .app（需要 PyInstaller）::

    ./build_app.sh

視窗上半部是拖曳區，把總表 .xlsx 拖進去就會顯示完整路徑；
Music 資料夾預設抓 .xlsx 旁邊的 ``Music/``，底稿 .qxw 可留空。
按「執行轉換」後會在下方的訊息區即時顯示 run_all 的輸出。
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 轉檔用的模組放在 ../scripts（打包後會一起被收進執行檔，這行只影響直接跑原始碼）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_all

try:  # 有裝 tkinterdnd2 才有真正的拖曳；沒有就退回「瀏覽…」按鈕
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:  # pragma: no cover - 只在缺套件時走到
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

APP_TITLE = "QLC+ 轉檔工具"
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
        self.log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.running = False

        root.title(APP_TITLE)
        root.configure(bg=BG)
        root.minsize(640, 560)
        root.geometry("720x640")

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
        outer.rowconfigure(4, weight=1)

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
        self.drop.grid(row=0, column=0, sticky="ew")
        self.drop.bind("<Button-1>", lambda _e: self.browse_source())
        self._register_drop(self.drop, self._on_drop_source)

        ttk.Label(outer, text="（也可以直接點一下這塊區域選檔）",
                  style="Hint.TLabel").grid(row=1, column=0, pady=(6, 12))

        # --- 選項 ---
        opts = ttk.Frame(outer)
        opts.grid(row=2, column=0, sticky="ew")
        opts.columnconfigure(1, weight=1)

        self._path_row(opts, 0, "Music 資料夾：", self.music_var,
                       self.browse_music, folder=True)
        self._path_row(opts, 1, "底稿 .qxw（可留空）：", self.base_var,
                       self.browse_base, folder=False)

        # --- 執行 ---
        bar = ttk.Frame(outer)
        bar.grid(row=3, column=0, sticky="ew", pady=(14, 8))
        bar.columnconfigure(1, weight=1)

        self.run_btn = ttk.Button(bar, text="執行轉換", style="Run.TButton",
                                  command=self.start_run, state="disabled")
        self.run_btn.grid(row=0, column=0, sticky="w")

        self.status = tk.Label(bar, text="請先拖入 .xlsx", bg=BG, fg=MUTED,
                               font=(UI_FONT, 12), anchor="w")
        self.status.grid(row=0, column=1, sticky="ew", padx=(12, 0))

        ttk.Button(bar, text="複製訊息",
                   command=self.copy_all_log).grid(row=0, column=2, sticky="e")

        # --- 訊息區 ---
        logbox = ttk.Frame(outer)
        logbox.grid(row=4, column=0, sticky="nsew")
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
        return f"把總表 .xlsx {verb}到這裡"

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
            title="選擇要轉換的總表",
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
        if music.is_dir() and not self.music_var.get():
            self.music_var.set(str(music))
        self.run_btn.configure(state="normal")
        self.set_status(f"準備轉換：{path.name}", MUTED)

    # ---------------------------------------------------------------- 執行
    def start_run(self):
        if self.running or self.source is None:
            return
        music = self.music_var.get().strip()
        base = self.base_var.get().strip()
        if music and not Path(music).is_dir():
            messagebox.showerror(APP_TITLE, f"找不到 Music 資料夾：\n{music}")
            return
        if base and not Path(base).is_file():
            messagebox.showerror(APP_TITLE, f"找不到底稿 .qxw：\n{base}")
            return

        self.running = True
        self.run_btn.configure(state="disabled")
        self.set_status("轉換中…", ACCENT)
        self.clear_log()

        args = [str(self.source), music or str(self.source.parent / "Music")]
        if base:
            args.append(base)
        args += ["--outdir", str(self.source.parent)]

        threading.Thread(target=self._worker, args=(args,), daemon=True).start()

    def _worker(self, args):
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
            sys.stdout, sys.stderr = old_out, old_err
            try:
                os.chdir(old_cwd)
            except OSError:
                pass
            self.log_queue.put(("done", str(code)))

    # ---------------------------------------------------------------- 畫面
    def _poll_log(self):
        while True:
            try:
                tag, text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            if tag == "done":
                self._finish(int(text))
            else:
                self.log_line(text, tag if tag == "err" else None)
        self.root.after(80, self._poll_log)

    def _finish(self, code):
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

    def log_line(self, text, tag=None):
        # 使用者捲上去看／選字時就不要硬拉回底部
        at_bottom = self.log.yview()[1] > 0.999
        self.log.insert("end", text, tag or ())
        if at_bottom:
            self.log.see("end")


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
