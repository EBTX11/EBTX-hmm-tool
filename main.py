import tkinter as tk
from tkinter import ttk, filedialog
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from modules.config_manager import ConfigManager
from modules.pays_frame import PaysFrame
from modules.character_frame import CharacterFrame
from modules.currency_frame import CurrencyFrame
from modules.population_frame import PopulationFrame
from modules.tech_frame import TechFrame
from modules.province_frame import ProvinceFrame
from modules.map_frame import MapFrame


# ============================================================
# FRAME CONFIG
# ============================================================

class ConfigFrame(ttk.Frame):
    def __init__(self, parent, config, on_save=None):
        super().__init__(parent)
        self.config = config
        self.on_save = on_save
        self._build()

    def _build(self):
        ttk.Label(self, text="Configuration", font=("Segoe UI", 15, "bold")).pack(pady=(25, 10))

        ttk.Label(self, text="Configure les chemins une seule fois.\nTous les outils utiliseront ces parametres.",
                  justify="center", font=("Segoe UI", 9)).pack(pady=(0, 20))

        # Mod path
        grp = ttk.LabelFrame(self, text="Chemins du projet")
        grp.pack(fill="x", padx=40, pady=5)

        row = ttk.Frame(grp)
        row.pack(fill="x", padx=10, pady=8)
        ttk.Label(row, text="Dossier du Mod :", width=24, anchor="w").pack(side="left")
        self._mod_var = tk.StringVar(value=self.config.get("mod_path"))
        ttk.Entry(row, textvariable=self._mod_var, width=50).pack(side="left", padx=5)
        ttk.Button(row, text="Parcourir", command=self._browse_mod).pack(side="left")

        row2 = ttk.Frame(grp)
        row2.pack(fill="x", padx=10, pady=8)
        ttk.Label(row2, text="Victoria 3 (Vanilla) :", width=24, anchor="w").pack(side="left")
        self._vanilla_var = tk.StringVar(value=self.config.get("vanilla_path"))
        ttk.Entry(row2, textvariable=self._vanilla_var, width=50).pack(side="left", padx=5)
        ttk.Button(row2, text="Parcourir", command=self._browse_vanilla).pack(side="left")

        ttk.Button(self, text="  Sauvegarder la configuration  ",
                   command=self._save).pack(pady=20)

        self._status = ttk.Label(self, text="", foreground="#22aa55")
        self._status.pack()

    def _browse_mod(self):
        path = filedialog.askdirectory(title="Selectionne le dossier du mod")
        if path:
            self._mod_var.set(path)

    def _browse_vanilla(self):
        path = filedialog.askdirectory(title="Selectionne le dossier Victoria 3")
        if path:
            self._vanilla_var.set(path)

    def _save(self):
        self.config.set("mod_path", self._mod_var.get())
        self.config.set("vanilla_path", self._vanilla_var.get())
        self.config.save()
        self._status.config(text="Configuration sauvegardee !")
        if self.on_save:
            self.on_save()


# ============================================================
# APPLICATION PRINCIPALE
# ============================================================

class EBTXApp:
    # Couleurs
    C_BG      = "#1e1e2e"
    C_SIDEBAR = "#181825"
    C_SURFACE = "#313244"
    C_SURFACE2 = "#45475a"
    C_FG      = "#cdd6f4"
    C_ACCENT  = "#cba6f7"
    C_GREEN   = "#a6e3a1"
    C_RED     = "#f38ba8"

    def __init__(self, root):
        self.root = root
        self.root.title("EBTX-HMM Tool  —  Victoria 3 Mod Editor")
        self.root.geometry("1280x780")
        self.root.minsize(960, 620)

        self.config = ConfigManager()
        self._current_key = None
        self._current_frame = None

        self._setup_style()
        self._build_layout()
        self._build_frames()
        self._show_frame("config")

    # ----------------------------------------------------------
    # STYLE
    # ----------------------------------------------------------

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        BG = self.C_BG
        SIDEBAR = self.C_SIDEBAR
        SURF = self.C_SURFACE
        SURF2 = self.C_SURFACE2
        FG = self.C_FG
        ACC = self.C_ACCENT

        self.root.configure(bg=BG)

        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 9))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=SURF, foreground=FG, borderwidth=0,
                        relief="flat", padding=(8, 5))
        style.map("TButton",
                  background=[("active", SURF2), ("pressed", SURF2)],
                  foreground=[("active", ACC)])
        style.configure("Accent.TButton", background=ACC, foreground=BG, font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#b4befe")])

        style.configure("Sidebar.TFrame", background=SIDEBAR)
        style.configure("SidebarTitle.TLabel", background=SIDEBAR, foreground=ACC,
                        font=("Segoe UI", 13, "bold"))
        style.configure("SidebarSub.TLabel", background=SIDEBAR, foreground="#6c7086",
                        font=("Segoe UI", 8))

        style.configure("Nav.TButton", background=SIDEBAR, foreground=FG,
                        font=("Segoe UI", 10), borderwidth=0, relief="flat",
                        padding=(12, 9), anchor="w")
        style.map("Nav.TButton",
                  background=[("active", SURF), ("pressed", SURF)],
                  foreground=[("active", ACC)])

        style.configure("NavActive.TButton", background=SURF, foreground=ACC,
                        font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat",
                        padding=(12, 9), anchor="w")

        style.configure("TopBar.TFrame", background=SURF)
        style.configure("TopBar.TLabel", background=SURF, foreground=FG, font=("Segoe UI", 9))
        style.configure("TopBarPath.TLabel", background=SURF, foreground="#888",
                        font=("Segoe UI", 8))

        style.configure("TEntry", fieldbackground=SURF, foreground=FG,
                        insertcolor=FG, borderwidth=1)
        style.configure("TCombobox", fieldbackground=SURF, foreground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", SURF)])

        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURF, foreground=FG,
                        padding=(10, 5), font=("Segoe UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", SURF2)],
                  foreground=[("selected", ACC)])

        style.configure("TLabelframe", background=BG, foreground=FG, bordercolor=SURF2)
        style.configure("TLabelframe.Label", background=BG, foreground=ACC,
                        font=("Segoe UI", 9, "bold"))

        style.configure("TScrollbar", background=SURF, troughcolor=BG, borderwidth=0)
        style.configure("TCheckbutton", background=BG, foreground=FG)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TOptionMenu", background=SURF, foreground=FG)
        style.configure("TSeparator", background=SURF2)

    # ----------------------------------------------------------
    # LAYOUT
    # ----------------------------------------------------------

    def _build_layout(self):
        # Sidebar
        self.sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=200)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Top bar + content
        right = ttk.Frame(self.root)
        right.pack(side="right", fill="both", expand=True)

        self.topbar = ttk.Frame(right, style="TopBar.TFrame", height=36)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        self._topbar_label = ttk.Label(self.topbar, text="Mod: (non configure)",
                                        style="TopBarPath.TLabel")
        self._topbar_label.pack(side="left", padx=12, pady=8)

        self.content = ttk.Frame(right)
        self.content.pack(fill="both", expand=True)

        # Sidebar content
        ttk.Label(self.sidebar, text="EBTX-HMM", style="SidebarTitle.TLabel").pack(pady=(20, 2))
        ttk.Label(self.sidebar, text="Victoria 3 Mod Tool", style="SidebarSub.TLabel").pack(pady=(0, 12))

        sep = tk.Frame(self.sidebar, bg=self.C_SURFACE, height=1)
        sep.pack(fill="x", padx=12, pady=4)

        self._nav_buttons = {}
        nav_items = [
            ("Config",       "config"),
            ("Carte",        "carte"),
            ("Pays",         "pays"),
            ("Personnages",  "perso"),
            ("Devises",      "devises"),
            ("Population",   "population"),
            ("Technologie",  "tech"),
            ("Provinces",    "provinces"),
        ]
        for label, key in nav_items:
            btn = ttk.Button(self.sidebar, text=label, style="Nav.TButton",
                             command=lambda k=key: self._show_frame(k))
            btn.pack(fill="x", padx=6, pady=1)
            self._nav_buttons[key] = btn

        sep2 = tk.Frame(self.sidebar, bg=self.C_SURFACE, height=1)
        sep2.pack(fill="x", padx=12, pady=(12, 4), side="bottom")
        ttk.Label(self.sidebar, text="v1.0 — EBTX-HMM", style="SidebarSub.TLabel").pack(
            side="bottom", pady=6)

    # ----------------------------------------------------------
    # FRAMES
    # ----------------------------------------------------------

    def _build_frames(self):
        self._frames = {}

        self._frames["config"]     = ConfigFrame(
            self.content, self.config, on_save=self._refresh_topbar
        )
        self._frames["carte"]      = MapFrame(self.content, self.config)
        self._frames["pays"]       = PaysFrame(self.content, self.config)
        self._frames["perso"]      = CharacterFrame(self.content, self.config)
        self._frames["devises"]    = CurrencyFrame(self.content, self.config)
        self._frames["population"] = PopulationFrame(self.content, self.config)
        self._frames["tech"]       = TechFrame(self.content, self.config)
        self._frames["provinces"]  = ProvinceFrame(self.content, self.config)

    # ----------------------------------------------------------
    # NAVIGATION
    # ----------------------------------------------------------

    def _show_frame(self, key):
        if self._current_frame:
            self._current_frame.pack_forget()
        if self._current_key and self._current_key in self._nav_buttons:
            self._nav_buttons[self._current_key].configure(style="Nav.TButton")

        self._frames[key].pack(fill="both", expand=True)
        self._current_frame = self._frames[key]
        self._current_key = key
        self._nav_buttons[key].configure(style="NavActive.TButton")

    def _refresh_topbar(self):
        mod = self.config.mod_path
        if mod:
            name = os.path.basename(mod)
            self._topbar_label.config(text=f"Mod: {name}   ({mod})")
        else:
            self._topbar_label.config(text="Mod: (non configure)")


# ============================================================
# ENTREE
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = EBTXApp(root)

    # Actualiser la topbar si un chemin est deja configure
    app._refresh_topbar()

    # Aller directement aux outils si deja configure
    if app.config.mod_path:
        app._show_frame("pays")

    root.mainloop()
