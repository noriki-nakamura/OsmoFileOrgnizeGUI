import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import shutil
import threading
from pathlib import Path

from organizer_core import (
    get_media_date,
    format_size,
    parse_exts,
    build_dest_path,
)


# ──────────────────────────────────────────────
# 定数・設定
# ──────────────────────────────────────────────
APP_VERSION = "v0.0.0-dev"


# ──────────────────────────────────────────────
# メインアプリケーション
# ──────────────────────────────────────────────

class OsmoOrganizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OSMO Pocket データ整理ツール")

        # アイコン設定
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            self.root.iconbitmap(str(icon_path))

        # 状態変数
        self.source_path = ""
        self.dest_path = ""
        self.detected_files = []   # { path, date, type, size }
        self.organized_files = []  # { src, dest }

        # チェックボックス変数
        self.var_delete = tk.BooleanVar(value=False)
        self.var_ignore_proxy = tk.BooleanVar(value=True)
        self.var_group_date = tk.BooleanVar(value=True)
        self.var_split_type = tk.BooleanVar(value=True)
        self.var_open_dest = tk.BooleanVar(value=True)
        self.var_date_format = tk.StringVar(value="YYYYMMDD")
        self.var_video_folder = tk.StringVar(value="Videos")
        self.var_photo_folder = tk.StringVar(value="Photos")
        self.var_ignore_exts = tk.StringVar(value=".LRF, .THM")
        self.var_folder_order = tk.StringVar(value="日付 > 種類")
        self.var_video_exts = tk.StringVar(value=".MP4")
        self.var_photo_exts = tk.StringVar(value=".JPG, .DNG, .JPEG")
        self.var_misc_folder = tk.StringVar(value="Misc")

        # 変数変更時にプレビューを更新するトレース設定
        self.var_video_folder.trace_add("write", lambda *args: self._update_previews())
        self.var_photo_folder.trace_add("write", lambda *args: self._update_previews())
        self.var_ignore_exts.trace_add("write", lambda *args: self._update_previews())
        self.var_video_exts.trace_add("write", lambda *args: self._update_previews())
        self.var_photo_exts.trace_add("write", lambda *args: self._update_previews())
        self.var_misc_folder.trace_add("write", lambda *args: self._update_previews())

        # Windows 標準テーマ
        style = ttk.Style()
        style.theme_use("winnative")
        style.configure("TCombobox", fieldbackground="white")
        style.map("TCombobox", fieldbackground=[("readonly", "white")])
        style.map("TCombobox", background=[("readonly", "white")])

        # UI 構築
        self._build_ui()

        # ウィンドウサイズの自動調整
        self.root.update_idletasks()
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        
        # 算出した必要サイズを最小サイズおよび初期サイズとして適用
        # （req_h が極端に小さい場合は Treeview の視認性を考慮したバランスをとる）
        init_h = max(req_h, 720) 
        self.root.minsize(req_w, req_h)
        self.root.geometry(f"{req_w}x{init_h}")

        # 設定の読み込み
        self._load_config()

        # 終了時の保存設定
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ─── UI 構築 ──────────────────────────────
    def _build_ui(self):
        # タイトル
        title = ttk.Label(self.root, text="OSMO Pocket データ整理ツール",
                          font=("Yu Gothic UI", 16, "bold"))
        title.pack(anchor="w", padx=16, pady=(12, 4))

        # バージョン表示 (右上に配置)
        version_lbl = ttk.Label(self.root, text=APP_VERSION, 
                                font=("Yu Gothic UI", 9), foreground="gray")
        version_lbl.place(relx=1.0, rely=0.0, anchor="ne", x=-16, y=14)

        # 1. フォルダ選択
        self._build_folder_section()

        # 2. 整理設定
        self._build_settings_section()

        # 3. ファイルリスト (2ペイン)
        self._build_file_lists()

        # 4. 処理実行
        self._build_execution_section()

    # ─── フォルダ選択 ─────────────────────────
    def _build_folder_section(self):
        frame = ttk.LabelFrame(self.root, text="フォルダ選択", padding=10)
        frame.pack(fill="x", padx=16, pady=4)

        # 読み込み元
        row_src = ttk.Frame(frame)
        row_src.pack(fill="x", pady=2)
        ttk.Button(row_src, text="読み込み元",
                   command=self._pick_source).pack(side="left")
        self.lbl_source = ttk.Label(row_src, text="選択されていません",
                                     font=("Yu Gothic UI", 9, "italic"))
        self.lbl_source.pack(side="left", padx=(10, 0))

        # 保存先
        row_dst = ttk.Frame(frame)
        row_dst.pack(fill="x", pady=2)
        ttk.Button(row_dst, text="保存先",
                   command=self._pick_dest).pack(side="left")
        self.lbl_dest = ttk.Label(row_dst, text="選択されていません",
                                   font=("Yu Gothic UI", 9, "italic"))
        self.lbl_dest.pack(side="left", padx=(10, 0))

    # ─── ファイルリスト (2ペイン) ──────────────
    def _build_file_lists(self):
        pane = ttk.Frame(self.root)
        pane.pack(fill="both", expand=True, padx=16, pady=4)
        pane.columnconfigure(0, weight=1)
        pane.columnconfigure(1, weight=1)
        pane.rowconfigure(0, weight=1)

        # 左: 検出されたファイル
        left_frame = ttk.LabelFrame(pane, text="検出されたファイル (SDカード)", padding=6)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        tree_frame_l = ttk.Frame(left_frame)
        tree_frame_l.pack(fill="both", expand=True)

        self.tree_detected = ttk.Treeview(tree_frame_l,
                                           columns=("name", "type", "date", "size"),
                                           show="headings",
                                           selectmode="none")
        self.tree_detected.heading("name", text="ファイル名")
        self.tree_detected.heading("type", text="種類")
        self.tree_detected.heading("date", text="撮影日")
        self.tree_detected.heading("size", text="サイズ")
        self.tree_detected.column("name", width=200, minwidth=120)
        self.tree_detected.column("type", width=60, minwidth=50, anchor="center")
        self.tree_detected.column("date", width=90, minwidth=80, anchor="center")
        self.tree_detected.column("size", width=80, minwidth=60, anchor="e")

        sb_l = ttk.Scrollbar(tree_frame_l, orient="vertical",
                              command=self.tree_detected.yview)
        self.tree_detected.configure(yscrollcommand=sb_l.set)
        self.tree_detected.pack(side="left", fill="both", expand=True)
        sb_l.pack(side="right", fill="y")

        # 右: 整理後のファイル構成
        right_frame = ttk.LabelFrame(pane, text="整理後のファイル構成 (プレビュー)", padding=6)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        tree_frame_r = ttk.Frame(right_frame)
        tree_frame_r.pack(fill="both", expand=True)

        self.tree_organized = ttk.Treeview(tree_frame_r,
                                            columns=("dest",),
                                            show="headings",
                                            selectmode="none")
        self.tree_organized.heading("dest", text="出力先パス")
        self.tree_organized.column("dest", anchor="w")

        sb_r = ttk.Scrollbar(tree_frame_r, orient="vertical",
                              command=self.tree_organized.yview)
        self.tree_organized.configure(yscrollcommand=sb_r.set)
        self.tree_organized.pack(side="left", fill="both", expand=True)
        sb_r.pack(side="right", fill="y")

    # ─── 整理設定 ────────────────────────────
    def _build_settings_section(self):
        # メインコンテナ
        container = ttk.Frame(self.root)
        container.pack(fill="x", padx=16, pady=(4, 6))

        settings_group = ttk.LabelFrame(container, text="整理設定", padding=10)
        settings_group.pack(fill="x")

        # 設定内を3列に分けるためのコンテナ
        cols = ttk.Frame(settings_group)
        cols.pack(fill="x")
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)
        cols.columnconfigure(2, weight=1)

        # --- 全般設定 ---
        f_gen = ttk.LabelFrame(cols, text="全般設定", padding=8)
        f_gen.grid(row=0, column=0, sticky="nsew", padx=4)
        ttk.Checkbutton(f_gen, text="SDカードから削除する",
                         variable=self.var_delete).pack(anchor="w", pady=2)
        ttk.Checkbutton(f_gen, text="プロキシ/サムネを無視",
                         variable=self.var_ignore_proxy,
                         command=self._update_previews).pack(anchor="w", pady=2)
        
        ignore_row = ttk.Frame(f_gen)
        ignore_row.pack(fill="x", padx=(16, 0))
        ttk.Label(ignore_row, text="対象").pack(side="left")
        self.ent_ignore_exts = ttk.Entry(ignore_row, textvariable=self.var_ignore_exts, width=12)
        self.ent_ignore_exts.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # --- 整理設定 ---
        f_date = ttk.LabelFrame(cols, text="整理設定", padding=8)
        f_date.grid(row=0, column=1, sticky="nsew", padx=4)
        ttk.Checkbutton(f_date, text="日付ごとにフォルダ分け",
                         variable=self.var_group_date,
                         command=self._update_previews).pack(anchor="w", pady=2)
        
        fmt_row = ttk.Frame(f_date)
        fmt_row.pack(anchor="w", pady=(4, 0))
        ttk.Label(fmt_row, text="日付形式").pack(side="left")
        self.combo_date_format = ttk.Combobox(
            fmt_row, textvariable=self.var_date_format,
            values=("YYYYMMDD", "YYYY-MM-DD"),
            state="readonly", width=12
        )
        self.combo_date_format.pack(side="left", padx=(4, 0))
        self.combo_date_format.bind("<<ComboboxSelected>>", lambda e: self._update_previews())

        # 階層順序
        order_row = ttk.Frame(f_date)
        order_row.pack(fill="x", pady=(10, 0))
        ttk.Label(order_row, text="階層順序").pack(side="left")
        self.combo_folder_order = ttk.Combobox(
            order_row, textvariable=self.var_folder_order,
            values=(
                "日付 > 種類", 
                "種類 > 日付", 
                "日付 > 種類 > 拡張子", 
                "種類 > 日付 > 拡張子",
                "日付 > 拡張子",
                "種類 > 拡張子",
                "拡張子 > 日付 > 種類"
            ),
            state="readonly", width=25
        )
        self.combo_folder_order.pack(side="left", padx=(4, 0))
        self.combo_folder_order.bind("<<ComboboxSelected>>", lambda e: self._update_previews())

        # --- 動画/写真の整理 ---
        f_type = ttk.LabelFrame(cols, text="動画/写真の整理", padding=8)
        f_type.grid(row=0, column=2, sticky="nsew", padx=4)
        ttk.Checkbutton(f_type, text="動画/写真を別フォルダ",
                         variable=self.var_split_type,
                         command=self._update_previews).pack(anchor="w", pady=2)
        
        v_row = ttk.Frame(f_type)
        v_row.pack(fill="x", pady=(4, 2))
        ttk.Label(v_row, text="動画フォルダ名", width=16).pack(side="left")
        self.ent_video_folder = ttk.Entry(v_row, textvariable=self.var_video_folder)
        self.ent_video_folder.pack(side="left", fill="x", expand=True)

        p_row = ttk.Frame(f_type)
        p_row.pack(fill="x", pady=2)
        ttk.Label(p_row, text="写真フォルダ名", width=16).pack(side="left")
        self.ent_photo_folder = ttk.Entry(p_row, textvariable=self.var_photo_folder)
        self.ent_photo_folder.pack(side="left", fill="x", expand=True)

        m_row = ttk.Frame(f_type)
        m_row.pack(fill="x", pady=(4, 0))
        ttk.Label(m_row, text="その他フォルダ名", width=16).pack(side="left")
        self.ent_misc_folder = ttk.Entry(m_row, textvariable=self.var_misc_folder)
        self.ent_misc_folder.pack(side="left", fill="x", expand=True)

        v_ext_row = ttk.Frame(f_type)
        v_ext_row.pack(fill="x", pady=(4, 2))
        ttk.Label(v_ext_row, text="動画拡張子", width=16).pack(side="left")
        self.ent_video_exts = ttk.Entry(v_ext_row, textvariable=self.var_video_exts)
        self.ent_video_exts.pack(side="left", fill="x", expand=True)

        p_ext_row = ttk.Frame(f_type)
        p_ext_row.pack(fill="x", pady=2)
        ttk.Label(p_ext_row, text="写真拡張子", width=16).pack(side="left")
        self.ent_photo_exts = ttk.Entry(p_ext_row, textvariable=self.var_photo_exts)
        self.ent_photo_exts.pack(side="left", fill="x", expand=True)

        # 列構成の重みを更新 (3列分)
        cols.columnconfigure(2, weight=1)

        # 変数の状態に合わせて有効/無効を切り替えるためのヘルパーを呼ぶ
        self.var_split_type.trace_add("write", lambda *args: self._update_entry_state())
        self.var_ignore_proxy.trace_add("write", lambda *args: self._update_entry_state())
        self._update_entry_state()

    # ─── 処理実行 ────────────────────────────
    def _build_execution_section(self):
        container = ttk.Frame(self.root)
        container.pack(fill="x", padx=16, pady=(4, 12))

        action_group = ttk.LabelFrame(container, text="処理実行", padding=10)
        action_group.pack(fill="x")

        # 上段
        top_row = ttk.Frame(action_group)
        top_row.pack(fill="x")

        self.lbl_progress = ttk.Label(top_row, text="待機中",
                                       font=("Yu Gothic UI", 9))
        self.lbl_progress.pack(side="left")

        ttk.Checkbutton(top_row, text="完了後に保存先フォルダを開く",
                         variable=self.var_open_dest).pack(side="left", padx=(20, 0))

        self.btn_start = ttk.Button(top_row, text="整理・バックアップを開始",
                                     command=self._start_import, state="disabled")
        self.btn_start.pack(side="right")

        # 下段
        self.progressbar = ttk.Progressbar(action_group, orient="horizontal",
                                            mode="determinate",
                                            maximum=100, value=0)
        self.progressbar.pack(fill="x", pady=(8, 0))

    # ─── フォルダ選択 ─────────────────────────
    def _pick_source(self):
        path = filedialog.askdirectory(title="読み込み元 (SDカード) を選択")
        if path:
            self.source_path = path
            self.lbl_source.config(text=path, font=("Yu Gothic UI", 9))
            self._update_previews()
            self._save_config()

    def _pick_dest(self):
        path = filedialog.askdirectory(title="保存先 (ハードディスク等) を選択")
        if path:
            self.dest_path = path
            self.lbl_dest.config(text=path, font=("Yu Gothic UI", 9))
            self._update_start_button()
            self._save_config()

    # ─── プレビュー更新 ───────────────────────
    def _update_previews(self):
        if not self.source_path:
            return

        # ファイルスキャン
        self.detected_files.clear()
        src = Path(self.source_path)
        try:
            for root, dirs, files in os.walk(src):
                for file in files:
                    full_path = Path(root) / file
                    ext = full_path.suffix.lower()

                    if self.var_ignore_proxy.get():
                        # 指定された除外拡張子をパース
                        ignored_exts = self._parse_exts(self.var_ignore_exts.get())
                        if ext in ignored_exts:
                            continue

                    v_exts = self._parse_exts(self.var_video_exts.get())
                    p_exts = self._parse_exts(self.var_photo_exts.get())

                    ftype = "動画" if ext in v_exts else \
                            "写真" if ext in p_exts else \
                            "その他"
                    shot_date = get_media_date(full_path)
                    sz = os.path.getsize(full_path)

                    self.detected_files.append({
                        "path": full_path, "date": shot_date,
                        "type": ftype, "size": sz
                    })
        except Exception as e:
            self.lbl_progress.config(text=f"スキャンエラー: {e}")

        # 整理先プレビュー生成
        self.organized_files.clear()
        for df in self.detected_files:
            # build_dest_path を使って整理先の相対パスを生成
            final_dest = build_dest_path(
                file_path=df["path"],
                date=df["date"],
                file_type=df["type"],
                group_date=self.var_group_date.get(),
                date_format=self.var_date_format.get(),
                split_type=self.var_split_type.get(),
                video_folder=self.var_video_folder.get(),
                photo_folder=self.var_photo_folder.get(),
                misc_folder=self.var_misc_folder.get(),
                folder_order=self.var_folder_order.get(),
            )

            # 表示用の日付文字列を生成（Treeview の撮影日列に使用）
            d_seg = df["date"]
            if self.var_date_format.get() == "YYYYMMDD":
                d_seg = d_seg.replace("-", "")

            self.organized_files.append({
                "src": df["path"],
                "dest": str(final_dest).replace("\\", "/"),
                "display_date": d_seg  # 表示用の日付も保持
            })

        # Treeview 更新 (左)
        self.tree_detected.delete(*self.tree_detected.get_children())
        for i, df in enumerate(self.detected_files):
            # 左側の撮影日表示も選択した形式に合わせる
            display_date = self.organized_files[i]["display_date"]
            
            self.tree_detected.insert("", "end", values=(
                df["path"].name,
                df["type"],
                display_date,
                format_size(df["size"])
            ))

        # Treeview 更新 (右)
        self.tree_organized.delete(*self.tree_organized.get_children())
        for of in self.organized_files:
            self.tree_organized.insert("", "end", values=(of["dest"],))

        self._update_start_button()

    def _update_start_button(self):
        if self.organized_files and self.dest_path:
            self.btn_start.config(state="normal")
        else:
            self.btn_start.config(state="disabled")

    def _update_entry_state(self):
        """チェックボックスの状態に合わせて入力欄の有効/無効を切り替える"""
        # 動画/写真フォルダ名
        state_split = "normal" if self.var_split_type.get() else "disabled"
        self.ent_video_folder.config(state=state_split)
        self.ent_photo_folder.config(state=state_split)
        self.ent_misc_folder.config(state=state_split)
        # 拡張子のカスタマイズ自体は分けなくても使えるため、常に有効でも良いが、
        # UIの一貫性のためにこれらも連動させるか検討。
        # ユーザーは「分類」のために指定するため。

        # 除外拡張子
        state_ignore = "normal" if self.var_ignore_proxy.get() else "disabled"
        self.ent_ignore_exts.config(state=state_ignore)

    def _parse_exts(self, ext_str: str) -> list:
        """カンマ区切りの拡張子文字列を正規化されたリストに変換する"""
        return parse_exts(ext_str)

    # ─── コピー実行 ───────────────────────────
    def _start_import(self):
        if not self.source_path or not self.dest_path:
            return

        self.btn_start.config(state="disabled")
        self.progressbar["value"] = 0
        self.lbl_progress.config(text="準備中...")
        self._save_config()
        threading.Thread(target=self._execute_copy, daemon=True).start()

    def _execute_copy(self):
        try:
            total = len(self.organized_files)
            for i, item in enumerate(self.organized_files):
                src_path = item["src"]
                dest_path = Path(self.dest_path) / item["dest"]

                # UI 更新 (メインスレッド)
                pct = int((i / total) * 100)
                msg = f"コピー中... ({i + 1}/{total}) {src_path.name}"
                self.root.after(0, self._set_progress, pct, msg)

                # コピー
                os.makedirs(dest_path.parent, exist_ok=True)
                shutil.copy2(src_path, dest_path)

                # 削除
                if self.var_delete.get():
                    try:
                        os.remove(src_path)
                    except Exception:
                        pass

            self.root.after(0, self._set_progress, 100, "処理が完了しました。")
            self.root.after(0, self._on_complete)
        except Exception as e:
            self.root.after(0, self._set_progress, 0,
                            f"エラーが発生しました: {e}")
            self.root.after(0, lambda: self.btn_start.config(state="normal"))

    def _set_progress(self, value: int, text: str):
        self.progressbar["value"] = value
        self.lbl_progress.config(text=text)

    def _on_complete(self):
        self.btn_start.config(state="normal")
        messagebox.showinfo("完了", "データの整理が完了しました。")
        if self.var_open_dest.get():
            try:
                os.startfile(self.dest_path)
            except Exception:
                pass

    # ─── 設定の保存・読み込み ─────────────────
    def _get_config_path(self) -> Path:
        """設定ファイルのパスを返す"""
        return Path(__file__).parent / "config.json"

    def _load_config(self):
        """設定を読み込む"""
        path = self._get_config_path()
        if not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                conf = json.load(f)

            # パス
            self.source_path = conf.get("source_path", "")
            if self.source_path:
                self.lbl_source.config(text=self.source_path, font=("Yu Gothic UI", 9))
            
            self.dest_path = conf.get("dest_path", "")
            if self.dest_path:
                self.lbl_dest.config(text=self.dest_path, font=("Yu Gothic UI", 9))

            # チェックボックス・変数
            # BooleanVar
            self.var_delete.set(conf.get("delete", False))
            self.var_ignore_proxy.set(conf.get("ignore_proxy", True))
            self.var_group_date.set(conf.get("group_date", True))
            self.var_split_type.set(conf.get("split_type", True))
            self.var_open_dest.set(conf.get("open_dest", True))
            
            # StringVar
            self.var_date_format.set(conf.get("date_format", "YYYYMMDD"))
            self.var_video_folder.set(conf.get("video_folder", "Videos"))
            self.var_photo_folder.set(conf.get("photo_folder", "Photos"))
            self.var_ignore_exts.set(conf.get("ignore_exts", ".LRF, .THM"))
            self.var_folder_order.set(conf.get("folder_order", "日付 > 種類"))
            self.var_video_exts.set(conf.get("video_exts", ".MP4"))
            self.var_photo_exts.set(conf.get("photo_exts", ".JPG, .DNG, .JPEG"))
            self.var_misc_folder.set(conf.get("misc_folder", "Misc"))

            # UI状態の更新
            self._update_entry_state()
            self._update_previews()

        except Exception as e:
            print(f"Failed to load config: {e}")

    def _save_config(self):
        """現在の設定を保存する"""
        conf = {
            "source_path": self.source_path,
            "dest_path": self.dest_path,
            "delete": self.var_delete.get(),
            "ignore_proxy": self.var_ignore_proxy.get(),
            "group_date": self.var_group_date.get(),
            "split_type": self.var_split_type.get(),
            "open_dest": self.var_open_dest.get(),
            "date_format": self.var_date_format.get(),
            "video_folder": self.var_video_folder.get(),
            "photo_folder": self.var_photo_folder.get(),
            "ignore_exts": self.var_ignore_exts.get(),
            "folder_order": self.var_folder_order.get(),
            "video_exts": self.var_video_exts.get(),
            "photo_exts": self.var_photo_exts.get(),
            "misc_folder": self.var_misc_folder.get(),
        }

        try:
            with open(self._get_config_path(), "w", encoding="utf-8") as f:
                json.dump(conf, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def _on_closing(self):
        """ウィンドウを閉じる前の処理"""
        self._save_config()
        self.root.destroy()


# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = OsmoOrganizerApp(root)
    root.mainloop()
