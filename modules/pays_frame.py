import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import os
import re
from modules.tech_frame import TechFrame

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def find_block_end(text, start_index):
    depth = 0
    for i in range(start_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def tag_exists(tag, file_path):
    if not os.path.exists(file_path):
        return False
    with open(file_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    return bool(re.search(rf"\b{tag}\s*=\s*{{", content))


class PaysFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._selected_country_tag = None
        self._build()

    def _build(self):
        ttk.Label(self, text="Outils Pays", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        self._build_country_sidebar(main)

        right_panel = ttk.Frame(main)
        right_panel.pack(side="right", fill="both", expand=True, padx=15, pady=10)

        nb = ttk.Notebook(right_panel)
        nb.pack(fill="both", expand=True)

        self._tab_generale(nb)
        self._tab_lois(nb)
        self._tab_techno_generale(nb)
        self._tab_diplomacy(nb)
        self._tab_power_blocs(nb)
        self._tab_military_formation(nb)
    # ---------------- SIDEBAR ----------------

    def _build_country_sidebar(self, parent):
        sidebar = ttk.LabelFrame(parent, text="Pays du mod")
        sidebar.pack(side="left", fill="y", padx=(15, 0), pady=10)

        search_frame = ttk.Frame(sidebar)
        search_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(search_frame, text="Rechercher:").pack(anchor="w")
        self._country_search_var = tk.StringVar()
        self._country_search_var.trace("w", self._filter_country_list)
        ttk.Entry(search_frame, textvariable=self._country_search_var).pack(fill="x")

        list_frame = ttk.Frame(sidebar)
        list_frame.pack(fill="both", expand=True)

        self._country_listbox = tk.Listbox(list_frame)
        self._country_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, command=self._country_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._country_listbox.config(yscrollcommand=scrollbar.set)

        self._country_listbox.bind("<<ListboxSelect>>", self._on_country_select)

        ttk.Button(sidebar, text="Charger les pays", command=self._load_country_list).pack(pady=5)

    def _load_country_list(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        countries_dir = os.path.join(mod, "common", "history", "countries")
        if not os.path.exists(countries_dir):
            messagebox.showerror("Erreur", "Dossier countries introuvable")
            return

        self._countries = []
        for fname in sorted(os.listdir(countries_dir)):
            if fname.endswith(".txt") and " - " in fname:
                tag, name = fname.replace(".txt", "").split(" - ", 1)
                self._countries.append((tag, name))

        self._countries.sort(key=lambda x: x[1].lower())
        self._update_country_listbox()

    def _update_country_listbox(self):
        self._country_listbox.delete(0, tk.END)
        search = self._country_search_var.get().lower()

        for tag, name in self._countries:
            if search in name.lower() or search in tag.lower():
                self._country_listbox.insert(tk.END, f"{name} ({tag})")

    def _filter_country_list(self, *args):
        self._update_country_listbox()

    def _on_country_select(self, event):
        selection = self._country_listbox.curselection()
        if not selection:
            return

        selected_text = self._country_listbox.get(selection[0])
        match = re.search(r'\(([A-Za-z0-9]{2,4})\)', selected_text)
        if match:
            self._selected_country_tag = match.group(1).upper()
            self._fill_tag_in_tabs(self._selected_country_tag)

    def _fill_tag_in_tabs(self, tag):
        if hasattr(self, '_mod_tag'):
            self._mod_tag.set(tag)
        if hasattr(self, '_dyn_tag'):
            self._dyn_tag.set(tag)
        if hasattr(self, '_hist_tag'):
            self._hist_tag.set(tag)
        if hasattr(self, '_gen_tag_var'):
            self._gen_tag_var.set(tag)
            self._load_general_data()
        if hasattr(self, '_dipl_tag_var'):
            self._dipl_tag_var.set(tag)
            self._load_diplomacy_data()
        if hasattr(self, '_pb_tag_var'):
            self._pb_tag_var.set(tag)
        if hasattr(self, '_mil_tag_var'):
            self._mil_tag_var.set(tag)
            self._mil_manage_tag.set(tag)
            self._mil_load_formations()

    # ---------------- HELPERS DONNÉES ----------------

    def _parse_cultures(self):
        path = os.path.join(DATA_DIR, "cultures", "00_cultures.txt")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        return sorted(re.findall(r'^(\w+)\s*=\s*\{', content, re.MULTILINE))

    def _parse_religions(self):
        path = os.path.join(DATA_DIR, "religions", "religion.txt")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        return sorted(re.findall(r'^(\w+)\s*=\s*\{', content, re.MULTILINE))

    def _def_block_indices(self, content, tag):
        """Retourne (tag_start, tag_end, inner_start, inner_end) pour le bloc TAG = { ... }.
        Utilise un comptage de braces pour gérer n'importe quel niveau d'imbrication."""
        m = re.search(rf'(?<![a-zA-Z0-9_]){re.escape(tag)}\s*\??\s*=\s*\{{', content)
        if not m:
            return None
        brace_open = m.end() - 1
        depth = 0
        for i in range(brace_open, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    return (m.start(), i + 1, brace_open + 1, i)
        return None

    def _ensure_law_groups(self):
        if not hasattr(self, '_law_groups') or not self._law_groups:
            self._law_groups = {}
            self._law_vars = getattr(self, '_law_vars', {})
            laws_dir = os.path.join(DATA_DIR, "laws")
            if os.path.exists(laws_dir):
                for fname in os.listdir(laws_dir):
                    if not fname.endswith(".txt"):
                        continue
                    with open(os.path.join(laws_dir, fname), "r", encoding="utf-8-sig") as fh:
                        content = fh.read()
                    for law, group in re.findall(
                        r'(law_\w+)\s*=\s*{[^}]*?group\s*=\s*(lawgroup_\w+)', content, re.DOTALL
                    ):
                        self._law_groups.setdefault(group, []).append(law)
                for g in self._law_groups:
                    self._law_groups[g] = sorted(set(self._law_groups[g]))

    # ---------------- TABS ----------------

    def _tab_generale(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Generale")

        self._ensure_law_groups()

        # Variables
        self._gen_tag_var   = tk.StringVar()
        self._gen_name      = tk.StringVar()
        self._gen_adj       = tk.StringVar()
        self._gen_dyn_name  = tk.StringVar()
        self._gen_dyn_adj   = tk.StringVar()
        self._gen_capital   = tk.StringVar()
        self._gen_tier      = tk.StringVar(value="kingdom")
        self._gen_type      = tk.StringVar(value="recognized")
        self._gen_religion  = tk.StringVar()
        self._gen_gov       = tk.StringVar()
        self._gen_econ      = tk.StringVar()
        self._gen_trade     = tk.StringVar()
        self._gen_power     = tk.StringVar()
        self._gen_ruler_first    = tk.StringVar()
        self._gen_ruler_last     = tk.StringVar()
        self._gen_ruler_culture  = tk.StringVar()
        self._gen_ruler_birth    = tk.StringVar()
        self._gen_ruler_ig       = tk.StringVar()
        self._gen_ruler_ideology = tk.StringVar()
        self._gen_ruler_female   = tk.BooleanVar(value=False)
        self._gen_color_rgb = [100, 100, 100]

        # ── Barre du haut ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 4))

        ttk.Label(top, text="Pays :").pack(side="left")
        ttk.Entry(top, textvariable=self._gen_tag_var, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 12))
        ttk.Button(top, text="Charger", command=self._load_general_data).pack(side="left", padx=3)
        self._gen_status = ttk.Label(top, text="Sélectionne un pays dans la liste", foreground="#888")
        self._gen_status.pack(side="left", padx=10)
        tk.Button(top, text="Sauvegarder", command=self._save_general_data,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="right", padx=5)

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=(4, 0))

        # ── Zone scrollable ────────────────────────────────────
        wrapper = ttk.Frame(f)
        wrapper.pack(fill="both", expand=True)

        bg = ttk.Style().lookup("TFrame", "background")
        gc = tk.Canvas(wrapper, borderwidth=0, highlightthickness=0, bg=bg)
        gs = ttk.Scrollbar(wrapper, orient="vertical", command=gc.yview)
        gi = ttk.Frame(gc)
        gi.bind("<Configure>", lambda e: gc.configure(scrollregion=gc.bbox("all")))
        gw = gc.create_window((0, 0), window=gi, anchor="nw")
        gc.configure(yscrollcommand=gs.set)
        gc.bind("<Configure>", lambda e: gc.itemconfig(gw, width=e.width))
        gc.bind_all("<MouseWheel>", lambda e: gc.yview_scroll(-1 * (e.delta // 120), "units"))
        gs.pack(side="right", fill="y")
        gc.pack(side="left", fill="both", expand=True)

        # ── Country Identity ───────────────────────────────────
        s1 = ttk.LabelFrame(gi, text="Country Identity", padding=(10, 6))
        s1.pack(fill="x", padx=10, pady=(10, 4))
        s1.columnconfigure(1, weight=1)
        s1.columnconfigure(3, weight=1)

        ttk.Label(s1, text="Name:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s1, textvariable=self._gen_name).grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s1, text="Adjective:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s1, textvariable=self._gen_adj).grid(row=0, column=3, sticky="ew", pady=4)

        ttk.Label(s1, text="Tier:", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Combobox(s1, textvariable=self._gen_tier, state="readonly",
                     values=["city_state", "principality", "grand_principality",
                             "kingdom", "empire", "hegemony"]).grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s1, text="Type:", anchor="w").grid(row=1, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Combobox(s1, textvariable=self._gen_type, state="readonly",
                     values=["recognized", "unrecognized", "colonial", "decentralized"]).grid(row=1, column=3, sticky="ew", pady=4)

        ttk.Label(s1, text="Capital State:", anchor="w").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s1, textvariable=self._gen_capital).grid(row=2, column=1, columnspan=3, sticky="ew", pady=4)

        color_row = ttk.Frame(s1)
        color_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=4)
        ttk.Label(color_row, text="Color:", anchor="w").pack(side="left", padx=(0, 6))
        self._gen_color_preview = tk.Label(color_row, width=5, bg="#646464", relief="solid", cursor="hand2")
        self._gen_color_preview.pack(side="left", padx=(0, 6))
        self._gen_color_preview.bind("<Button-1>", self._pick_color)
        ttk.Button(color_row, text="Color Picker", command=self._pick_color).pack(side="left")

        # ── Country Dynamic Name ───────────────────────────────
        s1_dyn = ttk.LabelFrame(gi, text="Country Dynamic Name", padding=(10, 6))
        s1_dyn.pack(fill="x", padx=10, pady=4)
        s1_dyn.columnconfigure(1, weight=1)
        s1_dyn.columnconfigure(3, weight=1)

        ttk.Label(s1_dyn, text="Name:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s1_dyn, textvariable=self._gen_dyn_name).grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s1_dyn, text="Adjective:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s1_dyn, textvariable=self._gen_dyn_adj).grid(row=0, column=3, sticky="ew", pady=4)

        # ── Culture & Religion ─────────────────────────────────
        s2 = ttk.LabelFrame(gi, text="Culture & Religion", padding=(10, 6))
        s2.pack(fill="x", padx=10, pady=4)

        cult_frame = ttk.Frame(s2)
        cult_frame.pack(fill="x", pady=3)
        ttk.Label(cult_frame, text="Primary Cultures:", anchor="w", width=16).pack(side="left")

        cult_list_wrap = ttk.Frame(cult_frame)
        cult_list_wrap.pack(side="left")
        self._gen_cultures_lb = tk.Listbox(cult_list_wrap, height=4, width=26, selectmode=tk.SINGLE)
        self._gen_cultures_lb.pack(side="left")
        ttk.Scrollbar(cult_list_wrap, command=self._gen_cultures_lb.yview).pack(side="right", fill="y")

        cult_ctrl = ttk.Frame(cult_frame)
        cult_ctrl.pack(side="left", padx=8)
        all_cultures = self._parse_cultures()
        self._gen_culture_combo = ttk.Combobox(cult_ctrl, values=all_cultures, width=24)
        self._gen_culture_combo.pack(pady=2)
        ttk.Button(cult_ctrl, text="Add", command=self._add_culture).pack(fill="x", pady=1)
        ttk.Button(cult_ctrl, text="Remove", command=self._remove_culture).pack(fill="x", pady=1)

        rel_frame = ttk.Frame(s2)
        rel_frame.pack(fill="x", pady=3)
        ttk.Label(rel_frame, text="State Religion:", anchor="w", width=16).pack(side="left")
        ttk.Combobox(rel_frame, textvariable=self._gen_religion,
                     values=self._parse_religions(), width=28).pack(side="left", padx=5)

        # ── Internal Politics ──────────────────────────────────
        s3 = ttk.LabelFrame(gi, text="Internal Politics", padding=(10, 6))
        s3.pack(fill="x", padx=10, pady=4)
        s3.columnconfigure(1, weight=1)
        s3.columnconfigure(3, weight=1)

        def law_values(group):
            return [""] + self._law_groups.get(group, [])

        politics = [
            ("Government:",      "lawgroup_governance_principles",   self._gen_gov,   0),
            ("Economic System:", "lawgroup_economic_system",          self._gen_econ,  0),
            ("Trade Policy:",    "lawgroup_trade_policy",             self._gen_trade, 1),
            ("Power Structure:", "lawgroup_distribution_of_power",    self._gen_power, 1),
        ]
        for label, group, var, row in politics:
            col = 0 if row == 0 else 2
            if label in ("Trade Policy:", "Power Structure:"):
                col = 2
                actual_row = 1 if label == "Trade Policy:" else 2
                ttk.Label(s3, text=label, anchor="w").grid(row=actual_row, column=2, sticky="w", padx=(20, 6), pady=4)
                ttk.Combobox(s3, textvariable=var, values=law_values(group),
                             state="readonly").grid(row=actual_row, column=3, sticky="ew", pady=4)
            else:
                actual_row = 1 if label == "Government:" else 2
                ttk.Label(s3, text=label, anchor="w").grid(row=actual_row, column=0, sticky="w", padx=(0, 6), pady=4)
                ttk.Combobox(s3, textvariable=var, values=law_values(group),
                             state="readonly").grid(row=actual_row, column=1, sticky="ew", padx=(0, 10), pady=4)


        # ── Ruler Designer ─────────────────────────────────────
        s4 = ttk.LabelFrame(gi, text="Ruler Designer", padding=(10, 6))
        s4.pack(fill="x", padx=10, pady=4)
        s4.columnconfigure(1, weight=1)
        s4.columnconfigure(3, weight=1)

        ttk.Label(s4, text="First Name:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_first).grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s4, text="Last Name:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_last).grid(row=0, column=3, sticky="ew", pady=4)

        ttk.Label(s4, text="Culture:", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        cult_e = ttk.Entry(s4, textvariable=self._gen_ruler_culture)
        cult_e.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=4)
        cult_e.insert(0, "primary_culture")
        ttk.Label(s4, text="Birth Date:", anchor="w").grid(row=1, column=2, sticky="w", padx=(0, 6), pady=4)
        bd_e = ttk.Entry(s4, textvariable=self._gen_ruler_birth)
        bd_e.grid(row=1, column=3, sticky="ew", pady=4)
        bd_e.insert(0, "YYYY.MM.JJ")

        ttk.Label(s4, text="Interest Group:", anchor="w").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_ig).grid(row=2, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s4, text="Ideology:", anchor="w").grid(row=2, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_ideology).grid(row=2, column=3, sticky="ew", pady=4)

        ruler_bot = ttk.Frame(s4)
        ruler_bot.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 2))
        ttk.Checkbutton(ruler_bot, text="Female", variable=self._gen_ruler_female).pack(side="left", padx=(0, 20))
        tk.Button(ruler_bot, text="Créer le Ruler", command=self._create_ruler,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="left")
        ttk.Button(ruler_bot, text="Supprimer sélection",
                   command=self._delete_ruler).pack(side="left", padx=(10, 0))

        # ── Viewer des rulers existants ────────────────────────
        viewer_frame = ttk.Frame(s4)
        viewer_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 2))

        ttk.Label(viewer_frame, text="Rulers existants pour ce pays :",
                  font=("Segoe UI", 8, "bold")).pack(anchor="w")

        tree_wrap = ttk.Frame(viewer_frame)
        tree_wrap.pack(fill="x")

        cols = ("template", "nom")
        self._ruler_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=4)
        self._ruler_tree.heading("template", text="Template")
        self._ruler_tree.heading("nom",      text="Nom complet")
        self._ruler_tree.column("template", width=280)
        self._ruler_tree.column("nom",      width=160)
        ruler_vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self._ruler_tree.yview)
        self._ruler_tree.configure(yscrollcommand=ruler_vsb.set)
        self._ruler_tree.pack(side="left", fill="x", expand=True)
        ruler_vsb.pack(side="right", fill="y")
        self._ruler_tree.bind("<<TreeviewSelect>>", self._on_ruler_select)

        # ── Population Settings ────────────────────────────────
        s5 = ttk.LabelFrame(gi, text="Population Settings", padding=(10, 6))
        s5.pack(fill="x", padx=10, pady=(4, 12))
        s5.columnconfigure(1, weight=1)
        s5.columnconfigure(3, weight=1)

        self._gen_wealth  = tk.StringVar()
        self._gen_literacy = tk.StringVar()

        wealth_opts = ["", "effect_starting_pop_wealth_very_low", "effect_starting_pop_wealth_low",
                       "effect_starting_pop_wealth_medium", "effect_starting_pop_wealth_high",
                       "effect_starting_pop_wealth_very_high"]
        lit_opts = ["", "effect_starting_pop_literacy_very_low", "effect_starting_pop_literacy_low",
                    "effect_starting_pop_literacy_medium", "effect_starting_pop_literacy_high",
                    "effect_starting_pop_literacy_very_high"]

        ttk.Label(s5, text="Starting Wealth:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Combobox(s5, textvariable=self._gen_wealth, values=wealth_opts,
                     state="readonly").grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s5, text="Starting Literacy:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Combobox(s5, textvariable=self._gen_literacy, values=lit_opts,
                     state="readonly").grid(row=0, column=3, sticky="ew", pady=4)

    # ── Actions General ────────────────────────────────────────

    def _pick_color(self, event=None):
        r, g, b = self._gen_color_rgb
        init = f"#{r:02x}{g:02x}{b:02x}"
        result = colorchooser.askcolor(color=init, title="Choisir une couleur")
        if result and result[0]:
            r, g, b = (int(x) for x in result[0])
            self._gen_color_rgb = [r, g, b]
            hex_col = f"#{r:02x}{g:02x}{b:02x}"
            self._gen_color_preview.config(bg=hex_col)

    def _add_culture(self):
        val = self._gen_culture_combo.get().strip()
        if val and val not in self._gen_cultures_lb.get(0, tk.END):
            self._gen_cultures_lb.insert(tk.END, val)

    def _remove_culture(self):
        sel = self._gen_cultures_lb.curselection()
        if sel:
            self._gen_cultures_lb.delete(sel[0])

    def _load_general_data(self):
        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()
        if not mod or not tag:
            return

        # ── Localisation ──
        self._gen_name.set("")
        self._gen_adj.set("")
        self._gen_dyn_name.set("")
        self._gen_dyn_adj.set("")
        self._gen_religion.set("")
        loc_path = os.path.join(mod, "localization", "english", "00_hmm_countries_l_english.yml")
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                loc = f.read()
            m = re.search(rf'^\s*{re.escape(tag)}:0\s+"([^"]*)"', loc, re.MULTILINE)
            if m:
                self._gen_name.set(m.group(1))
            m = re.search(rf'^\s*{re.escape(tag)}_ADJ:0\s+"([^"]*)"', loc, re.MULTILINE)
            if m:
                self._gen_adj.set(m.group(1))
                self._gen_dyn_adj.set(m.group(1))
            m = re.search(rf'^\s*{re.escape(f"dyn_c_{tag}_01")}:0\s+"([^"]*)"', loc, re.MULTILINE)
            if m:
                self._gen_dyn_name.set(m.group(1))

        # ── Country Definition ──
        def_dir = os.path.join(mod, "common", "country_definitions")
        if os.path.exists(def_dir):
            for fname in sorted(os.listdir(def_dir)):
                fpath = os.path.join(def_dir, fname)
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                indices = self._def_block_indices(content, tag)
                if indices:
                    _, _, inner_s, inner_e = indices
                    block = content[inner_s:inner_e]
                    # color = seulement (pas primary_unit_color etc.)
                    cm = re.search(r'(?<![_a-zA-Z])color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)', block)
                    if cm:
                        self._gen_color_rgb = [int(cm.group(i)) for i in range(1, 4)]
                        self._gen_color_preview.config(
                            bg="#{:02x}{:02x}{:02x}".format(*self._gen_color_rgb))
                    for attr, var in [('tier', self._gen_tier), ('country_type', self._gen_type)]:
                        m2 = re.search(rf'{attr}\s*=\s*(\w+)', block)
                        if m2:
                            var.set(m2.group(1))
                    # capital — valeur simple (STATE_xxx)
                    capm = re.search(r'(?<!\w)capital\s*=\s*([\w]+)', block)
                    if capm:
                        self._gen_capital.set(capm.group(1))
                    # religion
                    rm = re.search(r'(?<!\w)religion\s*=\s*(\w+)', block)
                    if rm:
                        self._gen_religion.set(rm.group(1))
                    # cultures
                    cults = re.search(r'cultures\s*=\s*\{([^}]*)\}', block)
                    if cults:
                        self._gen_cultures_lb.delete(0, tk.END)
                        for c in cults.group(1).split():
                            self._gen_cultures_lb.insert(tk.END, c)
                    break

        # ── History file (lois, religion) ──
        hist_dir = os.path.join(mod, "common", "history", "countries")
        if os.path.exists(hist_dir):
            for fname in os.listdir(hist_dir):
                if fname.upper().startswith(tag):
                    with open(os.path.join(hist_dir, fname), "r", encoding="utf-8") as f:
                        content = f.read()
                    laws = re.findall(r'activate_law\s*=\s*law_type:(\w+)', content)
                    pol_map = {
                        "lawgroup_governance_principles": self._gen_gov,
                        "lawgroup_economic_system":       self._gen_econ,
                        "lawgroup_trade_policy":          self._gen_trade,
                        "lawgroup_distribution_of_power": self._gen_power,
                    }
                    for law in laws:
                        for group, var in pol_map.items():
                            if law in self._law_groups.get(group, []):
                                var.set(law)
                    break

        self._refresh_ruler_viewer()
        self._gen_status.config(text=f"Chargé : {tag}", foreground="#6af")

    def _save_general_data(self):
        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()
        if not mod or not tag:
            messagebox.showerror("Erreur", "Aucun pays sélectionné")
            return

        # ── Localisation ──
        loc_dir = os.path.join(mod, "localization", "english")
        loc_path = os.path.join(loc_dir, "00_hmm_countries_l_english.yml")
        os.makedirs(loc_dir, exist_ok=True)

        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                loc = f.read()
        else:
            loc = "l_english:\n\n"

        def _escape_loc_value(value):
            return value.replace("\\", "\\\\").replace('"', '\\"')

        def _upsert_loc_entry(text, key, value, prefix=""):
            if not value:
                return text
            value = _escape_loc_value(value)
            pattern = rf'^(\s*{re.escape(key)}:0\s+")[^"]*(".*)$'
            if re.search(pattern, text, re.MULTILINE):
                return re.sub(pattern, lambda m: f'{m.group(1)}{value}{m.group(2)}', text, flags=re.MULTILINE)
            if text and not text.endswith("\n"):
                text += "\n"
            return text + f'{prefix}{key}:0 "{value}"\n'

        name = self._gen_name.get().strip()
        adj = self._gen_adj.get().strip()
        dyn_name = self._gen_dyn_name.get().strip()
        dyn_adj = self._gen_dyn_adj.get().strip()
        dyn_key = f"dyn_c_{tag}_01"

        loc = _upsert_loc_entry(loc, tag, name)
        loc = _upsert_loc_entry(loc, dyn_key, dyn_name, prefix="\t")

        adj_value = adj if adj else dyn_adj
        loc = _upsert_loc_entry(loc, f"{tag}_ADJ", adj_value)

        with open(loc_path, "w", encoding="utf-8-sig") as f:
            f.write(loc)

        # ── Country Definition ──
        def_dir = os.path.join(mod, "common", "country_definitions")
        if os.path.exists(def_dir):
            for fname in sorted(os.listdir(def_dir)):
                fpath = os.path.join(def_dir, fname)
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                indices = self._def_block_indices(content, tag)
                if not indices:
                    continue
                _, _, inner_s, inner_e = indices
                block = content[inner_s:inner_e]

                # color (pas primary_unit_color etc.)
                r, g, b = self._gen_color_rgb
                block = re.sub(
                    r'(?<![_a-zA-Z])(color\s*=\s*\{)[^}]*(\})',
                    rf'\g<1> {r} {g} {b} \2', block, count=1)

                # tier, country_type — uniquement dans ce bloc
                block = re.sub(r'(tier\s*=\s*)\w+',
                                rf'\g<1>{self._gen_tier.get()}', block, count=1)
                block = re.sub(r'(country_type\s*=\s*)\w+',
                                rf'\g<1>{self._gen_type.get()}', block, count=1)

                # capital
                capital = self._gen_capital.get().strip()
                if capital:
                    if re.search(r'(?<!\w)capital\s*=\s*\w+', block):
                        block = re.sub(r'((?<!\w)capital\s*=\s*)\w+',
                                       rf'\g<1>{capital}', block, count=1)
                    else:
                        block = block.rstrip() + f'\n    capital = {capital}\n'

                # religion
                religion = self._gen_religion.get().strip()
                if religion:
                    if re.search(r'(?<!\w)religion\s*=\s*\w+', block):
                        block = re.sub(r'((?<!\w)religion\s*=\s*)\w+',
                                       rf'\g<1>{religion}', block, count=1)
                    else:
                        block = block.rstrip() + f'\n    religion = {religion}\n'

                # cultures
                cults = list(self._gen_cultures_lb.get(0, tk.END))
                if cults:
                    if re.search(r'cultures\s*=\s*\{[^}]*\}', block):
                        block = re.sub(r'(cultures\s*=\s*\{)[^}]*(\})',
                                       rf'\g<1> {" ".join(cults)} \2', block, count=1)
                    else:
                        block = block.rstrip() + f'\n    cultures = {{ {" ".join(cults)} }}\n'

                content = content[:inner_s] + block + content[inner_e:]
                with open(fpath, "w", encoding="utf-8-sig") as f:
                    f.write(content)
                break

        # ── History file (lois politiques) ──
        hist_dir = os.path.join(mod, "common", "history", "countries")
        if os.path.exists(hist_dir):
            for fname in os.listdir(hist_dir):
                if fname.upper().startswith(tag):
                    fpath = os.path.join(hist_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    pol_vars = [self._gen_gov, self._gen_econ, self._gen_trade, self._gen_power]
                    pol_groups = [
                        "lawgroup_governance_principles", "lawgroup_economic_system",
                        "lawgroup_trade_policy", "lawgroup_distribution_of_power"
                    ]
                    for group, var in zip(pol_groups, pol_vars):
                        new_law = var.get().strip()
                        if not new_law:
                            continue
                        old_laws = self._law_groups.get(group, [])
                        for old in old_laws:
                            content = re.sub(rf'\s*activate_law\s*=\s*law_type:{old}\b', '', content)
                        content = re.sub(
                            rf'(c:{tag}\s*\??=\s*{{)',
                            rf'\1\n\t\tactivate_law = law_type:{new_law}',
                            content, count=1)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                    break

        self._gen_status.config(text="Sauvegardé !", foreground="#6f6")
        messagebox.showinfo("OK", f"{tag} sauvegardé !")

    def _refresh_ruler_viewer(self):
        if not hasattr(self, '_ruler_tree'):
            return
        self._ruler_tree.delete(*self._ruler_tree.get_children())

        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()
        if not mod or not tag:
            return

        # Lire z_00_hmm_cha.txt pour trouver les templates du tag
        hist_path = os.path.join(mod, "common", "history", "characters", "z_00_hmm_cha.txt")
        templates_for_tag = []
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                content = f.read()
            indices = self._def_block_indices(content, f"c:{tag} ?")
            if not indices:
                # Essayer sans le ?
                indices = self._def_block_indices(content, f"c:{tag}")
            if indices:
                _, _, inner_s, inner_e = indices
                block = content[inner_s:inner_e]
                for m in re.finditer(r'template\s*=\s*(\w+)', block):
                    templates_for_tag.append(m.group(1))

        if not templates_for_tag:
            return

        # Lire la localisation pour résoudre les noms
        loc_path = os.path.join(mod, "localization", "english",
                                "00_hmm_character_template_l_english.yml")
        loc = {}
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    m = re.match(r'\s*(\w+):\s*"([^"]*)"', line)
                    if m:
                        loc[m.group(1)] = m.group(2)

        # Lire les templates pour extraire first_name / last_name
        tpl_path = os.path.join(mod, "common", "character_templates",
                                "00_hmm_character_templates.txt")
        tpl_data = {}
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl_content = f.read()
            for tpl_key in templates_for_tag:
                idx = self._def_block_indices(tpl_content, tpl_key)
                if idx:
                    _, _, ts, te = idx
                    b = tpl_content[ts:te]
                    fm = re.search(r'first_name\s*=\s*(\w+)', b)
                    lm = re.search(r'last_name\s*=\s*(\w+)', b)
                    fn = loc.get(fm.group(1), fm.group(1)) if fm else ""
                    ln = loc.get(lm.group(1), lm.group(1)) if lm else ""
                    tpl_data[tpl_key] = f"{fn} {ln}".strip()

        for tpl_key in templates_for_tag:
            nom = tpl_data.get(tpl_key, "")
            self._ruler_tree.insert("", tk.END, values=(tpl_key, nom))

    def _on_ruler_select(self, *_):
        sel = self._ruler_tree.selection()
        if not sel:
            return
        tpl_key, _ = self._ruler_tree.item(sel[0], "values")
        # Pré-remplir les champs depuis la template
        mod = self.config.mod_path
        if not mod:
            return
        tpl_path = os.path.join(mod, "common", "character_templates",
                                "00_hmm_character_templates.txt")
        if not os.path.exists(tpl_path):
            return
        with open(tpl_path, "r", encoding="utf-8") as f:
            tpl_content = f.read()
        idx = self._def_block_indices(tpl_content, tpl_key)
        if not idx:
            return
        _, _, ts, te = idx
        b = tpl_content[ts:te]
        for pat, var in [
            (r'first_name\s*=\s*(\w+)',      self._gen_ruler_first),
            (r'last_name\s*=\s*(\w+)',       self._gen_ruler_last),
            (r'culture\s*=\s*(\w+)',         self._gen_ruler_culture),
            (r'birth_date\s*=\s*([\d.]+)',   self._gen_ruler_birth),
            (r'interest_group\s*=\s*(\w+)',  self._gen_ruler_ig),
            (r'ideology\s*=\s*(\w+)',        self._gen_ruler_ideology),
        ]:
            m = re.search(pat, b)
            if m:
                var.set(m.group(1))
        fm = re.search(r'female\s*=\s*(\w+)', b)
        if fm:
            self._gen_ruler_female.set(fm.group(1) == "yes")

    def _delete_ruler(self):
        sel = self._ruler_tree.selection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne un ruler dans la liste")
            return
        tpl_key, nom = self._ruler_tree.item(sel[0], "values")
        if not messagebox.askyesno("Confirmer", f"Supprimer le ruler '{nom}' ({tpl_key}) ?"):
            return

        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()

        # Supprimer du fichier template
        tpl_path = os.path.join(mod, "common", "character_templates",
                                "00_hmm_character_templates.txt")
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                content = f.read()
            idx = self._def_block_indices(content, tpl_key)
            if idx:
                ts, te, _, _ = idx
                content = content[:ts].rstrip() + "\n" + content[te:].lstrip("\n")
                with open(tpl_path, "w", encoding="utf-8") as f:
                    f.write(content)

        # Supprimer du fichier history
        hist_path = os.path.join(mod, "common", "history", "characters", "z_00_hmm_cha.txt")
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(
                rf'\tc:{tag}\s*\?=\s*\{{[^}}]*template\s*=\s*{re.escape(tpl_key)}[^}}]*\}}[^}}]*\}}',
                '', content, flags=re.DOTALL)
            with open(hist_path, "w", encoding="utf-8") as f:
                f.write(content)

        self._refresh_ruler_viewer()

    def _create_ruler(self):
        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()
        if not mod or not tag:
            messagebox.showerror("Erreur", "Aucun pays sélectionné")
            return

        first = self._gen_ruler_first.get().strip()
        last  = self._gen_ruler_last.get().strip()
        if not first:
            messagebox.showerror("Erreur", "First Name est obligatoire")
            return

        # Clé template : TAG_prenom_character_template
        first_key = first.lower().replace(" ", "_")
        last_key  = last.lower().replace(" ", "_") if last else ""
        tpl_key   = f"{tag.lower()}_{first_key}_character_template"

        culture = self._gen_ruler_culture.get().strip() or "primary_culture"
        if culture == "primary_culture" or culture == "YYYY.MM.JJ":
            culture = "primary_culture"

        birth = self._gen_ruler_birth.get().strip()
        if birth == "YYYY.MM.JJ" or not birth:
            birth = ""

        female  = "yes" if self._gen_ruler_female.get() else "no"
        ig      = self._gen_ruler_ig.get().strip() or "ig_landowners"
        ideology = self._gen_ruler_ideology.get().strip() or "ideology_royalist"

        # ── 1. Template ───────────────────────────────────────
        tpl_dir  = os.path.join(mod, "common", "character_templates")
        os.makedirs(tpl_dir, exist_ok=True)
        tpl_path = os.path.join(tpl_dir, "00_hmm_character_templates.txt")

        birth_line = f"\n    birth_date = {birth}" if birth else ""
        tpl_block = (
            f"\n{tpl_key} = {{\n"
            f"    first_name = {first_key}\n"
            f"    last_name = {last_key if last_key else first_key}\n"
            f"    historical = yes\n"
            f"    culture = {culture}\n"
            f"    female = {female}"
            f"{birth_line}\n"
            f"    ideology = {ideology}\n"
            f"    interest_group = {ig}\n"
            f"}}\n"
        )

        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl_content = f.read()
            if tpl_key in tpl_content:
                messagebox.showwarning("Attention", f"La template '{tpl_key}' existe déjà.")
            else:
                tpl_content = tpl_content.rstrip() + "\n" + tpl_block
                with open(tpl_path, "w", encoding="utf-8") as f:
                    f.write(tpl_content)
        else:
            with open(tpl_path, "w", encoding="utf-8") as f:
                f.write(tpl_block)

        # ── 2. History characters ─────────────────────────────
        hist_dir  = os.path.join(mod, "common", "history", "characters")
        os.makedirs(hist_dir, exist_ok=True)
        hist_path = os.path.join(hist_dir, "z_00_hmm_cha.txt")

        char_entry = (
            f"\tc:{tag} ?= {{\n"
            f"\t\tcreate_character = {{\n"
            f"\t\t\ttemplate = {tpl_key}\n"
            f"\t\t\truler = yes\n"
            f"\t\t}}\n"
            f"\t}}\n"
        )

        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                hist_content = f.read()
            # Insérer avant la dernière accolade fermante
            last_brace = hist_content.rfind("}")
            if last_brace != -1:
                hist_content = hist_content[:last_brace] + char_entry + hist_content[last_brace:]
            else:
                hist_content = hist_content.rstrip() + "\n" + char_entry
        else:
            hist_content = f"CHARACTERS = {{\n{char_entry}}}\n"

        with open(hist_path, "w", encoding="utf-8") as f:
            f.write(hist_content)

        # ── 3. Localisation ────────────────────────────────────
        loc_dir  = os.path.join(mod, "localization", "english")
        os.makedirs(loc_dir, exist_ok=True)
        loc_path = os.path.join(loc_dir, "00_hmm_character_template_l_english.yml")

        def name_to_loc(name):
            return name.lower().replace(" ", "_"), name

        first_loc_key, first_loc_val = name_to_loc(first)
        last_loc_key,  last_loc_val  = name_to_loc(last) if last else (None, None)

        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                loc = f.read()
        else:
            loc = "l_english:\n"

        def append_loc(text, key, val):
            if not key or f" {key}:" in text:
                return text
            if not text.endswith("\n"):
                text += "\n"
            return text + f" {key}: \"{val}\"\n"

        loc = append_loc(loc, first_loc_key, first_loc_val)
        if last_loc_key:
            loc = append_loc(loc, last_loc_key, last_loc_val)

        with open(loc_path, "w", encoding="utf-8-sig") as f:
            f.write(loc)

        self._refresh_ruler_viewer()
        messagebox.showinfo("OK",
            f"Ruler créé !\n\nTemplate : {tpl_key}\nFichier history : z_00_hmm_cha.txt")

    def _tab_lois(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Lois")

        self._law_groups = {}
        self._law_vars = {}
        self._current_law_file = ""

        self._parse_laws()

        # Barre du haut
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 5))

        ttk.Label(top, text="Pays :").pack(side="left")
        self._mod_tag = tk.StringVar()
        ttk.Entry(top, textvariable=self._mod_tag, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 8))
        ttk.Button(top, text="Charger", command=self._load_country_laws).pack(side="left", padx=(0, 8))
        self._mod_status = ttk.Label(top, text="Sélectionne un pays dans la liste", foreground="#888")
        self._mod_status.pack(side="left", padx=4)
        tk.Button(top, text="Sauvegarder", command=self._apply_laws,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="right", padx=5)

        self._mod_tag.trace_add("write", lambda *args: self._load_country_laws())
        self._selected_country_tag = self._selected_country_tag or ""
        if self._selected_country_tag:
            self._mod_tag.set(self._selected_country_tag)

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=(0, 5))

        # Zone scrollable
        wrapper = ttk.Frame(f)
        wrapper.pack(fill="both", expand=True)

        bg = ttk.Style().lookup("TFrame", "background")
        self._law_canvas = tk.Canvas(wrapper, borderwidth=0, highlightthickness=0, bg=bg)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=self._law_canvas.yview)
        self._law_scroll_frame = ttk.Frame(self._law_canvas)

        self._law_scroll_frame.bind(
            "<Configure>",
            lambda e: self._law_canvas.configure(scrollregion=self._law_canvas.bbox("all"))
        )

        self._law_canvas_window = self._law_canvas.create_window((0, 0), window=self._law_scroll_frame, anchor="nw")
        self._law_canvas.configure(yscrollcommand=scrollbar.set)
        self._law_canvas.bind(
            "<Configure>",
            lambda e: self._law_canvas.itemconfig(self._law_canvas_window, width=e.width)
        )
        self._law_canvas.bind_all("<MouseWheel>", lambda e: self._law_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        scrollbar.pack(side="right", fill="y")
        self._law_canvas.pack(side="left", fill="both", expand=True)

        self._build_law_grid()

    def _parse_laws(self):
        laws_dir = os.path.join(DATA_DIR, "laws")
        if not os.path.exists(laws_dir):
            return
        for fname in os.listdir(laws_dir):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(laws_dir, fname), "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            for law, group in re.findall(
                r'(law_\w+)\s*=\s*{[^}]*?group\s*=\s*(lawgroup_\w+)', content, re.DOTALL
            ):
                self._law_groups.setdefault(group, []).append(law)
        for g in self._law_groups:
            self._law_groups[g] = sorted(set(self._law_groups[g]))

    def _build_law_grid(self):
        for widget in self._law_scroll_frame.winfo_children():
            widget.destroy()
        self._law_vars.clear()

        COLS = 3
        groups = sorted(self._law_groups.keys())

        for col in range(COLS):
            self._law_scroll_frame.columnconfigure(col, weight=1, uniform="law_col")

        for i, group in enumerate(groups):
            col = i % COLS
            row_idx = i // COLS

            cell = ttk.Frame(self._law_scroll_frame, padding=(8, 4))
            cell.grid(row=row_idx, column=col, sticky="ew", padx=4, pady=3)

            label_text = group.replace("lawgroup_", "").replace("_", " ").title()
            ttk.Label(cell, text=label_text, font=("Segoe UI", 8, "bold"),
                      foreground="#aaa").pack(anchor="w")

            var = tk.StringVar()
            self._law_vars[group] = var
            values = ["(aucune)"] + self._law_groups[group]
            cb = ttk.Combobox(cell, textvariable=var, values=values,
                              state="readonly", font=("Segoe UI", 9))
            cb.pack(fill="x")
            var.set("(aucune)")

    def _load_country_laws(self):
        mod = self.config.mod_path
        if not mod:
            return
        tag = self._mod_tag.get().strip().upper()
        if not tag:
            return

        path = os.path.join(mod, "common", "history", "countries")
        file_path = None
        if os.path.exists(path):
            for fname in os.listdir(path):
                if fname.lower().startswith(tag.lower()):
                    file_path = os.path.join(path, fname)
                    break

        if not file_path:
            messagebox.showerror("Erreur", f"Fichier pays introuvable pour {tag}")
            return

        self._current_law_file = file_path
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        laws_found = re.findall(r'activate_law\s*=\s*law_type:(\w+)', content)
        for g in self._law_vars:
            self._law_vars[g].set("(aucune)")
        for law in laws_found:
            for group, values in self._law_groups.items():
                if law in values:
                    self._law_vars[group].set(law)

        self._mod_status.config(text=f"Chargé: {os.path.basename(file_path)}")

    def _apply_laws(self):
        if not self._current_law_file:
            messagebox.showerror("Erreur", "Charge d'abord un pays")
            return
        new_laws = [v.get() for v in self._law_vars.values() if v.get() and v.get() != "(aucune)"]
        if not new_laws:
            messagebox.showerror("Erreur", "Aucune loi sélectionnée")
            return

        tag = self._mod_tag.get().strip().upper()
        with open(self._current_law_file, "r", encoding="utf-8") as fh:
            content = fh.read()

        content = self._replace_laws(content, new_laws, tag)
        with open(self._current_law_file, "w", encoding="utf-8") as fh:
            fh.write(content)
        messagebox.showinfo("OK", "Lois mises à jour !")

    def _replace_laws(self, content, new_laws, tag):
        match = re.search(rf'c:{tag}\s*\??=\s*{{', content, re.IGNORECASE)
        if not match:
            return content
        start = match.end()
        brace = 1
        i = start
        end = start
        while i < len(content):
            if content[i] == "{":
                brace += 1
            elif content[i] == "}":
                brace -= 1
            if brace == 0:
                end = i
                break
            i += 1

        block = content[start:end]
        block = re.sub(r'\n\s*effect_starting_politics_\w+\s*=\s*yes', '', block)
        old_laws = re.findall(r'activate_law\s*=\s*law_type:(\w+)', block)
        final = old_laws.copy()
        for new in new_laws:
            for group, laws in self._law_groups.items():
                if new in laws:
                    final = [l for l in final if l not in laws]
                    final.append(new)
        block = re.sub(r'\s*activate_law\s*=\s*law_type:\w+', '', block)
        law_block = ""
        for law in sorted(set(final)):
            law_block += f"\n\t\tactivate_law = law_type:{law}"
        new_block = law_block + "\n" + block
        return content[:start] + new_block + content[end:]

    def _tab_diplomacy(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Diplomacy")

        self._dipl_tag_var = tk.StringVar()

        # ── Barre du haut ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 6))

        ttk.Label(top, text="Pays :").pack(side="left")
        ttk.Entry(top, textvariable=self._dipl_tag_var, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 8))
        ttk.Button(top, text="Charger", command=self._load_diplomacy_data).pack(side="left", padx=(0, 8))
        self._dipl_status = ttk.Label(top, text="Sélectionne un pays dans la liste", foreground="#888")
        self._dipl_status.pack(side="left", padx=4)
        tk.Button(top, text="Sauvegarder", command=self._dipl_save_all,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="right", padx=5)

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=(0, 8))

        # ── Deux listes côte à côte ────────────────────────────
        lists_frame = ttk.Frame(f)
        lists_frame.pack(fill="x", padx=10)
        lists_frame.columnconfigure(0, weight=1)
        lists_frame.columnconfigure(1, weight=1)

        # Subject Relationships
        subj_lf = ttk.LabelFrame(lists_frame, text="Subject Relationships", padding=(6, 4))
        subj_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._dipl_subj_lb = tk.Listbox(subj_lf, selectmode=tk.SINGLE, activestyle="none",
                                         font=("Segoe UI", 9), height=8)
        subj_sb = ttk.Scrollbar(subj_lf, command=self._dipl_subj_lb.yview)
        self._dipl_subj_lb.config(yscrollcommand=subj_sb.set)
        self._dipl_subj_lb.pack(side="left", fill="both", expand=True)
        subj_sb.pack(side="right", fill="y")
        ttk.Button(subj_lf, text="Remove Selected",
                   command=lambda: self._dipl_remove(self._dipl_subj_lb)).pack(fill="x", pady=(4, 0))

        # Add Subject Relationship (inside Subject panel)
        self._dipl_subj_target_var = tk.StringVar()
        self._dipl_subj_type_var   = tk.StringVar(value="colony")
        _subj_types = ["colony", "puppet", "dominion", "protectorate",
                       "personal_union", "tributary", "vassal"]
        add_subj_inner = ttk.Frame(subj_lf)
        add_subj_inner.pack(fill="x", pady=(6, 0))
        ttk.Label(add_subj_inner, text="Target:").pack(side="left")
        ttk.Entry(add_subj_inner, textvariable=self._dipl_subj_target_var, width=6).pack(side="left", padx=2)
        ttk.Combobox(add_subj_inner, textvariable=self._dipl_subj_type_var,
                     values=_subj_types, width=12, state="readonly").pack(side="left", padx=2)
        ttk.Button(add_subj_inner, text="Add", command=self._dipl_add_subject).pack(side="left", padx=2)

        # Hostile / Truces / Embargo
        host_lf = ttk.LabelFrame(lists_frame, text="Hostile / Truces / Embargo", padding=(6, 4))
        host_lf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._dipl_host_lb = tk.Listbox(host_lf, selectmode=tk.SINGLE, activestyle="none",
                                         font=("Segoe UI", 9), height=8)
        host_sb = ttk.Scrollbar(host_lf, command=self._dipl_host_lb.yview)
        self._dipl_host_lb.config(yscrollcommand=host_sb.set)
        self._dipl_host_lb.pack(side="left", fill="both", expand=True)
        host_sb.pack(side="right", fill="y")
        ttk.Button(host_lf, text="Remove Selected",
                   command=lambda: self._dipl_remove(self._dipl_host_lb)).pack(fill="x", pady=(4, 0))

        # Add Hostile / Truce / Embargo (inside Hostile panel)
        self._dipl_host_target_var = tk.StringVar()
        self._dipl_host_type_var   = tk.StringVar(value="rivalry")
        _hostile_types = ["rivalry", "embargo", "truce"]
        add_host_inner = ttk.Frame(host_lf)
        add_host_inner.pack(fill="x", pady=(6, 0))
        ttk.Label(add_host_inner, text="Target:").pack(side="left")
        ttk.Entry(add_host_inner, textvariable=self._dipl_host_target_var, width=6).pack(side="left", padx=2)
        ttk.Combobox(add_host_inner, textvariable=self._dipl_host_type_var,
                     values=_hostile_types, width=10, state="readonly").pack(side="left", padx=2)
        ttk.Button(add_host_inner, text="Add", command=self._dipl_add_hostile).pack(side="left", padx=2)

        # ── Rivalités + Set Relations côte à côte ──────────────
        riv_rel_frame = ttk.Frame(f)
        riv_rel_frame.pack(fill="x", padx=10, pady=(4, 10))
        riv_rel_frame.columnconfigure(0, weight=1)
        riv_rel_frame.columnconfigure(1, weight=1)

        # Rivalités (gauche)
        riv_lf = ttk.LabelFrame(riv_rel_frame, text="Rivalités", padding=(10, 6))
        riv_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        riv_lf.columnconfigure(0, weight=1)

        riv_tv_frame = ttk.Frame(riv_lf)
        riv_tv_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._dipl_riv_tv = ttk.Treeview(riv_tv_frame, columns=("tag",),
                                          show="headings", height=5, selectmode="browse")
        self._dipl_riv_tv.heading("tag", text="Target Tag")
        self._dipl_riv_tv.column("tag", width=160)
        riv_tv_sb = ttk.Scrollbar(riv_tv_frame, command=self._dipl_riv_tv.yview)
        self._dipl_riv_tv.config(yscrollcommand=riv_tv_sb.set)
        self._dipl_riv_tv.pack(side="left", fill="both", expand=True)
        riv_tv_sb.pack(side="right", fill="y")

        riv_form = ttk.Frame(riv_lf)
        riv_form.grid(row=0, column=1, sticky="n")
        self._dipl_riv_target_var = tk.StringVar()
        ttk.Label(riv_form, text="Target :").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(riv_form, textvariable=self._dipl_riv_target_var, width=10).grid(
            row=0, column=1, padx=4, pady=3)
        ttk.Button(riv_form, text="Ajouter",
                   command=self._dipl_riv_add).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 3))
        ttk.Button(riv_form, text="Supprimer",
                   command=self._dipl_riv_delete).grid(
            row=2, column=0, columnspan=2, sticky="ew")

        # Set Relations (droite)
        rel_lf = ttk.LabelFrame(riv_rel_frame, text="Set Relations", padding=(10, 6))
        rel_lf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        rel_lf.columnconfigure(0, weight=1)

        tv_frame = ttk.Frame(rel_lf)
        tv_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._dipl_rel_tv = ttk.Treeview(tv_frame, columns=("tag", "val"),
                                          show="headings", height=5, selectmode="browse")
        self._dipl_rel_tv.heading("tag", text="Target Tag")
        self._dipl_rel_tv.heading("val", text="Valeur")
        self._dipl_rel_tv.column("tag", width=120)
        self._dipl_rel_tv.column("val", width=70, anchor="center")
        rel_tv_sb = ttk.Scrollbar(tv_frame, command=self._dipl_rel_tv.yview)
        self._dipl_rel_tv.config(yscrollcommand=rel_tv_sb.set)
        self._dipl_rel_tv.pack(side="left", fill="both", expand=True)
        rel_tv_sb.pack(side="right", fill="y")
        self._dipl_rel_tv.bind("<<TreeviewSelect>>", self._dipl_rel_on_select)

        form = ttk.Frame(rel_lf)
        form.grid(row=0, column=1, sticky="n")

        self._dipl_rel_target_var = tk.StringVar()
        self._dipl_rel_value_var  = tk.StringVar(value="0")

        ttk.Label(form, text="Target :").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self._dipl_rel_target_var, width=10).grid(
            row=0, column=1, padx=4, pady=3)
        ttk.Label(form, text="Valeur :").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self._dipl_rel_value_var, width=10).grid(
            row=1, column=1, padx=4, pady=3)
        ttk.Label(form, text="(-100 à 100)", font=("Segoe UI", 8)).grid(
            row=2, column=1, sticky="w", padx=4)
        ttk.Button(form, text="Ajouter / Modifier",
                   command=self._dipl_rel_add_or_update).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 3))
        ttk.Button(form, text="Supprimer",
                   command=self._dipl_rel_delete).grid(
            row=4, column=0, columnspan=2, sticky="ew")

        # Auto-load si pays déjà sélectionné
        if self._selected_country_tag:
            self._dipl_tag_var.set(self._selected_country_tag)
            self._load_diplomacy_data()

    # ── Actions Diplomacy ──────────────────────────────────────

    def _load_diplomacy_data(self):
        mod = self.config.mod_path
        tag = self._dipl_tag_var.get().strip().upper()
        if not mod or not tag:
            return

        dipl_dir = os.path.join(mod, "common", "history", "diplomacy")
        self._dipl_subj_lb.delete(0, tk.END)
        self._dipl_host_lb.delete(0, tk.END)
        self._dipl_riv_tv.delete(*self._dipl_riv_tv.get_children())
        self._dipl_rel_tv.delete(*self._dipl_rel_tv.get_children())

        if not os.path.exists(dipl_dir):
            self._dipl_status.config(text="Dossier diplomacy introuvable", foreground="#f66")
            return

        _subject_types = {"colony", "puppet", "dominion", "protectorate",
                          "personal_union", "tributary", "vassal"}
        subj_count = 0
        host_count = 0
        riv_count = 0
        rel_count = 0

        for fname in sorted(os.listdir(dipl_dir)):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(dipl_dir, fname)
            with open(fpath, "r", encoding="utf-8-sig") as fh:
                content = fh.read()

            indices = self._def_block_indices(content, f"c:{tag}")
            if not indices:
                continue
            _, _, inner_start, inner_end = indices
            block = content[inner_start:inner_end]

            # create_diplomatic_pact entries
            for pm in re.finditer(r'create_diplomatic_pact\s*=\s*\{', block):
                depth = 0
                pact_end = pm.start()
                for i in range(pm.start(), len(block)):
                    if block[i] == '{':
                        depth += 1
                    elif block[i] == '}':
                        depth -= 1
                        if depth == 0:
                            pact_end = i + 1
                            break
                pact_text = block[pm.start():pact_end]
                cm = re.search(r'country\s*=\s*c:(\w+)', pact_text)
                tm = re.search(r'type\s*=\s*(\w+)', pact_text)
                if not cm or not tm:
                    continue
                target = cm.group(1)
                pact_type = tm.group(1)
                if pact_type in _subject_types:
                    self._dipl_subj_lb.insert(tk.END, f"{target} ({pact_type})")
                    subj_count += 1
                elif pact_type == "rivalry":
                    self._dipl_riv_tv.insert("", tk.END, values=(target,))
                    riv_count += 1
                else:
                    self._dipl_host_lb.insert(tk.END, f"{target} ({pact_type})")
                    host_count += 1

            # set_relations entries (only from "relation" files)
            if "relation" in fname.lower():
                for rm in re.finditer(
                    r'set_relations\s*=\s*\{\s*country\s*=\s*c:(\w+)\s*value\s*=\s*(-?\d+)',
                    block
                ):
                    self._dipl_rel_tv.insert("", tk.END,
                                              values=(rm.group(1), int(rm.group(2))))
                    rel_count += 1

        self._dipl_status.config(
            text=f"Chargé : {tag}  |  {subj_count} sujets, {riv_count} rivalités, "
                 f"{host_count} hostiles/truces/embargos, {rel_count} relations",
            foreground="#6af")

    def _dipl_remove(self, listbox):
        sel = listbox.curselection()
        if sel:
            listbox.delete(sel[0])

    def _dipl_save_all(self):
        mod = self.config.mod_path
        tag = self._dipl_tag_var.get().strip().upper()
        if not mod or not tag:
            return

        dipl_dir = os.path.join(mod, "common", "history", "diplomacy")
        os.makedirs(dipl_dir, exist_ok=True)

        _type_routing = {
            "rivalry":  ("rival",   "00_hmm_rivalries.txt"),
            "embargo":  ("embargo", "00_hmm_embargos.txt"),
            "truce":    ("truce",   "00_hmm_relations.txt"),
        }
        _subj_routing = ("subject", "00_subject_relationships.txt")

        def _find_file(keyword, default):
            for fn in os.listdir(dipl_dir):
                if fn.endswith(".txt") and keyword in fn.lower():
                    return os.path.join(dipl_dir, fn)
            return os.path.join(dipl_dir, default)

        # Collect create_diplomatic_pact entries grouped by target file
        pacts_by_file = {}
        for entry in self._dipl_subj_lb.get(0, tk.END):
            m = re.match(r'(\w+)\s*\((\w+)\)', entry)
            if m:
                fp = _find_file(*_subj_routing)
                pacts_by_file.setdefault(fp, []).append((m.group(1), m.group(2)))
        for entry in self._dipl_host_lb.get(0, tk.END):
            m = re.match(r'(\w+)\s*\((\w+)\)', entry)
            if m:
                pact_type = m.group(2)
                keyword, default = _type_routing.get(pact_type, ("relation", "00_hmm_relations.txt"))
                fp = _find_file(keyword, default)
                pacts_by_file.setdefault(fp, []).append((m.group(1), pact_type))

        # Collect rivalry entries from treeview → always go to the "rival" file
        riv_fp = _find_file("rival", "00_hmm_rivalries.txt")
        riv_targets = [self._dipl_riv_tv.item(iid, "values")[0]
                       for iid in self._dipl_riv_tv.get_children()]
        for tgt in riv_targets:
            pacts_by_file.setdefault(riv_fp, []).append((tgt, "rivalry"))

        # Collect set_relations from treeview → always go to the "relation" file
        rel_fp = _find_file("relation", "00_hmm_relations.txt")
        rel_rows = [self._dipl_rel_tv.item(iid, "values")
                    for iid in self._dipl_rel_tv.get_children()]

        # Remove this tag's block from ALL diplomacy files first
        for fn in os.listdir(dipl_dir):
            if not fn.endswith(".txt"):
                continue
            fp = os.path.join(dipl_dir, fn)
            with open(fp, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            indices = self._def_block_indices(content, f"c:{tag}")
            if not indices:
                continue
            tag_start, tag_end, _, _ = indices
            content = content[:tag_start].rstrip() + "\n" + content[tag_end:].lstrip()
            content = re.sub(r'DIPLOMACY\s*=\s*\{\s*\}', '', content)
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(content)

        # Determine all files that need writing
        all_files = set(pacts_by_file.keys())
        if rel_rows:
            all_files.add(rel_fp)
        # riv_fp already added via pacts_by_file if riv_targets non-empty

        def _write_tag_block(fp, pacts, set_rels):
            inner_lines = ""
            for target, ptype in pacts:
                inner_lines += (f"\n\t\tcreate_diplomatic_pact = {{"
                                f"\n\t\t\tcountry = c:{target}"
                                f"\n\t\t\ttype = {ptype}"
                                f"\n\t\t}}")
            for tgt, val in set_rels:
                inner_lines += f"\n\t\tset_relations = {{ country = c:{tgt} value = {val} }}"
            if not inner_lines:
                return
            tag_block = f"\n\tc:{tag} ?= {{{inner_lines}\n\t}}"
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8-sig") as fh:
                    content = fh.read()
            else:
                content = "DIPLOMACY = {\n}\n"
            dm = re.search(r'DIPLOMACY\s*=\s*\{', content)
            if dm:
                brace_start = dm.end() - 1
                depth = 0
                for i in range(brace_start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            content = content[:i] + tag_block + "\n" + content[i:]
                            break
            else:
                content = f"DIPLOMACY = {{{tag_block}\n}}\n"
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(content)

        for fp in all_files:
            _write_tag_block(fp,
                             pacts_by_file.get(fp, []),
                             rel_rows if fp == rel_fp else [])

        self._dipl_status.config(text="Sauvegardé !", foreground="#6f6")

    def _dipl_add_subject(self):
        target = self._dipl_subj_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        subj_type = self._dipl_subj_type_var.get()
        self._dipl_subj_lb.insert(tk.END, f"{target} ({subj_type})")
        self._dipl_subj_target_var.set("")
        self._dipl_save_all()

    def _dipl_add_hostile(self):
        target = self._dipl_host_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        host_type = self._dipl_host_type_var.get()
        self._dipl_host_lb.insert(tk.END, f"{target} ({host_type})")
        self._dipl_host_target_var.set("")
        self._dipl_save_all()

    def _dipl_rel_on_select(self, *_):
        sel = self._dipl_rel_tv.selection()
        if not sel:
            return
        tgt, val = self._dipl_rel_tv.item(sel[0], "values")
        self._dipl_rel_target_var.set(tgt)
        self._dipl_rel_value_var.set(val)

    def _dipl_rel_add_or_update(self):
        target = self._dipl_rel_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        try:
            value = int(self._dipl_rel_value_var.get())
            value = max(-100, min(100, value))
        except ValueError:
            messagebox.showerror("Erreur", "Valeur invalide (entier -100 à 100)")
            return
        # Update existing row if target already present
        for iid in self._dipl_rel_tv.get_children():
            if self._dipl_rel_tv.item(iid, "values")[0] == target:
                self._dipl_rel_tv.item(iid, values=(target, value))
                self._dipl_rel_target_var.set("")
                self._dipl_rel_value_var.set("0")
                return
        # New row
        self._dipl_rel_tv.insert("", tk.END, values=(target, value))
        self._dipl_rel_target_var.set("")
        self._dipl_rel_value_var.set("0")

    def _dipl_rel_delete(self):
        sel = self._dipl_rel_tv.selection()
        if sel:
            self._dipl_rel_tv.delete(sel[0])
            self._dipl_rel_target_var.set("")
            self._dipl_rel_value_var.set("0")

    def _dipl_riv_add(self):
        target = self._dipl_riv_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        # Avoid duplicate
        for iid in self._dipl_riv_tv.get_children():
            if self._dipl_riv_tv.item(iid, "values")[0] == target:
                return
        self._dipl_riv_tv.insert("", tk.END, values=(target,))
        self._dipl_riv_target_var.set("")

    def _dipl_riv_delete(self):
        sel = self._dipl_riv_tv.selection()
        if sel:
            self._dipl_riv_tv.delete(sel[0])
            self._dipl_riv_target_var.set("")

    def _tab_power_blocs(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Power blocs")

        self._pb_tag_var    = tk.StringVar()
        self._pb_key_var    = tk.StringVar()
        self._pb_name_var   = tk.StringVar()
        self._pb_adj_var    = tk.StringVar()
        self._pb_identity   = tk.StringVar()
        self._pb_date_var   = tk.StringVar(value="1836.1.1")
        self._pb_leader_var = tk.StringVar()
        self._pb_color_rgb  = [100, 100, 100]
        self._pb_select_var = tk.StringVar()
        self._pb_blocs      = {}   # key → bloc dict

        # ── Barre du haut ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 6))

        ttk.Label(top, text="Pays :").pack(side="left")
        ttk.Entry(top, textvariable=self._pb_tag_var, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 8))
        ttk.Label(top, text="OR Select Bloc:").pack(side="left")
        self._pb_select_cb = ttk.Combobox(top, textvariable=self._pb_select_var,
                                           state="readonly", width=24)
        self._pb_select_cb.pack(side="left", padx=(4, 4))
        self._pb_select_cb.bind("<<ComboboxSelected>>", self._pb_on_select)
        ttk.Button(top, text="Charger", command=self._pb_refresh_list).pack(side="left", padx=4)
        tk.Button(top, text="Sauvegarder", command=self._pb_save,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="right", padx=5)

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=(4, 0))

        # ── Bloc Details ───────────────────────────────────────
        det = ttk.LabelFrame(f, text="Bloc Details", padding=(10, 6))
        det.pack(fill="x", padx=10, pady=(8, 4))
        det.columnconfigure(1, weight=1)
        det.columnconfigure(3, weight=1)

        identities = [
            "power_bloc_identity_hegemony",
            "power_bloc_identity_trade_league",
            "power_bloc_identity_defensive_pact",
            "power_bloc_identity_customs_union",
            "power_bloc_identity_sphere_of_influence",
            "power_bloc_identity_ideological_union",
        ]

        ttk.Label(det, text="Key:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_key_var).grid(row=0, column=1, sticky="ew", padx=(0,20), pady=3)
        ttk.Label(det, text="Identity:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0,6), pady=3)
        ttk.Combobox(det, textvariable=self._pb_identity, values=identities,
                     width=30).grid(row=0, column=3, sticky="ew", pady=3)

        ttk.Label(det, text="Name:", anchor="w").grid(row=1, column=0, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_name_var).grid(row=1, column=1, sticky="ew", padx=(0,20), pady=3)
        ttk.Label(det, text="Adjective:", anchor="w").grid(row=1, column=2, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_adj_var).grid(row=1, column=3, sticky="ew", pady=3)

        color_row = ttk.Frame(det)
        color_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Label(color_row, text="Color:", anchor="w").pack(side="left", padx=(0,6))
        self._pb_color_preview = tk.Label(color_row, width=5, bg="#646464", relief="solid", cursor="hand2")
        self._pb_color_preview.pack(side="left", padx=(0,6))
        self._pb_color_preview.bind("<Button-1>", self._pb_pick_color)
        ttk.Button(color_row, text="Pick Color", command=self._pb_pick_color).pack(side="left")

        ttk.Label(det, text="Founding Date:", anchor="w").grid(row=3, column=0, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_date_var, width=12).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(det, text="Leader Tag:", anchor="w").grid(row=3, column=2, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_leader_var, width=10).grid(row=3, column=3, sticky="w", pady=3)

        # ── Principles + Members côte à côte ───────────────────
        mid = ttk.Frame(f)
        mid.pack(fill="both", expand=True, padx=10, pady=(6, 4))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        # Principles (gauche)
        prin_lf = ttk.LabelFrame(mid, text="Principles", padding=(6, 4))
        prin_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        cols = ("principle", "level")
        self._pb_tree = ttk.Treeview(prin_lf, columns=cols, show="headings", height=8)
        self._pb_tree.heading("principle", text="Principle Key")
        self._pb_tree.heading("level", text="Level")
        self._pb_tree.column("principle", width=280)
        self._pb_tree.column("level", width=60, anchor="center")
        tree_sb = ttk.Scrollbar(prin_lf, command=self._pb_tree.yview)
        self._pb_tree.configure(yscrollcommand=tree_sb.set)
        self._pb_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")

        add_prin = ttk.Frame(prin_lf)
        add_prin.pack(fill="x", pady=(4, 0))
        ttk.Label(add_prin, text="Add:").pack(side="left")
        principles = [
            "pb_trade_policy_principle", "pb_military_principle",
            "pb_diplomatic_principle", "pb_economic_principle",
            "pb_cultural_principle", "pb_religious_principle",
            "pb_colonial_principle", "pb_industrial_principle",
        ]
        self._pb_prin_key = tk.StringVar()
        self._pb_prin_lvl = tk.StringVar(value="1")
        ttk.Combobox(add_prin, textvariable=self._pb_prin_key, values=principles,
                     width=26).pack(side="left", padx=3)
        ttk.Combobox(add_prin, textvariable=self._pb_prin_lvl, values=["1","2","3","4","5"],
                     width=4, state="readonly").pack(side="left", padx=3)
        ttk.Button(add_prin, text="+", width=3,
                   command=self._pb_add_principle).pack(side="left", padx=2)
        ttk.Button(add_prin, text="Remove", command=self._pb_remove_principle).pack(side="right")

        # Members (droite)
        mem_lf = ttk.LabelFrame(mid, text="Members  (Subjects are automatically made members)",
                                 padding=(6, 4))
        mem_lf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self._pb_members_lb = tk.Listbox(mem_lf, height=8, font=("Segoe UI", 9))
        mem_sb = ttk.Scrollbar(mem_lf, command=self._pb_members_lb.yview)
        self._pb_members_lb.configure(yscrollcommand=mem_sb.set)
        self._pb_members_lb.pack(side="left", fill="both", expand=True)
        mem_sb.pack(side="right", fill="y")

        add_mem = ttk.Frame(mem_lf)
        add_mem.pack(fill="x", pady=(4, 0))
        ttk.Label(add_mem, text="Add Tag:").pack(side="left")
        self._pb_mem_tag = tk.StringVar()
        ttk.Entry(add_mem, textvariable=self._pb_mem_tag, width=8).pack(side="left", padx=3)
        ttk.Button(add_mem, text="+", width=3, command=self._pb_add_member).pack(side="left", padx=2)
        ttk.Button(add_mem, text="Remove",
                   command=self._pb_remove_member).pack(side="right")

        # ── Boutons bas ────────────────────────────────────────
        bot = ttk.Frame(f)
        bot.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bot, text="Remove Power Bloc",
                   command=self._pb_remove_bloc).pack(side="right", padx=(6, 0))
        ttk.Button(bot, text="Create / Modify",
                   command=self._pb_save).pack(side="right")

        self._pb_refresh_list()

    # ── Actions Power Blocs ────────────────────────────────────

    def _pb_get_file(self):
        mod = self.config.mod_path
        if not mod:
            return None
        path = os.path.join(mod, "common", "history", "power_blocs")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "00_hmm_power_blocs.txt")

    def _pb_parse_all(self):
        fpath = self._pb_get_file()
        self._pb_blocs = {}
        if not fpath or not os.path.exists(fpath):
            return
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        for m in re.finditer(r'(\w+)\s*=\s*\{', content):
            key = m.group(1)
            if key == "power_blocs":
                continue
            start = m.end()
            depth = 1
            i = start
            while i < len(content) and depth > 0:
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                i += 1
            block = content[start:i-1]
            def get(pat, txt, default=""):
                r = re.search(pat, txt)
                return r.group(1).strip('"') if r else default
            r, g, b = 100, 100, 100
            cm = re.search(r'color\s*=\s*\{[^\d]*(\d+)[^\d]+(\d+)[^\d]+(\d+)', block)
            if cm:
                r, g, b = int(cm.group(1)), int(cm.group(2)), int(cm.group(3))
            principles = []
            for pm in re.finditer(
                r'set_principle\s*=\s*\{[^}]*principle\s*=\s*(\w+)[^}]*level\s*=\s*(\d+)[^}]*\}',
                block, re.DOTALL
            ):
                principles.append((pm.group(1), pm.group(2)))
            members = re.findall(r'members\s*=\s*\{([^}]*)\}', block)
            member_list = []
            if members:
                member_list = [t.strip().lstrip("c:") for t in members[0].split() if t.strip()]
            self._pb_blocs[key] = {
                "identity":   get(r'identity\s*=\s*(\w+)', block),
                "name":       get(r'name\s*=\s*"([^"]*)"', block),
                "adjective":  get(r'adjective\s*=\s*"([^"]*)"', block),
                "color":      [r, g, b],
                "date":       get(r'founding_date\s*=\s*([\d.]+)', block, "1836.1.1"),
                "leader":     get(r'leader\s*=\s*c:(\w+)', block),
                "principles": principles,
                "members":    member_list,
            }

    def _pb_refresh_list(self):
        self._pb_parse_all()
        keys = list(self._pb_blocs.keys())
        self._pb_select_cb["values"] = keys

    def _pb_on_select(self, event=None):
        key = self._pb_select_var.get()
        if key not in self._pb_blocs:
            return
        b = self._pb_blocs[key]
        self._pb_key_var.set(key)
        self._pb_identity.set(b["identity"])
        self._pb_name_var.set(b["name"])
        self._pb_adj_var.set(b["adjective"])
        self._pb_date_var.set(b["date"])
        self._pb_leader_var.set(b["leader"])
        self._pb_color_rgb = b["color"][:]
        hex_c = "#{:02x}{:02x}{:02x}".format(*self._pb_color_rgb)
        self._pb_color_preview.config(bg=hex_c)
        self._pb_tree.delete(*self._pb_tree.get_children())
        for principle, level in b["principles"]:
            self._pb_tree.insert("", tk.END, values=(principle, level))
        self._pb_members_lb.delete(0, tk.END)
        for tag in b["members"]:
            self._pb_members_lb.insert(tk.END, tag)

    def _pb_pick_color(self, event=None):
        r, g, b = self._pb_color_rgb
        result = colorchooser.askcolor(color=f"#{r:02x}{g:02x}{b:02x}", title="Couleur du bloc")
        if result and result[0]:
            self._pb_color_rgb = [int(x) for x in result[0]]
            self._pb_color_preview.config(bg="#{:02x}{:02x}{:02x}".format(*self._pb_color_rgb))

    def _pb_add_principle(self):
        key = self._pb_prin_key.get().strip()
        lvl = self._pb_prin_lvl.get().strip()
        if key:
            self._pb_tree.insert("", tk.END, values=(key, lvl))

    def _pb_remove_principle(self):
        sel = self._pb_tree.selection()
        if sel:
            self._pb_tree.delete(sel[0])

    def _pb_add_member(self):
        tag = self._pb_mem_tag.get().strip().upper()
        if tag and tag not in self._pb_members_lb.get(0, tk.END):
            self._pb_members_lb.insert(tk.END, tag)
            self._pb_mem_tag.set("")

    def _pb_remove_member(self):
        sel = self._pb_members_lb.curselection()
        if sel:
            self._pb_members_lb.delete(sel[0])

    def _pb_save(self):
        key = self._pb_key_var.get().strip()
        if not key:
            messagebox.showerror("Erreur", "Entre une Key pour le bloc")
            return
        fpath = self._pb_get_file()
        if not fpath:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        r, g, b = self._pb_color_rgb
        principles_str = ""
        for iid in self._pb_tree.get_children():
            p, l = self._pb_tree.item(iid, "values")
            principles_str += f"\n\t\tset_principle = {{ principle = {p} level = {l} }}"

        members = list(self._pb_members_lb.get(0, tk.END))
        members_str = " ".join(f"c:{t}" for t in members)

        leader = self._pb_leader_var.get().strip()
        bloc_block = (
            f'\t{key} = {{\n'
            f'\t\tidentity = {self._pb_identity.get()}\n'
            f'\t\tname = "{self._pb_name_var.get()}"\n'
            f'\t\tadjective = "{self._pb_adj_var.get()}"\n'
            f'\t\tcolor = {{ {r} {g} {b} }}\n'
            f'\t\tfounding_date = {self._pb_date_var.get()}\n'
            f'\t\tleader = c:{leader}\n'
            f'{principles_str}\n'
            f'\t\tmembers = {{ {members_str} }}\n'
            f'\t}}\n'
        )

        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(
                rf'\t{key}\s*=\s*\{{[^}}]*(?:\{{[^}}]*\}}[^}}]*)*\}}',
                bloc_block.rstrip("\n"), content, flags=re.DOTALL)
            if key not in content:
                content = content.rstrip().rstrip("}").rstrip() + f"\n{bloc_block}}}\n"
        else:
            content = f"power_blocs = {{\n{bloc_block}}}\n"

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        self._pb_refresh_list()
        messagebox.showinfo("OK", f"Bloc '{key}' sauvegardé !")

    def _pb_remove_bloc(self):
        key = self._pb_key_var.get().strip()
        if not key:
            return
        fpath = self._pb_get_file()
        if not fpath or not os.path.exists(fpath):
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer le bloc '{key}' ?"):
            return
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            rf'\t{key}\s*=\s*\{{[^}}]*(?:\{{[^}}]*\}}[^}}]*)*\}}',
            '', content, flags=re.DOTALL)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self._pb_refresh_list()
        messagebox.showinfo("OK", f"Bloc '{key}' supprimé")

    def _tab_military_formation(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Military formation")

        self._mil_tag_var      = tk.StringVar()
        self._mil_name_var     = tk.StringVar(value="First Army")
        self._mil_state_var    = tk.StringVar()
        self._mil_type_var     = tk.StringVar(value="army")
        self._mil_infantry_var = tk.StringVar(value="10")
        self._mil_artillery_var= tk.StringVar(value="0")
        self._mil_cavalry_var  = tk.StringVar(value="0")
        self._mil_formations   = []   # liste de dicts chargés

        # ── Header unifié ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 6))
        ttk.Label(top, text="Pays :").pack(side="left")
        ttk.Entry(top, textvariable=self._mil_tag_var, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 8))
        ttk.Button(top, text="Charger", command=self._mil_load_formations).pack(side="left", padx=(0, 8))
        self._mil_status = ttk.Label(top, text="Sélectionne un pays dans la liste", foreground="#888")
        self._mil_status.pack(side="left", padx=4)
        tk.Button(top, text="Sauvegarder", command=self._mil_create,
                  bg="#1a7a1a", fg="white", activebackground="#2a9e2a", activeforeground="white",
                  relief="flat", padx=10, pady=3).pack(side="right", padx=5)

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=(4, 0))

        # ── Create Military Formation ──────────────────────────
        create_lf = ttk.LabelFrame(f, text="Create Military Formation", padding=(12, 8))
        create_lf.pack(fill="x", padx=10, pady=(10, 4))

        row1 = ttk.Frame(create_lf)
        row1.pack(fill="x", pady=3)
        ttk.Label(row1, text="Formation Name:", anchor="w").pack(side="left")
        ttk.Entry(row1, textvariable=self._mil_name_var, width=22).pack(side="left", padx=(4, 0))

        row2 = ttk.Frame(create_lf)
        row2.pack(fill="x", pady=3)
        ttk.Label(row2, text="Target State:", width=14, anchor="w").pack(side="left")
        ttk.Entry(row2, textvariable=self._mil_state_var, width=18).pack(side="left", padx=(0, 8))
        ttk.Label(row2, text="(Defaults to Capital if empty/invalid)",
                  foreground="#888", font=("Segoe UI", 8)).pack(side="left")

        row3 = ttk.Frame(create_lf)
        row3.pack(fill="x", pady=3)
        ttk.Label(row3, text="Formation Type:", width=14, anchor="w").pack(side="left")
        ttk.Radiobutton(row3, text="Army", variable=self._mil_type_var,
                        value="army").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row3, text="Navy", variable=self._mil_type_var,
                        value="navy").pack(side="left")

        # Composition
        comp_lf = ttk.LabelFrame(create_lf, text="Composition", padding=(8, 4))
        comp_lf.pack(fill="x", pady=(6, 4))

        comp_row = ttk.Frame(comp_lf)
        comp_row.pack(anchor="w")
        ttk.Label(comp_row, text="Infantry:").pack(side="left")
        ttk.Entry(comp_row, textvariable=self._mil_infantry_var, width=6).pack(side="left", padx=(3, 14))
        ttk.Label(comp_row, text="Artillery:").pack(side="left")
        ttk.Entry(comp_row, textvariable=self._mil_artillery_var, width=6).pack(side="left", padx=(3, 14))
        ttk.Label(comp_row, text="Cavalry:").pack(side="left")
        ttk.Entry(comp_row, textvariable=self._mil_cavalry_var, width=6).pack(side="left", padx=(3, 0))

        ttk.Button(create_lf, text="Create New Formation",
                   command=self._mil_create).pack(pady=(8, 2))

        ttk.Separator(f, orient="horizontal").pack(fill="x", padx=10, pady=6)

        # ── Manage Existing Formations ─────────────────────────
        manage_lf = ttk.LabelFrame(f, text="Manage Existing Formations", padding=(10, 6))
        manage_lf.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self._mil_manage_tag = tk.StringVar()

        self._mil_listbox = tk.Listbox(manage_lf, height=6, font=("Segoe UI", 9),
                                        activestyle="none", selectmode=tk.SINGLE)
        mil_sb = ttk.Scrollbar(manage_lf, command=self._mil_listbox.yview)
        self._mil_listbox.configure(yscrollcommand=mil_sb.set)
        self._mil_listbox.pack(side="left", fill="both", expand=True)
        mil_sb.pack(side="right", fill="y")
        self._mil_listbox.bind("<<ListboxSelect>>", self._mil_on_select)

        # ── Edit Selected ──────────────────────────────────────
        edit_lf = ttk.LabelFrame(f, text="Edit Selected", padding=(10, 6))
        edit_lf.pack(fill="x", padx=10, pady=(4, 10))

        edit_row = ttk.Frame(edit_lf)
        edit_row.pack(fill="x", pady=3)
        ttk.Label(edit_row, text="Name:", width=8, anchor="w").pack(side="left")
        self._mil_edit_name = tk.StringVar()
        ttk.Entry(edit_row, textvariable=self._mil_edit_name, width=26).pack(side="left", padx=(4, 0))

        btn_row = ttk.Frame(edit_lf)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="Update Formation",
                   command=self._mil_update).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Delete Formation",
                   command=self._mil_delete).pack(side="left")

        if self._selected_country_tag:
            self._mil_tag_var.set(self._selected_country_tag)
            self._mil_manage_tag.set(self._selected_country_tag)
            self._mil_load_formations()

    # ── Actions Military ───────────────────────────────────────

    def _mil_get_file(self, tag):
        mod = self.config.mod_path
        if not mod or not tag:
            return None
        path = os.path.join(mod, "common", "history", "military_formations")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, f"{tag}_formations.txt")

    def _mil_create(self):
        tag = self._mil_tag_var.get().strip().upper()
        name = self._mil_name_var.get().strip()
        if not tag or not name:
            messagebox.showerror("Erreur", "Country Tag et Formation Name sont obligatoires")
            return

        fpath = self._mil_get_file(tag)
        state = self._mil_state_var.get().strip()
        ftype = self._mil_type_var.get()

        try:
            infantry  = int(self._mil_infantry_var.get() or 0)
            artillery = int(self._mil_artillery_var.get() or 0)
            cavalry   = int(self._mil_cavalry_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Les valeurs de composition doivent être des entiers")
            return

        units_str = ""
        if ftype == "army":
            if infantry:
                units_str += f"\n\t\t\tadd_battalion = {{ type = infantry count = {infantry} }}"
            if artillery:
                units_str += f"\n\t\t\tadd_battalion = {{ type = artillery count = {artillery} }}"
            if cavalry:
                units_str += f"\n\t\t\tadd_battalion = {{ type = cavalry count = {cavalry} }}"
        else:
            if infantry:
                units_str += f"\n\t\t\tadd_ship = {{ type = man_o_war count = {infantry} }}"

        state_line = f"\n\t\tlocation = s:{state}" if state else ""
        block = (
            f"\n\tc:{tag} ?= {{\n"
            f"\t\tcreate_{'army' if ftype == 'army' else 'navy'} = {{"
            f"\n\t\t\tname = \"{name}\""
            f"{state_line}"
            f"{units_str}"
            f"\n\t\t}}\n\t}}\n"
        )

        existing = ""
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                existing = f.read()

        if "MILITARY_FORMATION" not in existing and existing:
            content = existing.rstrip() + block
        elif existing:
            content = existing.rstrip().rstrip("}").rstrip() + block + "}\n"
        else:
            content = f"MILITARY_FORMATION = {{{block}}}\n"

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        messagebox.showinfo("OK", f"Formation '{name}' créée pour {tag}")
        if self._mil_manage_tag.get().strip().upper() == tag:
            self._mil_load_formations()

    def _mil_load_formations(self):
        tag = self._mil_tag_var.get().strip().upper()
        self._mil_manage_tag.set(tag)
        fpath = self._mil_get_file(tag)
        self._mil_listbox.delete(0, tk.END)
        self._mil_formations = []

        if not fpath or not os.path.exists(fpath):
            return

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        for m in re.finditer(
            r'create_(?:army|navy)\s*=\s*\{[^}]*name\s*=\s*"([^"]*)"',
            content, re.DOTALL
        ):
            name = m.group(1)
            self._mil_formations.append({"name": name, "match_start": m.start()})
            self._mil_listbox.insert(tk.END, name)

    def _mil_on_select(self, *_):
        sel = self._mil_listbox.curselection()
        if sel:
            self._mil_edit_name.set(self._mil_formations[sel[0]]["name"])

    def _mil_update(self):
        sel = self._mil_listbox.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une formation")
            return
        tag = self._mil_manage_tag.get().strip().upper()
        fpath = self._mil_get_file(tag)
        old_name = self._mil_formations[sel[0]]["name"]
        new_name = self._mil_edit_name.get().strip()
        if not new_name:
            return
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace(f'name = "{old_name}"', f'name = "{new_name}"', 1)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self._mil_load_formations()

    def _mil_delete(self):
        sel = self._mil_listbox.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une formation")
            return
        name = self._mil_formations[sel[0]]["name"]
        if not messagebox.askyesno("Confirmer", f"Supprimer '{name}' ?"):
            return
        tag = self._mil_manage_tag.get().strip().upper()
        fpath = self._mil_get_file(tag)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(
            rf'create_(?:army|navy)\s*=\s*\{{[^}}]*name\s*=\s*"{re.escape(name)}"[^}}]*\}}',
            '', content, flags=re.DOTALL)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        self._mil_load_formations()


    def _tab_techno_generale(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Technologie générale")

        base_frame = ttk.LabelFrame(f, text="Défaut (BASE:)")
        base_frame.pack(fill="x", padx=10, pady=(5, 10))

        base_content = ttk.Frame(base_frame)
        base_content.pack(fill="x", padx=5, pady=5)

        self._effect_combo_items = [
            "effect_starting_technology_tier_1_tech_hmm",
            "effect_starting_technology_tier_2_tech_hmm",
            "effect_starting_technology_tier_3_tech_hmm",
            "effect_starting_technology_tier_4_tech_hmm",
            "effect_starting_technology_tier_1_tech",
            "effect_starting_technology_tier_2_tech",
            "effect_starting_technology_tier_3_tech",
            "effect_starting_technology_tier_4_tech",
            "effect_starting_technology_tier_5_tech",
            "effect_starting_technology_tier_6_tech",
        ]

        self._effect_combo = ttk.Combobox(base_content, width=50, state="readonly", values=self._effect_combo_items)
        self._effect_combo.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self._effect_combo.current(0)

        self._execute_button = tk.Button(base_content, text="Exécuter", command=self._execute_tech_update,
                                          bg="#1a7a1a", fg="white", activebackground="#2a9e2a",
                                          activeforeground="white", relief="flat", padx=10, pady=4)
        self._execute_button.pack(side="left", padx=5, pady=5)

        outer = ttk.Frame(f)
        outer.pack(fill="both", expand=True, padx=10, pady=5)

        hmm_frame = ttk.LabelFrame(outer, text="Technologie HMM")
        hmm_frame.pack(side="left", fill="both", expand=True, padx=(0, 5), ipadx=0)

        regular_frame = ttk.LabelFrame(outer, text="Technologie Standard")
        regular_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), ipadx=0)

        outer.columnconfigure(0, weight=1, uniform="tech_columns")
        outer.columnconfigure(1, weight=1, uniform="tech_columns")

        self._hmm_sections_frame = ttk.Frame(hmm_frame)
        self._hmm_sections_frame.pack(fill="both", expand=True)
        hmm_frame.pack_propagate(False)

        tiers_hmm = [
            "effect_starting_technology_tier_1_tech_hmm",
            "effect_starting_technology_tier_2_tech_hmm",
            "effect_starting_technology_tier_3_tech_hmm",
            "effect_starting_technology_tier_4_tech_hmm",
        ]

        self._hmm_text_areas = {}
        for tier in tiers_hmm:
            label = ttk.Label(self._hmm_sections_frame, text=f"# {tier}")
            label.pack(anchor="w", padx=5, pady=(5, 0))
            txt = tk.Text(self._hmm_sections_frame, height=4, font=("Consolas", 9), wrap="word")
            txt.pack(fill="x", padx=5, pady=(0, 5))
            self._hmm_text_areas[tier] = txt

        self._regular_sections_frame = ttk.Frame(regular_frame)
        self._regular_sections_frame.pack(fill="both", expand=True)
        regular_frame.pack_propagate(False)

        tiers_std = [
            "effect_starting_technology_tier_1_tech",
            "effect_starting_technology_tier_2_tech",
            "effect_starting_technology_tier_3_tech",
            "effect_starting_technology_tier_4_tech",
            "effect_starting_technology_tier_5_tech",
            "effect_starting_technology_tier_6_tech",
        ]

        self._std_text_areas = {}
        for tier in tiers_std:
            label = ttk.Label(self._regular_sections_frame, text=f"# {tier}")
            label.pack(anchor="w", padx=5, pady=(5, 0))
            txt = tk.Text(self._regular_sections_frame, height=4, font=("Consolas", 9), wrap="word")
            txt.pack(fill="x", padx=5, pady=(0, 5))
            self._std_text_areas[tier] = txt

    def _execute_tech_update(self):
        mod_path = self.config.mod_path
        if not mod_path:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        countries_folder = os.path.join(mod_path, "common", "history", "countries")
        if not os.path.exists(countries_folder):
            messagebox.showerror("Erreur", "Dossier countries introuvable")
            return

        base_effect = self._effect_combo.get().strip()
        if not base_effect:
            messagebox.showerror("Erreur", "Sélectionne un effet de base dans le menu déroulant")
            return

        hmm_tags = {}
        std_tags = {}

        for tier in range(1, 5):
            key = f"effect_starting_technology_tier_{tier}_tech_hmm"
            text_widget = self._hmm_text_areas.get(key)
            if text_widget:
                tags_text = text_widget.get("1.0", "end").strip().upper()
                tags = set(line.strip() for line in tags_text.splitlines() if line.strip())
                hmm_tags[key] = tags

        for tier in range(1, 7):
            key = f"effect_starting_technology_tier_{tier}_tech"
            text_widget = self._std_text_areas.get(key)
            if text_widget:
                tags_text = text_widget.get("1.0", "end").strip().upper()
                tags = set(line.strip() for line in tags_text.splitlines() if line.strip())
                std_tags[key] = tags

        def process_file(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            original = content

            match = re.search(r'c:\s*([A-Z]{3}|Y\d{2})\s*\??\s*=\s*{', content)
            if not match:
                return 0

            tag = match.group(1).upper()

            content = re.sub(r'effect_starting_technology_[^\n]+', '', content)
            content = re.sub(r'\n\s*\n+', '\n', content)

            effect_line = None

            for effect, tags_set in hmm_tags.items():
                if tag in tags_set:
                    effect_line = effect + " = yes"
                    break

            if not effect_line:
                for effect, tags_set in std_tags.items():
                    if tag in tags_set:
                        effect_line = effect + " = yes"
                        break

            if not effect_line:
                effect_line = base_effect + " = yes"

            content = re.sub(
                r'(c:\s*(?:[A-Z]{3}|Y\d{2})\s*\??\s*=\s*{)',
                r'\1\n        ' + effect_line,
                content,
                count=1
            )

            if content != original:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"✔ {tag} → {effect_line}")
                return 1

            return 0

        files = 0
        modified = 0
        for filename in os.listdir(countries_folder):
            if filename.endswith(".txt"):
                files += 1
                modified += process_file(os.path.join(countries_folder, filename))

        messagebox.showinfo("Terminé", f"Fichiers lus : {files}\nModifiés : {modified}")

        print("———————")
        print(f"Fichiers lus : {files}")
        print(f"Modifiés : {modified}")
        print("Script terminé")
