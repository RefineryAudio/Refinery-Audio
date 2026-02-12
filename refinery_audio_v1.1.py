import os
import re
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError
import webbrowser

# ---------- RESOURCE PATH ----------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------- COLORS ----------
BG = "#000000"
PANEL = "#252526"
WHITE = "#FFFFFF"
BLUE = "#00BFFF"
GRAY = "#9E9E9E"
ORANGE = "#FF9800"
EDIT_ROW_BG = "#1ABCFF"
GRAPHITE = "#3A3A3A"
POPUP_BG = "#1E1E2F"
ENTRY_BG = "#2D2D44"
ENTRY_FG = "#FFFFFF"

PRESTIGE_ENABLED_COLORS = {
    "White": WHITE, "Gold": "#FFD700", "Electric Blue": "#1E90FF",
    "Teal": "#1ABC9C", "Violet": "#8A2BE2", "Orange": ORANGE,
    "Cyan": "#00FFFF", "Magenta": "#FF00FF", "Lime Green": "#32CD32",
    "Crimson": "#DC143C", "Pink": "#FF69B4", "Turquoise": "#40E0D0",
    "Neon Indigo": "#6F00FF", "Solar Flare": "#FF4500", "Electric Lime": "#CCFF00",
    "Hot Magenta": "#FF1493"
}

ROW_COLORS = {"enabled": WHITE, "disabled": GRAY, "manual": BLUE}

# ---------- UTILS ----------
def strip_junk(text):
    patterns = [
        r"\(.*?official.*?\)", r"\bofficial audio\b", r"\bofficial video\b",
        r"\blyrics\b", r"\bremaster(ed)?\b", r"\bhq\b", r"\bhigh quality\b"
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" -_–")

def smart_title_parse(name):
    match = re.search(r"\(([^)]*[\-–][^)]*)\)", name)
    if match:
        inside = match.group(1)
        parts = re.split(r"\s*[–\-]\s*", inside)
        return strip_junk(parts[-1])
    if "-" in name:
        parts = re.split(r"\s*[–\-]\s*", name)
        return strip_junk(parts[-1])
    return strip_junk(name)

def safe_rename(src, dst):
    if os.path.exists(dst):
        return False
    os.rename(src, dst)
    return True

def write_id3_tags(file_path, title="", artist="", album_artist="", album="", year="", genre=""):
    try:
        audio = EasyID3(file_path)
    except ID3NoHeaderError:
        audio = EasyID3()
        audio.save(file_path)
        audio = EasyID3(file_path)
    if title: audio['title'] = title
    if artist: audio['artist'] = artist
    if album_artist: audio['albumartist'] = album_artist
    if album: audio['album'] = album
    if year: audio['date'] = year
    if genre: audio['genre'] = genre
    audio.save()

def nuke_id3_tags(file_path):
    try:
        audio = ID3(file_path)
        audio.delete()
        audio.save()
    except ID3NoHeaderError:
        pass

# ---------- APP ----------
class RefineryAudio:
    def __init__(self, root):
        self.root = root
        root.title("Refinery Audio – Prestige Build")
        root.geometry("1280x680")
        root.configure(bg=BG)

        self.files = []
        self.enabled = {}
        self.manual = {}
        self.original = {}
        self.metadata = {}
        self.undo_stack = []

        self.mode = tk.StringVar(value="artist")
        self.artist = tk.StringVar()
        self.nuke_metadata = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Ready")
        self.row_colors = ROW_COLORS.copy()
        self.enabled_color_var = tk.StringVar(value="White")

        self.build_ui()

    # ---------- UI ----------
    def build_ui(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(6,3), pady=6)

        logo_frame = tk.Frame(left, bg=BG)
        logo_frame.pack(anchor="w", pady=(0,4))

        try:
            self.logo_img = tk.PhotoImage(file=resource_path("Refinery_Logo.png"))
            tk.Label(logo_frame, image=self.logo_img, bg=BG).pack(anchor="w", side="left")
        except Exception:
            tk.Label(logo_frame, text="Refinery Audio", bg=BG, fg=WHITE, font=("Arial", 24)).pack(anchor="w", side="left")

        kofi_label = tk.Label(
            logo_frame,
            text="— Free to use. Supported by users.",
            fg=ORANGE,
            bg=BG,
            cursor="hand2",
            font=("Arial", 12, "bold")
        )
        kofi_label.pack(anchor="w", side="left", padx=(20,0))
        kofi_label.bind("<Button-1>", lambda e: webbrowser.open("https://ko-fi.com/refineryaudio"))

        pulse_colors = ["#FFA500", "#FFB833", "#FFC966", "#FFD700"]
        pulse_index = 0
        def pulse():
            nonlocal pulse_index
            kofi_label.config(fg=pulse_colors[pulse_index])
            pulse_index = (pulse_index + 1) % len(pulse_colors)
            self.root.after(500, pulse)
        pulse()

        self.build_toolbar(left)
        self.build_tree(left)

        right = tk.Frame(main, bg=PANEL, width=280)
        right.pack(side="right", fill="y", padx=(3,6), pady=6)
        right.pack_propagate(False)
        self.build_right_panel(right)

    # ---------- TOOLBAR ----------
    def build_toolbar(self, parent):
        bar = tk.Frame(parent, bg=PANEL)
        bar.pack(fill="x", pady=(0,6))
        def btn(txt, cmd):
            tk.Button(bar, text=txt, command=cmd, bg="#333333", fg=WHITE, relief="flat", padx=10).pack(side="left", padx=4)
        btn("Add Folder", self.add_folder)
        btn("Add Files", self.add_files)
        btn("Clear", self.clear_session)
        btn("Select All", self.select_all)
        btn("Deselect All", self.deselect_all)
        btn("Apply Changes", self.refine)
        btn("Undo", self.undo)

    # ---------- TREE ----------
    def build_tree(self, parent):
        cols = ("enabled","original","preview")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings")
        self.tree.pack(fill="both", expand=True)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=BG, fieldbackground=BG, foreground=WHITE, rowheight=24)
        style.configure("Treeview.Heading", background=PANEL, foreground=WHITE)
        self.tree.heading("enabled", text="Enabled", anchor="center")
        self.tree.heading("original", text="Original Name", anchor="w")
        self.tree.heading("preview", text="Preview Name", anchor="w")
        self.tree.column("enabled", width=80, anchor="center", stretch=False)
        self.tree.column("original", width=460)
        self.tree.column("preview", width=460)
        self.tree.tag_configure("enabled", foreground=self.row_colors["enabled"], background=BG)
        self.tree.tag_configure("disabled", foreground=self.row_colors["disabled"], background=BG)
        self.tree.tag_configure("manual", foreground=self.row_colors["manual"], background=BG)
        self.tree.tag_configure("edit", foreground="black", background=EDIT_ROW_BG)
        self.tree.bind("<Double-1>", self.edit_single)

    # ---------- RIGHT PANEL ----------
    def build_right_panel(self, parent):
        info = tk.LabelFrame(parent, text="Session Info", bg=PANEL, fg=WHITE)
        info.pack(fill="x", padx=8, pady=(8,4))
        self.info_label = tk.Label(info, text="", bg=PANEL, fg=WHITE, justify="left")
        self.info_label.pack(anchor="w", padx=6, pady=6)

        naming = tk.LabelFrame(parent, text="Naming", bg=PANEL, fg=WHITE)
        naming.pack(fill="x", padx=8, pady=4)
        tk.Radiobutton(naming, text="Artist - Title", variable=self.mode, value="artist", bg=PANEL, fg=WHITE, selectcolor=PANEL).pack(anchor="w", padx=6)
        tk.Radiobutton(naming, text="Title Only", variable=self.mode, value="title", bg=PANEL, fg=WHITE, selectcolor=PANEL).pack(anchor="w", padx=6)
        tk.Entry(naming, textvariable=self.artist, bg=GRAPHITE, fg=WHITE, insertbackground=WHITE).pack(fill="x", padx=6, pady=6)
        self.artist.trace_add("write", lambda *_: self.refresh_tree())
        self.mode.trace_add("write", lambda *_: self.refresh_tree())

        color_frame = tk.LabelFrame(parent, text="Enabled Row Color", bg=PANEL, fg=WHITE)
        color_frame.pack(fill="x", padx=8, pady=4)
        opt = tk.OptionMenu(color_frame, self.enabled_color_var, *PRESTIGE_ENABLED_COLORS.keys(), command=self.change_enabled_color)
        opt.configure(bg="#333333", fg=WHITE, relief="flat")
        opt.pack(fill="x", padx=6, pady=4)

        actions = tk.LabelFrame(parent, text="Actions", bg=PANEL, fg=WHITE)
        actions.pack(fill="x", padx=8, pady=4)
        tk.Button(actions, text="Edit Metadata", bg="#333333", fg=WHITE, relief="flat", command=self.edit_metadata).pack(fill="x", padx=6, pady=4)
        tk.Button(actions, text="Change Manifest", bg="#333333", fg=WHITE, relief="flat", command=self.export_report).pack(fill="x", padx=6, pady=4)
        tk.Checkbutton(actions, text="NUKE METADATA (ALL AUDIO)", variable=self.nuke_metadata, bg=PANEL, fg=ORANGE, selectcolor=PANEL).pack(anchor="w", padx=6, pady=6)

        status = tk.LabelFrame(parent, text="Status", bg=PANEL, fg=WHITE)
        status.pack(fill="x", padx=8, pady=(4,8))
        tk.Label(status, textvariable=self.status, bg=PANEL, fg=WHITE).pack(anchor="w", padx=6, pady=6)

    # ---------- CHANGE ENABLED ROW COLOR ----------
    def change_enabled_color(self, color_name):
        self.row_colors["enabled"] = PRESTIGE_ENABLED_COLORS.get(color_name, WHITE)
        self.tree.tag_configure("enabled", foreground=self.row_colors["enabled"])
        self.refresh_tree()

    # ---------- TREE REFRESH ----------
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        title_only_mode = self.mode.get() == "title"
        for f in self.files:
            enabled = "✔" if self.enabled.get(f, True) else ""
            original = os.path.basename(f)
            clean_title = smart_title_parse(original)
            artist = self.artist.get() if self.artist.get() else self.metadata.get(f, {}).get("Contributing Artist","")
            preview = clean_title if title_only_mode else f"{artist} - {clean_title}" if artist else clean_title
            tag = "manual" if f in self.manual and self.manual[f] != original else ("enabled" if self.enabled.get(f, True) else "disabled")
            self.tree.insert("", "end", values=(enabled, original, preview), tags=(tag,))

    # ---------- BUTTON METHODS ----------
    def add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder: return
        new_files = []
        for root_dir, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(".mp3"):
                    full_path = os.path.join(root_dir, f)
                    if full_path not in self.files:
                        new_files.append(full_path)
        self.files += new_files
        for f in new_files: self.enabled.setdefault(f, True)
        self.refresh_tree()
        self.status.set(f"Added {len(new_files)} files from folder")

    def add_files(self):
        files = filedialog.askopenfilenames(title="Select MP3 Files", filetypes=[("MP3 Files","*.mp3")])
        for f in files:
            if f not in self.files:
                self.files.append(f)
                self.enabled.setdefault(f, True)
        self.refresh_tree()
        self.status.set(f"Added {len(files)} files")

    def clear_session(self):
        if messagebox.askyesno("Confirm", "Clear current session?"):
            self.files.clear()
            self.enabled.clear()
            self.manual.clear()
            self.original.clear()
            self.metadata.clear()
            self.undo_stack.clear()
            self.refresh_tree()
            self.status.set("Session cleared")

    def select_all(self):
        for f in self.files: self.enabled[f] = True
        self.refresh_tree()
        self.status.set("All files selected")

    def deselect_all(self):
        for f in self.files: self.enabled[f] = False
        self.refresh_tree()
        self.status.set("All files deselected")

    # ---------- APPLY CHANGES (FULL FIX) ----------
    def refine(self):
        if not self.files:
            messagebox.showwarning("Warning", "No files to process")
            return
        self.undo_stack.append(self.files.copy())
        title_only_mode = self.mode.get() == "title"
        for f in list(self.files):
            if not self.enabled.get(f, True):
                continue
            self.original[f] = os.path.basename(f)
            artist = self.artist.get() if self.artist.get() else self.metadata.get(f, {}).get("Contributing Artist","")
            clean_title = smart_title_parse(os.path.basename(f))
            new_name = clean_title if title_only_mode else f"{artist} - {clean_title}" if artist else clean_title
            base_dir = os.path.dirname(f)
            new_path = os.path.join(base_dir, new_name)
            if f != new_path:
                if safe_rename(f, new_path):
                    self.files[self.files.index(f)] = new_path
                    self.manual[new_path] = self.manual.pop(f, new_name)
                    self.metadata[new_path] = self.metadata.pop(f, {})
                    self.enabled[new_path] = self.enabled.pop(f, True)
                    f = new_path
            if self.nuke_metadata.get():
                nuke_id3_tags(f)
        self.refresh_tree()
        self.status.set("Apply Changes complete")

    # ---------- UNDO ----------
    def undo(self):
        if not self.undo_stack: messagebox.showinfo("Info", "Nothing to undo"); return
        self.files = self.undo_stack.pop()
        self.refresh_tree()
        self.status.set("Undo applied")

    # ---------- SINGLE ROW MANUAL EDIT ----------
    def edit_single(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row_id: return
        idx = self.tree.index(row_id)
        f = self.files[idx]
        if col == "#1":
            self.enabled[f] = not self.enabled.get(f, True)
            self.refresh_tree()
            return
        popup = tk.Toplevel(self.root)
        popup.title("Manual Edit")
        popup.geometry("400x200")
        popup.configure(bg=POPUP_BG)
        tk.Label(popup, text="New File Name:", bg=POPUP_BG, fg=ENTRY_FG).pack(anchor="w", padx=10, pady=(10,0))
        title_var = tk.StringVar(value=os.path.basename(f))
        tk.Entry(popup, textvariable=title_var, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG).pack(fill="x", padx=10)
        btn_frame = tk.Frame(popup, bg=POPUP_BG)
        btn_frame.pack(pady=10)
        def apply_changes():
            new_name = title_var.get()
            base_dir = os.path.dirname(f)
            new_path = os.path.join(base_dir, new_name)
            if safe_rename(f, new_path):
                self.manual[new_path] = self.manual.pop(f, new_name)
                self.metadata[new_path] = self.metadata.pop(f, self.metadata.get(f, {}))
                self.enabled[new_path] = self.enabled.pop(f, True)
                self.files[self.files.index(f)] = new_path
                popup.destroy()
                self.refresh_tree()
        tk.Button(btn_frame, text="Apply", bg="#333333", fg=WHITE, relief="flat", command=apply_changes).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", bg="#333333", fg=WHITE, relief="flat", command=popup.destroy).pack(side="left", padx=10)

    # ---------- METADATA EDIT ----------
    def edit_metadata(self):
        selected_rows = [f for f in self.files if self.enabled.get(f, True)]
        if not selected_rows: messagebox.showinfo("Info", "No files enabled for editing"); return
        popup = tk.Toplevel(self.root)
        popup.title("Edit Metadata")
        popup.geometry("400x350")
        popup.configure(bg=POPUP_BG)
        fields = ["Title","Contributing Artist","Album Artist","Album","Year","Genre"]
        vars_dict = {}
        for f in fields:
            tk.Label(popup, text=f"{f}:", bg=POPUP_BG, fg=ENTRY_FG).pack(anchor="w", padx=10, pady=(5,0))
            v = tk.StringVar()
            vars_dict[f] = v
            tk.Entry(popup, textvariable=v, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG).pack(fill="x", padx=10)
        def apply_all():
            for f in selected_rows:
                write_id3_tags(f,
                              title=vars_dict["Title"].get(),
                              artist=vars_dict["Contributing Artist"].get(),
                              album_artist=vars_dict["Album Artist"].get(),
                              album=vars_dict["Album"].get(),
                              year=vars_dict["Year"].get(),
                              genre=vars_dict["Genre"].get())
            popup.destroy()
            self.status.set("Metadata updated")
        tk.Button(popup, text="Apply", bg="#333333", fg=WHITE, relief="flat", command=apply_all).pack(pady=10)

    def export_report(self):
        messagebox.showinfo("Export", "Report export not yet implemented")

# ---------- MAIN ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = RefineryAudio(root)
    root.mainloop()
