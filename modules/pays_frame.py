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
            self._pb_load_for_country(tag)
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

        # Subject Relationships (gauche)
        subj_lf = ttk.LabelFrame(lists_frame, text="Subject Relationships", padding=(6, 4))
        subj_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._dipl_subj_lb = tk.Listbox(subj_lf, selectmode=tk.SINGLE, activestyle="none",
                                         font=("Segoe UI", 9), height=8)
        subj_sb = ttk.Scrollbar(subj_lf, command=self._dipl_subj_lb.yview)
        self._dipl_subj_lb.config(yscrollcommand=subj_sb.set)
        self._dipl_subj_lb.pack(side="left", fill="both", expand=True)
        subj_sb.pack(side="right", fill="y")

        # Add/Modify/Remove Subject Relationship
        self._dipl_subj_target_var = tk.StringVar()
        self._dipl_subj_type_var   = tk.StringVar(value="colony")
        _subj_types = ["colony", "puppet", "dominion", "protectorate",
                       "personal_union", "tributary", "vassal", "chartered_company"]
        subj_form = ttk.LabelFrame(subj_lf, text="Add Subject Relationship", padding=(4, 4))
        subj_form.pack(fill="x", pady=(6, 0))
        ttk.Label(subj_form, text="Target:").pack(side="left")
        ttk.Entry(subj_form, textvariable=self._dipl_subj_target_var, width=6).pack(side="left", padx=2)
        ttk.Combobox(subj_form, textvariable=self._dipl_subj_type_var,
                     values=_subj_types, width=12, state="readonly").pack(side="left", padx=2)
        ttk.Button(subj_form, text="Add", command=self._dipl_add_subject).pack(side="left", padx=2)
        ttk.Button(subj_form, text="Modify", command=self._dipl_modify_subject).pack(side="left", padx=2)
        ttk.Button(subj_form, text="Remove", command=lambda: self._dipl_remove(self._dipl_subj_lb)).pack(side="left", padx=2)

        # Rivalité / Truce / Embargo (droite) - Fusionné
        host_lf = ttk.LabelFrame(lists_frame, text="Rivalité / Truce / Embargo", padding=(6, 4))
        host_lf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._dipl_host_lb = tk.Listbox(host_lf, selectmode=tk.SINGLE, activestyle="none",
                                         font=("Segoe UI", 9), height=8)
        host_sb = ttk.Scrollbar(host_lf, command=self._dipl_host_lb.yview)
        self._dipl_host_lb.config(yscrollcommand=host_sb.set)
        self._dipl_host_lb.pack(side="left", fill="both", expand=True)
        host_sb.pack(side="right", fill="y")

        # Add/Modify/Remove Hostile/Truce/Embargo
        self._dipl_host_target_var = tk.StringVar()
        self._dipl_host_type_var   = tk.StringVar(value="rivalry")
        _hostile_types = ["rivalry", "embargo", "truce"]
        host_form = ttk.LabelFrame(host_lf, text="Add Hostile/Truce/Embargo", padding=(4, 4))
        host_form.pack(fill="x", pady=(6, 0))
        ttk.Label(host_form, text="Target:").pack(side="left")
        ttk.Entry(host_form, textvariable=self._dipl_host_target_var, width=6).pack(side="left", padx=2)
        ttk.Combobox(host_form, textvariable=self._dipl_host_type_var,
                     values=_hostile_types, width=10, state="readonly").pack(side="left", padx=2)
        ttk.Button(host_form, text="Add", command=self._dipl_add_hostile).pack(side="left", padx=2)
        ttk.Button(host_form, text="Modify", command=self._dipl_modify_hostile).pack(side="left", padx=2)
        ttk.Button(host_form, text="Remove", command=lambda: self._dipl_remove(self._dipl_host_lb)).pack(side="left", padx=2)

        # ── Set Relations (pleine largeur) ─────────────────────
        rel_lf = ttk.LabelFrame(f, text="Set Relations", padding=(10, 6))
        rel_lf.pack(fill="x", padx=10, pady=(4, 10))
        rel_lf.columnconfigure(0, weight=1)

        tv_frame = ttk.Frame(rel_lf)
        tv_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._dipl_rel_tv = ttk.Treeview(tv_frame, columns=("tag", "val"),
                                          show="headings", height=5, selectmode="browse")
        self._dipl_rel_tv.heading("tag", text="Target Tag")
        self._dipl_rel_tv.heading("val", text="Valeur")
        self._dipl_rel_tv.column("tag", width=200)
        self._dipl_rel_tv.column("val", width=80, anchor="center")
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
        self._dipl_rel_tv.delete(*self._dipl_rel_tv.get_children())

        if not os.path.exists(dipl_dir):
            self._dipl_status.config(text="Dossier diplomacy introuvable", foreground="#f66")
            return

        _subject_types = {"colony", "puppet", "dominion", "protectorate",
                          "personal_union", "tributary", "vassal", "chartered_company"}
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
                else:
                    # rivalry, embargo, truce - tous dans le panneau host_lb
                    self._dipl_host_lb.insert(tk.END, f"{target} ({pact_type})")
                    if pact_type == "rivalry":
                        riv_count += 1
                    else:
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

    def _dipl_modify_subject(self):
        sel = self._dipl_subj_lb.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une entrée à modifier")
            return
        target = self._dipl_subj_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        subj_type = self._dipl_subj_type_var.get()
        self._dipl_subj_lb.delete(sel[0])
        self._dipl_subj_lb.insert(sel[0], f"{target} ({subj_type})")
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

    def _dipl_modify_hostile(self):
        sel = self._dipl_host_lb.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une entrée à modifier")
            return
        target = self._dipl_host_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        host_type = self._dipl_host_type_var.get()
        self._dipl_host_lb.delete(sel[0])
        self._dipl_host_lb.insert(sel[0], f"{target} ({host_type})")
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

    # Rivalités maintenant gérées via _dipl_host_lb (type "rivalry")
    # Les méthodes _dipl_riv_add et _dipl_riv_delete ne sont plus utilisées

    def _tab_power_blocs(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Power blocs")

        self._pb_tag_var    = tk.StringVar()
        self._pb_key_var    = tk.StringVar()   # = name = POR_EMP dans le fichier
        self._pb_identity   = tk.StringVar()
        self._pb_date_var   = tk.StringVar(value="1836.1.1")
        self._pb_leader_var = tk.StringVar()   # = outer c:TAG
        self._pb_color_rgb  = [100, 100, 100]
        self._pb_blocs      = {}   # name → bloc dict
        self._pb_bloc_files = {}   # name → filepath

        # ── Barre du haut ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 6))

        ttk.Label(top, text="Pays :").pack(side="left")
        ttk.Entry(top, textvariable=self._pb_tag_var, width=8, state="readonly",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 8))
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
            "identity_trade_league",
            "identity_sovereign_empire",
            "identity_ideological_union",
            "identity_military_treaty_organization",
            "identity_religious",
            "identity_cultural",
        ]

        ttk.Label(det, text="Name (bloc):", anchor="w").grid(row=0, column=0, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_key_var).grid(row=0, column=1, sticky="ew", padx=(0,20), pady=3)
        ttk.Label(det, text="Identity:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0,6), pady=3)
        ttk.Combobox(det, textvariable=self._pb_identity, values=identities,
                     width=34, state="readonly").grid(row=0, column=3, sticky="ew", pady=3)

        color_row = ttk.Frame(det)
        color_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Label(color_row, text="Color:", anchor="w").pack(side="left", padx=(0,6))
        self._pb_color_preview = tk.Label(color_row, width=5, bg="#646464", relief="solid", cursor="hand2")
        self._pb_color_preview.pack(side="left", padx=(0,6))
        self._pb_color_preview.bind("<Button-1>", self._pb_pick_color)
        ttk.Button(color_row, text="Pick Color", command=self._pb_pick_color).pack(side="left")

        ttk.Label(det, text="Founding Date:", anchor="w").grid(row=2, column=0, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_date_var, width=12).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(det, text="Leader Tag:", anchor="w").grid(row=2, column=2, sticky="w", padx=(0,6), pady=3)
        ttk.Entry(det, textvariable=self._pb_tag_var, width=10, state="readonly",
                  font=("Segoe UI", 10, "bold")).grid(row=2, column=3, sticky="w", pady=3)

        # ── Principle (un seul par bloc) ───────────────────────
        prin_lf = ttk.LabelFrame(f, text="Principle", padding=(8, 6))
        prin_lf.pack(fill="x", padx=10, pady=(6, 4))

        _principles = [
            "principle_construction",
            "principle_internal_trade",
            "principle_market_unification",
            "principle_vassalization",
            "principle_advanced_research",
            "principle_defensive_cooperation",
            "principle_aggressive_coordination",
            "principle_external_trade",
            "principle_food_standardization",
            "principle_police_coordination",
            "principle_transport",
            "principle_military_industry",
            "principle_colonial_offices",
            "principle_foreign_investment",
            "principle_creative_legislature",
            "principle_freedom_of_movement",
            "principle_divine_economics",
            "principle_exploit_members",
            "principle_sacred_civics",
            "principle_ideological_truth",
            "principle_companies",
            "principle_shared_canon",
        ]
        self._pb_prin_key = tk.StringVar()
        self._pb_prin_lvl = tk.StringVar(value="1")
        ttk.Label(prin_lf, text="Principle:").pack(side="left", padx=(0, 4))
        ttk.Combobox(prin_lf, textvariable=self._pb_prin_key, values=_principles,
                     width=34, state="readonly").pack(side="left", padx=(0, 12))
        ttk.Label(prin_lf, text="Level:").pack(side="left", padx=(0, 4))
        ttk.Combobox(prin_lf, textvariable=self._pb_prin_lvl, values=["1", "2", "3"],
                     width=4, state="readonly").pack(side="left")

        # ── Members ────────────────────────────────────────────
        mem_lf = ttk.LabelFrame(f, text="Members",
                                 padding=(6, 4))
        mem_lf.pack(fill="x", padx=10, pady=(4, 4))

        self._pb_members_lb = tk.Listbox(mem_lf, height=5, font=("Segoe UI", 9))
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

        # ── Power Blocs Existants ──────────────────────────────
        blocs_lf = ttk.LabelFrame(f, text="Power Blocs Existants",
                                   padding=(6, 4))
        blocs_lf.pack(fill="x", padx=10, pady=(4, 4))

        self._pb_blocs_lb = tk.Listbox(blocs_lf, height=4, font=("Segoe UI", 9))
        blocs_sb = ttk.Scrollbar(blocs_lf, command=self._pb_blocs_lb.yview)
        self._pb_blocs_lb.configure(yscrollcommand=blocs_sb.set)
        self._pb_blocs_lb.pack(side="left", fill="both", expand=True)
        blocs_sb.pack(side="right", fill="y")
        self._pb_blocs_lb.bind("<<ListboxSelect>>", self._pb_on_bloc_list_select)

        # ── Boutons bas ────────────────────────────────────────
        bot = ttk.Frame(f)
        bot.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(bot, text="Remove Power Bloc",
                   command=self._pb_remove_bloc).pack(side="right", padx=(6, 0))
        ttk.Button(bot, text="Create / Modify",
                   command=self._pb_save).pack(side="right")

        self._pb_refresh_list()

    # ── Actions Power Blocs ────────────────────────────────────

    def _pb_get_dir(self):
        mod = self.config.mod_path
        if not mod:
            return None
        path = os.path.join(mod, "common", "history", "power_blocs")
        os.makedirs(path, exist_ok=True)
        return path

    def _pb_load_localization(self):
        """Load power bloc localization for name resolution"""
        mod = self.config.mod_path
        if not mod:
            return {}
        loc_path = os.path.join(mod, "localization", "english", "00_hmm_power_blocs_l_english.yml")
        loc = {}
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    m = re.match(r'\s*(\w+):\s*"([^"]*)"', line)
                    if m:
                        loc[m.group(1)] = m.group(2)
        return loc

    def _pb_parse_all(self):
        self._pb_blocs = {}
        self._pb_bloc_files = {}
        pb_dir = self._pb_get_dir()
        if not pb_dir or not os.path.exists(pb_dir):
            return

        # Load localization for name resolution
        pb_loc = self._pb_load_localization()

        def _get(pat, txt, default=""):
            r = re.search(pat, txt)
            return r.group(1).strip('"') if r else default

        def _extract_block(content, start):
            depth = 1
            i = start
            while i < len(content) and depth > 0:
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                i += 1
            return content[start:i - 1]

        for fname in os.listdir(pb_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(pb_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except Exception:
                continue

            for m in re.finditer(r'c:(\w+)\s*\?=\s*\{', content):
                leader = m.group(1)
                outer_block = _extract_block(content, m.end())

                cbm = re.search(r'create_power_bloc\s*=\s*\{', outer_block)
                if not cbm:
                    continue
                bloc_content = _extract_block(outer_block, cbm.end())

                r, g, b = 100, 100, 100
                cm = re.search(
                    r'map_color\s*=\s*\{[^\d]*(\d+)[^\d]+(\d+)[^\d]+(\d+)', bloc_content)
                if cm:
                    r, g, b = int(cm.group(1)), int(cm.group(2)), int(cm.group(3))

                principle_full = _get(r'principle\s*=\s*(\w+)', bloc_content)
                prin_base, prin_lvl = principle_full, "1"
                if principle_full:
                    pm = re.match(r'(.+)_(\d+)$', principle_full)
                    if pm:
                        prin_base, prin_lvl = pm.group(1), pm.group(2)

                member_list = re.findall(r'member\s*=\s*c:(\w+)', bloc_content)
                # Get the localization key (e.g., TAG_POWER_BLOCS)
                loc_key = _get(r'name\s*=\s*(\S+)', bloc_content)
                
                # Try to resolve the name from localization
                display_name = pb_loc.get(loc_key, loc_key)
                
                # Use the leader as key if no loc_key found
                key = loc_key if loc_key else leader

                self._pb_blocs[key] = {
                    "leader":    leader,
                    "name":      display_name,  # Use resolved name for display
                    "loc_key":   loc_key,       # Keep the localization key for reference
                    "identity":  _get(r'identity\s*=\s*(\w+)', bloc_content),
                    "color":     [r, g, b],
                    "date":      _get(r'founding_date\s*=\s*([\d.]+)', bloc_content, "1836.1.1"),
                    "prin_base": prin_base,
                    "prin_lvl":  prin_lvl,
                    "members":   member_list,
                }
                self._pb_bloc_files[key] = fpath

    def _pb_refresh_list(self):
        self._pb_parse_all()
        # Update the listbox with existing power blocs
        self._pb_blocs_lb.delete(0, tk.END)
        for key, b in self._pb_blocs.items():
            display_text = f"{b['name']} (Leader: {b['leader']})"
            self._pb_blocs_lb.insert(tk.END, display_text)

    def _pb_on_bloc_list_select(self, event=None):
        selection = self._pb_blocs_lb.curselection()
        if not selection:
            return
        selected_text = self._pb_blocs_lb.get(selection[0])
        # Extract bloc name from "NAME (Leader: TAG)"
        match = re.search(r'^(.+?)\s*\(Leader:\s*(\w+)\)', selected_text)
        if not match:
            return
        bloc_name = match.group(1)
        leader_tag = match.group(2)
        
        # Find the bloc by name
        for key, b in self._pb_blocs.items():
            if b["name"] == bloc_name:
                self._pb_key_var.set(b["name"])
                self._pb_leader_var.set(b["leader"])
                self._pb_tag_var.set(b["leader"])
                self._pb_identity.set(b["identity"])
                self._pb_date_var.set(b["date"])
                self._pb_color_rgb = b["color"][:]
                hex_c = "#{:02x}{:02x}{:02x}".format(*self._pb_color_rgb)
                self._pb_color_preview.config(bg=hex_c)
                self._pb_prin_key.set(b["prin_base"])
                self._pb_prin_lvl.set(b["prin_lvl"])
                self._pb_members_lb.delete(0, tk.END)
                for tag in b["members"]:
                    self._pb_members_lb.insert(tk.END, tag)
                break

    def _pb_load_for_country(self, tag):
        """Load power bloc data for a country if it leads a bloc"""
        self._pb_parse_all()
        for key, b in self._pb_blocs.items():
            if b["leader"].upper() == tag.upper():
                self._pb_key_var.set(b["name"])
                self._pb_leader_var.set(b["leader"])
                self._pb_tag_var.set(b["leader"])
                self._pb_identity.set(b["identity"])
                self._pb_date_var.set(b["date"])
                self._pb_color_rgb = b["color"][:]
                hex_c = "#{:02x}{:02x}{:02x}".format(*self._pb_color_rgb)
                self._pb_color_preview.config(bg=hex_c)
                self._pb_prin_key.set(b["prin_base"])
                self._pb_prin_lvl.set(b["prin_lvl"])
                self._pb_members_lb.delete(0, tk.END)
                for member_tag in b["members"]:
                    self._pb_members_lb.insert(tk.END, member_tag)
                return True
        # No bloc found for this country - clear fields
        self._pb_key_var.set("")
        self._pb_leader_var.set("")
        self._pb_tag_var.set(tag)
        self._pb_identity.set("")
        self._pb_date_var.set("1836.1.1")
        self._pb_color_rgb = [100, 100, 100]
        self._pb_color_preview.config(bg="#646464")
        self._pb_prin_key.set("")
        self._pb_prin_lvl.set("1")
        self._pb_members_lb.delete(0, tk.END)
        return False

    def _pb_pick_color(self, event=None):
        r, g, b = self._pb_color_rgb
        result = colorchooser.askcolor(color=f"#{r:02x}{g:02x}{b:02x}", title="Couleur du bloc")
        if result and result[0]:
            self._pb_color_rgb = [int(x) for x in result[0]]
            self._pb_color_preview.config(bg="#{:02x}{:02x}{:02x}".format(*self._pb_color_rgb))

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
        name = self._pb_key_var.get().strip()    # ex. "Empire Portuguese"
        leader = self._pb_tag_var.get().strip().upper()  # Use selected country tag
        if not name or not leader:
            messagebox.showerror("Erreur", "Sélectionne un pays et entre un nom de bloc")
            return
        pb_dir = self._pb_get_dir()
        if not pb_dir:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        # Generate localization key: TAG_POWER_BLOCS
        bloc_key = f"{leader}_POWER_BLOCS"

        r, g, b = self._pb_color_rgb
        prin_base = self._pb_prin_key.get().strip()
        prin_lvl  = self._pb_prin_lvl.get().strip() or "1"
        principle_str = f"{prin_base}_{prin_lvl}" if prin_base else ""

        members = list(self._pb_members_lb.get(0, tk.END))
        members_lines = "".join(f"\t\t\tmember = c:{t}\n" for t in members)

        # Use localization key for name
        bloc_block = (
            f'\tc:{leader} ?= {{\n'
            f'\t\tcreate_power_bloc = {{\n'
            f'\t\t\tname = {bloc_key}\n'
            f'\t\t\tmap_color = {{ {r} {g} {b} }}\n'
            f'\t\t\tfounding_date = {self._pb_date_var.get()}\n'
            f'\t\t\tidentity = {self._pb_identity.get()}\n'
            f'\t\t\tprinciple = {principle_str}\n'
            f'{members_lines}'
            f'\t\t}}\n'
            f'\t}}\n'
        )

        # Fichier cible : celui qui contenait déjà ce bloc, sinon fichier par défaut
        if bloc_key in self._pb_bloc_files:
            fpath = self._pb_bloc_files[bloc_key]
        else:
            fpath = os.path.join(pb_dir, "00_hmm_power_blocs.txt")

        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
            
            # Check if POWER_BLOCS = { exists
            if "POWER_BLOCS = {" in content:
                # Insert inside POWER_BLOCS block
                match = re.search(r'(POWER_BLOCS\s*=\s*\{)', content)
                if match:
                    insert_pos = match.end()
                    content = content[:insert_pos] + bloc_block + content[insert_pos:]
            else:
                # Replace existing bloc or add new one
                new_content = re.sub(
                    rf'c:{re.escape(leader)}\s*\?=\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}',
                    bloc_block.strip("\n"), content, flags=re.DOTALL)
                if new_content == content:
                    # No existing bloc found - wrap in POWER_BLOCS
                    content = f"POWER_BLOCS = {{\n{bloc_block}}}\n"
                else:
                    content = new_content
        else:
            # Create new file with POWER_BLOCS wrapper
            content = f"POWER_BLOCS = {{\n{bloc_block}}}\n"

        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)

        # Update localization file
        self._pb_update_localization(bloc_key, name)

        self._pb_refresh_list()
        messagebox.showinfo("OK", f"Bloc '{name}' sauvegardé !")

    def _pb_update_localization(self, bloc_key, display_name):
        """Update the localization file with the power bloc name"""
        mod = self.config.mod_path
        if not mod:
            return
        
        loc_dir = os.path.join(mod, "localization", "english")
        loc_path = os.path.join(loc_dir, "00_hmm_power_blocs_l_english.yml")
        os.makedirs(loc_dir, exist_ok=True)
        
        # Read existing content or create new file
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
        else:
            content = "l_english:\n"
        
        # Escape special characters for YAML
        escaped_name = display_name.replace("\\", "\\\\").replace('"', '\\"')
        
        # Check if entry exists and update it, or add new entry
        key_pattern = rf'^\s*{re.escape(bloc_key)}:0\s+".*"$'
        adj_key = f"{bloc_key}_adj"
        adj_pattern = rf'^\s*{re.escape(adj_key)}:0\s+".*"$'
        
        if re.search(key_pattern, content, re.MULTILINE):
            # Update existing entry
            content = re.sub(
                key_pattern,
                f' {bloc_key}:0 "{escaped_name}"',
                content,
                flags=re.MULTILINE
            )
        else:
            # Add new entry
            if not content.endswith("\n"):
                content += "\n"
            content += f" {bloc_key}:0 \"{escaped_name}\"\n"
        
        # Add or update _adj entry (empty by default)
        if not re.search(adj_pattern, content, re.MULTILINE):
            if not content.endswith("\n"):
                content += "\n"
            content += f" {adj_key}:0 \"\"\n"
        
        with open(loc_path, "w", encoding="utf-8-sig") as fh:
            fh.write(content)

    def _pb_remove_bloc(self):
        name = self._pb_key_var.get().strip()
        leader = self._pb_leader_var.get().strip().upper()
        if not name or name not in self._pb_bloc_files:
            return
        fpath = self._pb_bloc_files[name]
        if not os.path.exists(fpath):
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer le bloc '{name}' ?"):
            return
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()
        content = re.sub(
            rf'c:{re.escape(leader)}\s*\?=\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}',
            '', content, flags=re.DOTALL)
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(content)
        self._pb_refresh_list()
        messagebox.showinfo("OK", f"Bloc '{name}' supprimé")

    def _tab_military_formation(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Military formation")

        self._mil_tag_var      = tk.StringVar()
        self._mil_name_var     = tk.StringVar(value="First Army")
        self._mil_sr_var       = tk.StringVar()
        self._mil_state_var    = tk.StringVar()
        self._mil_type_var     = tk.StringVar(value="army")
        # Army composition
        self._mil_infantry_type_var  = tk.StringVar()
        self._mil_infantry_var       = tk.StringVar(value="10")
        self._mil_artillery_type_var = tk.StringVar()
        self._mil_artillery_var      = tk.StringVar(value="0")
        self._mil_cavalry_type_var   = tk.StringVar()
        self._mil_cavalry_var        = tk.StringVar(value="0")
        # Navy composition
        self._mil_light_ship_type_var   = tk.StringVar()
        self._mil_light_ship_var        = tk.StringVar(value="0")
        self._mil_capital_ship_type_var = tk.StringVar()
        self._mil_capital_ship_var      = tk.StringVar(value="0")
        self._mil_support_ship_type_var = tk.StringVar()
        self._mil_support_ship_var      = tk.StringVar(value="0")
        self._mil_formations   = []   # liste de dicts chargés
        self._mil_selected_idx = None  # index de la formation sélectionnée
        # Variables pour Général/Amiral
        self._mil_general_first = tk.StringVar()
        self._mil_general_last = tk.StringVar()
        self._mil_general_historical = tk.BooleanVar(value=True)
        self._mil_general_rank = tk.StringVar(value="5")
        # Variable pour le bouton Building
        self._mil_building_var = tk.BooleanVar(value=False)

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

        # ── Layout en deux colonnes ────────────────────────────
        content = ttk.Frame(f)
        content.pack(fill="both", expand=True, padx=10, pady=(6, 4))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # ── COLONNE GAUCHE : Create Military Formation ─────────
        create_lf = ttk.LabelFrame(content, text="Create / Edit Military Formation", padding=(12, 8))
        create_lf.grid(column=0, row=0, sticky="nsew", padx=(0, 5))

        row1 = ttk.Frame(create_lf)
        row1.pack(fill="x", pady=3)
        ttk.Label(row1, text="Formation Name:", anchor="w").pack(side="left")
        ttk.Entry(row1, textvariable=self._mil_name_var, width=22).pack(side="left", padx=(4, 0))

        row_sr = ttk.Frame(create_lf)
        row_sr.pack(fill="x", pady=3)
        ttk.Label(row_sr, text="HQ Region:", width=14, anchor="w").pack(side="left")
        sr_values = self._mil_load_strategic_regions_list()
        self._mil_sr_combo = ttk.Combobox(row_sr, textvariable=self._mil_sr_var,
                                          values=sr_values, width=30, state="readonly")
        self._mil_sr_combo.pack(side="left", padx=(0, 8))
        self._mil_sr_combo.bind("<<ComboboxSelected>>", self._mil_on_sr_selected)

        row2 = ttk.Frame(create_lf)
        row2.pack(fill="x", pady=3)
        ttk.Label(row2, text="Target State:", width=14, anchor="w").pack(side="left")
        self._mil_state_combo = ttk.Combobox(row2, textvariable=self._mil_state_var,
                                             width=30, state="readonly")
        self._mil_state_combo.pack(side="left", padx=(0, 8))

        row3 = ttk.Frame(create_lf)
        row3.pack(fill="x", pady=3)
        ttk.Label(row3, text="Formation Type:", width=14, anchor="w").pack(side="left")
        ttk.Radiobutton(row3, text="Army", variable=self._mil_type_var,
                        value="army", command=self._mil_on_type_change).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(row3, text="Navy", variable=self._mil_type_var,
                        value="navy", command=self._mil_on_type_change).pack(side="left")

        # Row pour le bouton Building
        row4 = ttk.Frame(create_lf)
        row4.pack(fill="x", pady=3)
        ttk.Label(row4, text="Building:", width=14, anchor="w").pack(side="left")
        ttk.Checkbutton(row4, text="Yes", variable=self._mil_building_var).pack(side="left")

        # Row pour supprimer tous les bâtiments du TAG
        row5 = ttk.Frame(create_lf)
        row5.pack(fill="x", pady=3)
        ttk.Label(row5, text="Remove All:", width=14, anchor="w").pack(side="left")
        ttk.Button(row5, text="Delete All Buildings",
                   command=self._mil_delete_all_buildings_for_tag,
                   width=18).pack(side="left")

        # Composition
        comp_lf = ttk.LabelFrame(create_lf, text="Composition", padding=(8, 4))
        comp_lf.pack(fill="x", pady=(6, 4))

        # Charger les types d'unités depuis les fichiers de données
        land_units = self._mil_load_unit_types_from_file("00_land_combat_unit_types.txt")
        navy_units = self._mil_load_unit_types_from_file("01_navy_combat_unit_types.txt")

        inf_types     = land_units.get("Infantry",     ["combat_unit_type_line_infantry"])
        art_types     = land_units.get("Artillery",    ["combat_unit_type_cannon_artillery"])
        cav_types     = land_units.get("Cavalry",      ["combat_unit_type_hussars"])
        light_types   = navy_units.get("Light Ships",  ["combat_unit_type_frigate"])
        capital_types = navy_units.get("Capital Ships",["combat_unit_type_man_o_war"])
        support_types = navy_units.get("Support Ships",["combat_unit_type_submarine"])

        self._mil_infantry_type_var.set(inf_types[0]     if inf_types     else "")
        self._mil_artillery_type_var.set(art_types[0]    if art_types     else "")
        self._mil_cavalry_type_var.set(cav_types[0]      if cav_types     else "")
        self._mil_light_ship_type_var.set(light_types[0]    if light_types   else "")
        self._mil_capital_ship_type_var.set(capital_types[0] if capital_types else "")
        self._mil_support_ship_type_var.set(support_types[0] if support_types else "")

        _lw, _cw, _ew = 13, 30, 5   # label width, combo width, entry width

        # ── Cadre Army ─────────────────────────────────────────
        self._mil_army_comp_frame = ttk.Frame(comp_lf)
        self._mil_army_comp_frame.pack(fill="x")

        for label, type_var, types_list, count_var in [
            ("Infantry:",  self._mil_infantry_type_var,  inf_types, self._mil_infantry_var),
            ("Artillery:", self._mil_artillery_type_var, art_types, self._mil_artillery_var),
            ("Cavalry:",   self._mil_cavalry_type_var,   cav_types, self._mil_cavalry_var),
        ]:
            r = ttk.Frame(self._mil_army_comp_frame)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text=label, width=_lw, anchor="w").pack(side="left")
            ttk.Combobox(r, textvariable=type_var, values=types_list,
                         width=_cw, state="readonly").pack(side="left", padx=(0, 6))
            ttk.Entry(r, textvariable=count_var, width=_ew).pack(side="left")

        # ── Cadre Navy (caché par défaut) ──────────────────────
        self._mil_navy_comp_frame = ttk.Frame(comp_lf)
        # non pack() → caché tant qu'Army est sélectionné

        for label, type_var, types_list, count_var in [
            ("Light Ships:",   self._mil_light_ship_type_var,   light_types,   self._mil_light_ship_var),
            ("Capital Ships:", self._mil_capital_ship_type_var, capital_types, self._mil_capital_ship_var),
            ("Support Ships:", self._mil_support_ship_type_var, support_types, self._mil_support_ship_var),
        ]:
            r = ttk.Frame(self._mil_navy_comp_frame)
            r.pack(fill="x", pady=2)
            ttk.Label(r, text=label, width=_lw, anchor="w").pack(side="left")
            ttk.Combobox(r, textvariable=type_var, values=types_list,
                         width=_cw, state="readonly").pack(side="left", padx=(0, 6))
            ttk.Entry(r, textvariable=count_var, width=_ew).pack(side="left")

        # ── Général / Amiral ────────────────────────────────────────
        gen_lf = ttk.LabelFrame(create_lf, text="Général / Amiral", padding=(8, 4))
        gen_lf.pack(fill="x", pady=(6, 4))

        gen_row1 = ttk.Frame(gen_lf)
        gen_row1.pack(fill="x", pady=2)
        ttk.Label(gen_row1, text="First Name:", width=14, anchor="w").pack(side="left")
        ttk.Entry(gen_row1, textvariable=self._mil_general_first, width=20).pack(side="left", padx=(0, 8))
        ttk.Label(gen_row1, text="Last Name:", width=12, anchor="w").pack(side="left")
        ttk.Entry(gen_row1, textvariable=self._mil_general_last, width=20).pack(side="left")

        gen_row2 = ttk.Frame(gen_lf)
        gen_row2.pack(fill="x", pady=2)
        ttk.Label(gen_row2, text="Rank:", width=14, anchor="w").pack(side="left")
        ttk.Combobox(gen_row2, textvariable=self._mil_general_rank, 
                     values=["1", "2", "3", "4", "5"], width=5, state="readonly").pack(side="left", padx=(0, 12))
        ttk.Checkbutton(gen_row2, text="Historical", variable=self._mil_general_historical).pack(side="left")

        # ── Boutons Create/Update ───────────────────────────────
        btn_row = ttk.Frame(create_lf)
        btn_row.pack(pady=(8, 2))
        ttk.Button(btn_row, text="Create New Formation",
                   command=self._mil_create).pack(side="left", padx=(0, 6))
        self._mil_update_btn = ttk.Button(btn_row, text="Update Formation",
                   command=self._mil_update, state="disabled")
        self._mil_update_btn.pack(side="left")

        # ── COLONNE DROITE : Manage Existing Formations ────────
        manage_lf = ttk.LabelFrame(content, text="Manage Existing Formations", padding=(10, 6))
        manage_lf.grid(column=1, row=0, sticky="nsew", padx=(5, 0))

        self._mil_manage_tag = tk.StringVar()

        self._mil_listbox = tk.Listbox(manage_lf, height=8, font=("Segoe UI", 9),
                                        activestyle="none", selectmode=tk.SINGLE)
        mil_sb = ttk.Scrollbar(manage_lf, command=self._mil_listbox.yview)
        self._mil_listbox.configure(yscrollcommand=mil_sb.set)
        self._mil_listbox.pack(side="left", fill="both", expand=True)
        mil_sb.pack(side="right", fill="y")
        self._mil_listbox.bind("<<ListboxSelect>>", self._mil_on_select)

        # ── Bouton Delete centré sous la liste ──────────────────
        ttk.Button(manage_lf, text="Delete Formation",
                   command=self._mil_delete).pack(pady=(6, 0))

        if self._selected_country_tag:
            self._mil_tag_var.set(self._selected_country_tag)
            self._mil_manage_tag.set(self._selected_country_tag)
            self._mil_load_formations()

    # ── Actions Military ───────────────────────────────────────

    def _mil_get_formations_dir(self):
        mod = self.config.mod_path
        if not mod:
            return None
        path = os.path.join(mod, "common", "history", "military_formations")
        os.makedirs(path, exist_ok=True)
        return path

    def _mil_find_tag_file(self, tag):
        """Trouve le fichier où le tag existe ou doit être ajouté.
        Retourne (file_path, tag_exists, is_new_file)"""
        formations_dir = self._mil_get_formations_dir()
        if not formations_dir:
            return None, False, True
        
        tag_upper = tag.upper()
        
        # Scanner tous les fichiers .txt dans le dossier (sauf example)
        files = sorted([f for f in os.listdir(formations_dir) 
                       if f.endswith('.txt') and 'example' not in f.lower()])
        
        for fname in files:
            fpath = os.path.join(formations_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Chercher MILITARY_FORMATIONS = {
                m = re.search(r'MILITARY_FORMATIONS\s*=\s*\{', content)
                if not m:
                    continue
                
                # Trouver la fin du bloc MILITARY_FORMATIONS
                start = m.end() - 1
                depth = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                
                # Extraire le bloc MILITARY_FORMATIONS
                mil_block = content[start:end+1]
                
                # Chercher c:TAG ?= { dans ce bloc
                if re.search(rf'c:{tag_upper}\s*\??=\s*\{{', mil_block):
                    return fpath, True, False
            except Exception as e:
                print(f"Erreur lecture {fname}: {e}")
        
        # Le tag n'existe pas - retourner le chemin pour 99_hmm_military_formations.txt
        new_file = os.path.join(formations_dir, "99_hmm_military_formations.txt")
        return new_file, False, True

    def _mil_get_file(self, tag):
        """Ancienne fonction conservée pour compatibilité - retourne le fichier du tag"""
        mod = self.config.mod_path
        if not mod or not tag:
            return None
        path = os.path.join(mod, "common", "history", "military_formations")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, f"{tag}_formations.txt")

    def _mil_load_strategic_regions_list(self):
        """Charge la liste des régions stratégiques depuis le fichier data."""
        base = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.normpath(os.path.join(base, "..", "data",
                                 "strategic_regions", "strategic_regions_by_continent.txt"))
        items = []
        try:
            with open(data_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        continent = line.lstrip("#").rstrip(":").strip().upper()
                        items.append(f"── {continent} ──")
                    else:
                        items.append(line)
        except Exception:
            pass
        return items

    def _mil_on_sr_selected(self, event=None):
        """Ignore la sélection si c'est un en-tête de continent."""
        val = self._mil_sr_var.get()
        if val.startswith("──"):
            self._mil_sr_var.set("")

    def _mil_load_unit_types_from_file(self, filename):
        """Parse un fichier de types d'unités et retourne {section: [unit_types]}."""
        # Utiliser le répertoire du projet (parent de modules)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(base, "data", "combat_unit_types", filename)
        data_path = os.path.normpath(data_path)
        result = {}
        current_section = None
        try:
            with open(data_path, "r", encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("###"):
                        current_section = line.lstrip("#").strip()
                        result[current_section] = []
                    elif current_section is not None:
                        result[current_section].append(line)
        except Exception as e:
            print(f"Erreur lecture {data_path}: {e}")
        return result

    def _mil_on_type_change(self):
        """Affiche le cadre Army ou Navy selon la sélection."""
        if self._mil_type_var.get() == "army":
            self._mil_navy_comp_frame.pack_forget()
            self._mil_army_comp_frame.pack(fill="x")
        else:
            self._mil_army_comp_frame.pack_forget()
            self._mil_navy_comp_frame.pack(fill="x")

    def _mil_refresh_states(self):
        """Charge les états possédés par le tag courant dans le combobox."""
        tag = self._mil_tag_var.get().strip().upper()
        states = self._mil_load_states_for_tag(tag)
        self._mil_state_combo["values"] = states
        if states:
            if self._mil_state_var.get() not in states:
                self._mil_state_var.set(states[0])
        else:
            self._mil_state_var.set("")

    def _mil_load_states_for_tag(self, tag):
        """Parse le fichier 00_states.txt du mod et retourne les états du tag."""
        mod = self.config.mod_path
        if not mod or not tag:
            return []
        states_file = os.path.join(mod, "common", "history", "states", "00_states.txt")
        if not os.path.exists(states_file):
            return []
        states = []
        try:
            with open(states_file, "r", encoding="utf-8") as fh:
                content = fh.read()
            pattern = (
                rf's:(\w+)\s*=\s*\{{[^{{]*?'
                rf'create_state\s*=\s*\{{[^{{]*?'
                rf'country\s*=\s*c:{re.escape(tag.upper())}\b'
            )
            for m in re.finditer(pattern, content, re.DOTALL):
                state = m.group(1)
                if state not in states:
                    states.append(state)
        except Exception as e:
            print(f"Erreur lecture states: {e}")
        return sorted(states)

    def _mil_get_next_formation_index(self, tag):
        """Retourne le prochain indice de formation pour ce tag (basé sur le fichier de localisation)."""
        mod = self.config.mod_path
        if not mod:
            return 1
        yml_path = os.path.join(mod, "localization", "english",
                                "00_hmm_military_formation_name_l_english.yml")
        if not os.path.exists(yml_path):
            return 1
        try:
            with open(yml_path, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            indices = re.findall(
                rf'{re.escape(tag.upper())}_MILITARY_FORMATION_(\d+)', content, re.IGNORECASE
            )
            return max((int(i) for i in indices), default=0) + 1
        except Exception:
            return 1

    def _mil_write_localization(self, tag, key, display_name):
        """Écrit la clé de localisation dans le fichier YML."""
        mod = self.config.mod_path
        if not mod:
            return
        loc_dir = os.path.join(mod, "localization", "english")
        os.makedirs(loc_dir, exist_ok=True)
        yml_path = os.path.join(loc_dir, "00_hmm_military_formation_name_l_english.yml")
        entry = f' {key}: "{display_name}"\n'
        if os.path.exists(yml_path):
            with open(yml_path, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            if not content.endswith("\n"):
                content += "\n"
            content += entry
            with open(yml_path, "w", encoding="utf-8-sig") as fh:
                fh.write(content)
        else:
            with open(yml_path, "w", encoding="utf-8-sig") as fh:
                fh.write(f"l_english:\n{entry}")

    def _mil_write_character_localization(self, key, display_name):
        """Écrit la clé de localisation pour un personnage dans le fichier YML."""
        mod = self.config.mod_path
        if not mod:
            return
        loc_dir = os.path.join(mod, "localization", "english")
        os.makedirs(loc_dir, exist_ok=True)
        yml_path = os.path.join(loc_dir, "00_hmm_character_template_l_english.yml")
        entry = f' {key}: "{display_name}"\n'
        if os.path.exists(yml_path):
            with open(yml_path, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            # Vérifier si la clé existe déjà
            if f" {key}:" not in content:
                if not content.endswith("\n"):
                    content += "\n"
                content += entry
                with open(yml_path, "w", encoding="utf-8-sig") as fh:
                    fh.write(content)
        else:
            with open(yml_path, "w", encoding="utf-8-sig") as fh:
                fh.write(f"l_english:\n{entry}")

    def _mil_create(self):
        tag = self._mil_tag_var.get().strip().upper()
        name = self._mil_name_var.get().strip()
        if not tag or not name:
            messagebox.showerror("Erreur", "Country Tag et Formation Name sont obligatoires")
            return

        # Trouver le fichier où ajouter le tag (existant ou nouveau)
        fpath, tag_exists, is_new = self._mil_find_tag_file(tag)
        if not fpath:
            messagebox.showerror("Erreur", "Impossible de trouver le dossier des formations")
            return

        state    = self._mil_state_var.get().strip()
        hq_region = self._mil_sr_var.get().strip()
        ftype    = self._mil_type_var.get()

        try:
            infantry      = int(self._mil_infantry_var.get()     or 0)
            artillery     = int(self._mil_artillery_var.get()    or 0)
            cavalry       = int(self._mil_cavalry_var.get()      or 0)
            light_count   = int(self._mil_light_ship_var.get()   or 0)
            capital_count = int(self._mil_capital_ship_var.get() or 0)
            support_count = int(self._mil_support_ship_var.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Les valeurs de composition doivent être des entiers")
            return

        # Générer la clé de localisation et l'écrire dans le YML
        idx = self._mil_get_next_formation_index(tag)
        loc_key = f"{tag}_MILITARY_FORMATION_{idx:02d}"
        self._mil_write_localization(tag, loc_key, name)

        # Déterminer le type d'unité selon le type de formation
        unit_type = "army"
        if ftype == "navy":
            unit_type = "fleet"

        # Générer les combat_unit blocks
        state_code = state if state else "STATE_CAPITAL"
        units_str = ""
        if ftype == "army":
            if infantry:
                ut = self._mil_infantry_type_var.get() or "combat_unit_type_line_infantry"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {infantry}\n\t\t\t}}"
            if artillery:
                ut = self._mil_artillery_type_var.get() or "combat_unit_type_cannon_artillery"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {artillery}\n\t\t\t}}"
            if cavalry:
                ut = self._mil_cavalry_type_var.get() or "combat_unit_type_hussars"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {cavalry}\n\t\t\t}}"
        else:  # navy
            if light_count:
                ut = self._mil_light_ship_type_var.get() or "combat_unit_type_frigate"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {light_count}\n\t\t\t}}"
            if capital_count:
                ut = self._mil_capital_ship_type_var.get() or "combat_unit_type_man_o_war"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {capital_count}\n\t\t\t}}"
            if support_count:
                ut = self._mil_support_ship_type_var.get() or "combat_unit_type_submarine"
                units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {support_count}\n\t\t\t}}"

        # Générer le bloc au nouveau format
        hq_str = f"sr:{hq_region}" if hq_region else "sr:region_capital"
        
        # Ajouter save_scope_as à la formation
        scope_key = f"{tag}_MILITARY_FORMATION_{idx:02d}"
        
        formation_block = (
            f"\n\t\tcreate_military_formation = {{\n"
            f"\t\t\ttype = {unit_type}\n"
            f"\t\t\thq_region = {hq_str}\n"
            f"\t\t\tname = {loc_key}\n"
            f"{units_str}\n"
            f"\t\t\tsave_scope_as = {scope_key}\n"
            f"\t\t}}\n"
        )
        
        # Générer le bloc du général/de l'amiral
        general_block = ""
        char_scope_key = f"character_{scope_key}"
        
        # Déterminer is_general ou is_admiral
        is_general = "yes" if ftype == "army" else "no"
        is_admiral = "yes" if ftype == "navy" else "no"
        
        # Préparer les noms
        first_name_input = self._mil_general_first.get().strip()
        last_name_input = self._mil_general_last.get().strip()
        historical = "yes" if self._mil_general_historical.get() else "no"
        rank = self._mil_general_rank.get().strip() or "5"
        
        # Générer les clés de localisation si nom custom
        first_key = ""
        last_key = ""
        
        if first_name_input:
            # Transformer le nom en clé valide
            first_key = first_name_input.lower().replace(" ", "_")
            first_key = re.sub(r'[^a-z0-9_]', '', first_key)
            first_key = f"{tag.lower()}_{first_key}_first"
            
            # Ajouter la localisation
            self._mil_write_character_localization(first_key, first_name_input)
        else:
            # Utiliser le pattern par défaut
            first_key = f"character_{scope_key}"
        
        if last_name_input:
            last_key = last_name_input.lower().replace(" ", "_")
            last_key = re.sub(r'[^a-z0-9_]', '', last_key)
            last_key = f"{tag.lower()}_{last_key}_last"
            self._mil_write_character_localization(last_key, last_name_input)
        
        # HQ sans le préfixe sr:
        hq_no_prefix = hq_region if hq_region else "region_capital"
        
        # Construire le bloc create_character
        general_block = (
            f"\n\t\tcreate_character = {{\n"
            f"\t\t\tis_general = {is_general}\n"
            f"\t\t\tis_admiral = {is_admiral}\n"
            f"\t\t\tfirst_name = {first_key}\n"
        )
        
        if last_key:
            general_block += f"\t\t\tlast_name = {last_key}\n"
        
        general_block += (
            f"\t\t\thistorical = {historical}\n"
            f"\t\t\thq = {hq_no_prefix}\n"
            f"\t\t\tcommander_rank = commander_rank_{rank}\n"
            f"\t\t\tage = 40\n"
            f"\t\t\tsave_scope_as = {char_scope_key}\n"
            f"\t\t}}\n"
        )
        
        # Bloc scope de transfert
        scope_block = (
            f"\n\t\tscope:{char_scope_key} = {{\n"
            f"\t\t\ttransfer_to_formation = scope:{scope_key}\n"
            f"\t\t}}\n"
        )

        # Lire le contenu existant
        existing = ""
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                existing = f.read()

        # Insérer le bloc dans MILITARY_FORMATIONS
        if "MILITARY_FORMATIONS" in existing:
            # Le fichier a déjà MILITARY_FORMATIONS
            if tag_exists:
                # Le tag existe déjà - ajouter après le bloc du tag
                # Trouver la position après le bloc du tag
                tag_pattern = rf'(c:{tag}\s*\??=\s*\{{)'
                match = re.search(tag_pattern, existing)
                if match:
                    # Trouver la fin du bloc du tag
                    brace_start = match.end() - 1
                    depth = 0
                    for i in range(brace_start, len(existing)):
                        if existing[i] == '{':
                            depth += 1
                        elif existing[i] == '}':
                            depth -= 1
                            if depth == 0:
                                # Insérer juste avant la fermeture du bloc du tag
                                insert_pos = i
                                # Combiner tous les blocs (formation + général + scope)
                                full_block = formation_block + general_block + scope_block
                                existing = existing[:insert_pos] + full_block + existing[insert_pos:]
                                break
            else:
                # Le tag n'existe pas - ajouter un nouveau bloc
                # Trouver la fin de MILITARY_FORMATIONS
                match = re.search(r'(MILITARY_FORMATIONS\s*=\s*\{)', existing)
                if match:
                    brace_start = match.end() - 1
                    depth = 0
                    for i in range(brace_start, len(existing)):
                        if existing[i] == '{':
                            depth += 1
                        elif existing[i] == '}':
                            depth -= 1
                            if depth == 0:
                                # Insérer juste avant la fermeture
                                insert_pos = i
                                # Combiner tous les blocs (formation + général + scope)
                                full_block = formation_block + general_block + scope_block
                                tag_block = f"\n\tc:{tag} ?= {{{full_block}\t}}\n"
                                existing = existing[:insert_pos] + tag_block + existing[insert_pos:]
                                break
        else:
            # Créer un nouveau fichier MILITARY_FORMATIONS
            content = f"MILITARY_FORMATIONS = {{\n\tc:{tag} ?= {{{formation_block}\t}}\n}}\n"
            existing = content

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(existing)

        # Créer ou mettre à jour le bâtiment militaire
        if state:
            total_units = self._mil_calculate_total_units(ftype)
            building_type = "building_barrack" if ftype == "army" else "building_naval_base"
            # Only create/update building if Building checkbox is checked
            if self._mil_building_var.get():
                self._mil_create_or_update_building(tag, state, building_type, total_units)

        messagebox.showinfo("OK", f"Formation '{name}' créée pour {tag}\nFichier: {os.path.basename(fpath)}")
        if self._mil_manage_tag.get().strip().upper() == tag:
            self._mil_load_formations()

    def _mil_load_formations(self):
        tag = self._mil_tag_var.get().strip().upper()
        self._mil_manage_tag.set(tag)
        self._mil_listbox.delete(0, tk.END)
        self._mil_formations = []

        # Rafraîchir le combobox des états pour ce pays
        self._mil_refresh_states()

        if not tag:
            return

        # Scanner tous les fichiers dans le dossier military_formations (sauf example)
        formations_dir = self._mil_get_formations_dir()
        if not formations_dir or not os.path.exists(formations_dir):
            return

        files = sorted([f for f in os.listdir(formations_dir) 
                       if f.endswith('.txt') and 'example' not in f.lower()])
        
        for fname in files:
            fpath = os.path.join(formations_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"Erreur lecture {fname}: {e}")
                continue

            # Chercher le bloc du tag dans ce fichier
            # Cherche c:TAG ?= { ... } dans MILITARY_FORMATIONS
            tag_pattern = rf'c:{tag}\s*\??=\s*\{{'
            tag_match = re.search(tag_pattern, content)
            if not tag_match:
                continue
            
            # Extraire le bloc du tag pour chercher les formations
            tag_start = tag_match.start()
            brace_start = tag_match.end() - 1
            depth = 0
            tag_end = brace_start
            for i in range(brace_start, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        tag_end = i + 1
                        break
            
            tag_block = content[tag_start:tag_end]
            
            # Chercher les formations au nouveau format (create_military_formation) dans le bloc du tag
            for m in re.finditer(
                r'create_military_formation\s*=\s*\{[^}]*?name\s*=\s*(\w+)',
                tag_block, re.DOTALL
            ):
                name = m.group(1)
                self._mil_formations.append({
                    "name": name, 
                    "match_start": m.start() + tag_start,
                    "file": fpath
                })
                self._mil_listbox.insert(tk.END, f"{name} ({fname})")
            
            # Chercher aussi les formations à l'ancien format (create_army/create_navy) dans le bloc du tag
            for m in re.finditer(
                r'create_(?:army|navy)\s*=\s*\{[^}]*name\s*=\s*"([^"]*)"',
                tag_block, re.DOTALL
            ):
                name = m.group(1)
                # Éviter les doublons
                if not any(f["name"] == name for f in self._mil_formations):
                    self._mil_formations.append({
                        "name": name, 
                        "match_start": m.start() + tag_start,
                        "file": fpath
                    })
                    self._mil_listbox.insert(tk.END, f"{name} ({fname})")

    def _mil_on_select(self, *_):
        sel = self._mil_listbox.curselection()
        if sel:
            idx = sel[0]
            formation = self._mil_formations[idx]
            self._mil_selected_idx = idx
            
            # Activer le bouton Update Formation
            self._mil_update_btn.config(state="normal")
            
            # Charger les détails de la formation depuis le fichier
            self._mil_load_formation_details(formation["name"], formation["file"])
    
    def _mil_load_formation_details(self, name, fpath):
        """Charge les détails d'une formation depuis le fichier et remplit les champs."""
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Erreur lecture {fpath}: {e}")
            return
        
        tag = self._mil_tag_var.get().strip().upper()
        
        # Chercher le bloc de la formation
        # Nouveau format: create_military_formation = { ... name = XXX ... }
        pattern = rf'create_military_formation\s*=\s*\{{[^}}]*?name\s*=\s*{re.escape(name)}'
        m = re.search(pattern, content, re.DOTALL)
        
        if m:
            # Extraire le bloc de la formation
            start = m.start()
            depth = 0
            end = start
            for i in range(start, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            block = content[start:end]
            
            # Extraire le type (army ou fleet)
            type_match = re.search(r'type\s*=\s*(\w+)', block)
            if type_match:
                unit_type = type_match.group(1)
                if unit_type == "fleet":
                    self._mil_type_var.set("navy")
                    self._mil_on_type_change()
                else:
                    self._mil_type_var.set("army")
                    self._mil_on_type_change()
            
            # Extraire la région HQ
            hq_match = re.search(r'hq_region\s*=\s*sr:(\w+)', block)
            if hq_match:
                self._mil_sr_var.set(hq_match.group(1))
            
            # Extraire les combat_units
            for unit_match in re.finditer(
                r'combat_unit\s*=\s*\{{[^}}]*?type\s*=\s*unit_type:(\w+)[^}}]*?state_region\s*=\s*s:(\w+)[^}}]*?count\s*=\s*(\d+)',
                block, re.DOTALL
            ):
                unit_type = unit_match.group(1)
                count = int(unit_match.group(3))
                
                # Déterminer si c'est une unité terrestre ou navale
                land_types = ["line_infantry", "cannon_artillery", "hussars", "dragoons", "cavalry"]
                navy_types = ["frigate", "man_o_war", "submarine", "ironclad", "steam_frigate"]
                
                is_navy = any(ut in unit_type for ut in navy_types)
                
                if is_navy:
                    if "frigate" in unit_type or "light" in unit_type.lower():
                        self._mil_light_ship_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_light_ship_var.set(str(count))
                    elif "man_o_war" in unit_type or "capital" in unit_type.lower():
                        self._mil_capital_ship_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_capital_ship_var.set(str(count))
                    else:
                        self._mil_support_ship_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_support_ship_var.set(str(count))
                else:
                    if "infantry" in unit_type or "line" in unit_type:
                        self._mil_infantry_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_infantry_var.set(str(count))
                    elif "artillery" in unit_type or "cannon" in unit_type:
                        self._mil_artillery_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_artillery_var.set(str(count))
                    else:
                        self._mil_cavalry_type_var.set(f"combat_unit_type_{unit_type}")
                        self._mil_cavalry_var.set(str(count))
            
            # Charger le nom depuis la localisation
            loc_path = os.path.join(self.config.mod_path, "localization", "english", 
                                    "00_hmm_military_formation_name_l_english.yml")
            if os.path.exists(loc_path):
                with open(loc_path, "r", encoding="utf-8-sig") as f:
                    loc = f.read()
                name_match = re.search(rf'^\s*{re.escape(name)}:0\s+"([^"]*)"', loc, re.MULTILINE)
                if name_match:
                    self._mil_name_var.set(name_match.group(1))
                else:
                    self._mil_name_var.set(name)
            else:
                self._mil_name_var.set(name)
        else:
            # Ancien format: create_army ou create_navyname = "XXX"
            old_pattern = rf'create_(?:army|navy)\s*=\s*\{{[^}}]*?name\s*=\s*"{re.escape(name)}"'
            m = re.search(old_pattern, content, re.DOTALL)
            if m:
                start = m.start()
                depth = 0
                end = start
                for i in range(start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                
                block = content[start:end]
                
                # Type
                if "create_army" in block:
                    self._mil_type_var.set("army")
                    self._mil_on_type_change()
                else:
                    self._mil_type_var.set("navy")
                    self._mil_on_type_change()
                
                # Nom
                self._mil_name_var.set(name)
                
                # Régiment count (ancien format)
                inf_match = re.search(r'regiments\s*=\s*\{\s*infantry\s*=\s*(\d+)', block)
                if inf_match:
                    self._mil_infantry_var.set(inf_match.group(1))
                
                art_match = re.search(r'artillery\s*=\s*(\d+)', block)
                if art_match:
                    self._mil_artillery_var.set(art_match.group(1))
                
                cav_match = re.search(r'cavalry\s*=\s*(\d+)', block)
                if cav_match:
                    self._mil_cavalry_var.set(cav_match.group(1))
                
                # Navy count (ancien format)
                trans_match = re.search(r'transports\s*=\s*(\d+)', block)
                if trans_match:
                    self._mil_light_ship_var.set(trans_match.group(1))
                
                warships_match = re.search(r'warships\s*=\s*(\d+)', block)
                if warships_match:
                    self._mil_capital_ship_var.set(warships_match.group(1))

    def _mil_update(self):
        """Met à jour la formation sélectionnée avec les valeurs des champs actuels."""
        sel = self._mil_listbox.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une formation")
            return
        
        tag = self._mil_tag_var.get().strip().upper()
        name = self._mil_name_var.get().strip()
        if not tag or not name:
            messagebox.showerror("Erreur", "Country Tag et Formation Name sont obligatoires")
            return
        
        # Récupérer l'ancienne formation
        old_formation = self._mil_formations[sel[0]]
        old_name = old_formation["name"]
        fpath = old_formation["file"]
        
        if not os.path.exists(fpath):
            messagebox.showerror("Erreur", "Fichier de formation introuvable")
            return
        
        # Lire le contenu du fichier
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Chercher et remplacer le bloc de la formation
        # Nouveau format: create_military_formation = { ... name = XXX ... }
        old_pattern = rf'create_military_formation\s*=\s*\{{[^}}]*?name\s*=\s*{re.escape(old_name)}'
        m = re.search(old_pattern, content, re.DOTALL)
        
        if m:
            # Extraire l'ancien bloc
            start = m.start()
            depth = 0
            end = start
            for i in range(start, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            
            old_block = content[start:end]

            # Mémoriser l'ancienne composition pour calculer le delta bâtiment
            old_total_units = self._mil_count_units_in_block(old_block)
            old_state_m = re.search(r'state_region\s*=\s*s:(\w+)', old_block)
            old_state = old_state_m.group(1) if old_state_m else ""

            # Générer le nouveau bloc avec les valeurs actuelles
            state    = self._mil_state_var.get().strip()
            hq_region = self._mil_sr_var.get().strip()
            ftype    = self._mil_type_var.get()
            
            try:
                infantry      = int(self._mil_infantry_var.get()     or 0)
                artillery     = int(self._mil_artillery_var.get()    or 0)
                cavalry       = int(self._mil_cavalry_var.get()      or 0)
                light_count   = int(self._mil_light_ship_var.get()   or 0)
                capital_count = int(self._mil_capital_ship_var.get() or 0)
                support_count = int(self._mil_support_ship_var.get() or 0)
            except ValueError:
                messagebox.showerror("Erreur", "Les valeurs de composition doivent être des entiers")
                return
            
            # Conserver l'ancienne clé de localisation ou en créer une nouvelle
            loc_key = old_name  # Garder la même clé pour éviter de créer des doublons
            
            # Mettre à jour la localisation si le nom a changé
            new_display_name = self._mil_name_var.get().strip()
            loc_path = os.path.join(self.config.mod_path, "localization", "english",
                                    "00_hmm_military_formation_name_l_english.yml")
            if os.path.exists(loc_path):
                with open(loc_path, "r", encoding="utf-8-sig") as f:
                    loc_content = f.read()
                # Remplacer le nom dans la localisation
                old_name_match = re.search(rf'^\s*{re.escape(old_name)}:0\s+"([^"]*)"', loc_content, re.MULTILINE)
                if old_name_match:
                    old_display = old_name_match.group(1)
                    if old_display != new_display_name:
                        loc_content = re.sub(
                            rf'^\s*{re.escape(old_name)}:0\s+".*"$',
                            f' {old_name}:0 "{new_display_name}"',
                            loc_content, flags=re.MULTILINE
                        )
                        with open(loc_path, "w", encoding="utf-8-sig") as f:
                            f.write(loc_content)
            
            # Déterminer le type d'unité
            unit_type = "army"
            if ftype == "navy":
                unit_type = "fleet"
            
            # Générer les combat_unit blocks
            state_code = state if state else "STATE_CAPITAL"
            units_str = ""
            if ftype == "army":
                if infantry:
                    ut = self._mil_infantry_type_var.get() or "combat_unit_type_line_infantry"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {infantry}\n\t\t\t}}"
                if artillery:
                    ut = self._mil_artillery_type_var.get() or "combat_unit_type_cannon_artillery"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {artillery}\n\t\t\t}}"
                if cavalry:
                    ut = self._mil_cavalry_type_var.get() or "combat_unit_type_hussars"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {cavalry}\n\t\t\t}}"
            else:  # navy
                if light_count:
                    ut = self._mil_light_ship_type_var.get() or "combat_unit_type_frigate"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {light_count}\n\t\t\t}}"
                if capital_count:
                    ut = self._mil_capital_ship_type_var.get() or "combat_unit_type_man_o_war"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {capital_count}\n\t\t\t}}"
                if support_count:
                    ut = self._mil_support_ship_type_var.get() or "combat_unit_type_submarine"
                    units_str += f"\n\t\t\tcombat_unit = {{\n\t\t\t\ttype = unit_type:{ut}\n\t\t\t\tstate_region = s:{state_code}\n\t\t\t\tcount = {support_count}\n\t\t\t}}"
            
            # Générer le nouveau bloc
            hq_str = f"sr:{hq_region}" if hq_region else "sr:region_capital"
            new_block = (
                f"create_military_formation = {{\n"
                f"\t\t\ttype = {unit_type}\n"
                f"\t\t\thq_region = {hq_str}\n"
                f"\t\t\tname = {loc_key}\n"
                f"{units_str}\n"
                f"\t\t}}"
            )
            
            # Remplacer l'ancien bloc par le nouveau
            content = content[:start] + new_block + content[end:]
            
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Mettre à jour le bâtiment militaire par delta (nouveau - ancien)
            new_total_units = self._mil_calculate_total_units(ftype)
            building_type = "building_barrack" if ftype == "army" else "building_naval_base"

            if old_state and old_state != state:
                # L'état a changé : retirer de l'ancien, ajouter au nouveau
                if old_total_units > 0:
                    self._mil_create_or_update_building(tag, old_state, building_type, -old_total_units)
                if new_total_units > 0 and state:
                    self._mil_create_or_update_building(tag, state, building_type, new_total_units)
            elif state:
                delta = new_total_units - old_total_units
                if delta != 0:
                    self._mil_create_or_update_building(tag, state, building_type, delta)

            messagebox.showinfo("OK", f"Formation '{new_display_name}' mise à jour !")
            self._mil_load_formations()
        else:
            # Ancien format - essayer de mettre à jour
            old_pattern = rf'create_(?:army|navy)\s*=\s*\{{[^}}]*?name\s*=\s*"{re.escape(old_name)}"'
            m = re.search(old_pattern, content, re.DOTALL)
            if m:
                messagebox.showwarning("Attention", "Les formations au ancien format ne peuvent pas être complètement modifiées. Veuillez les supprimer et en créer une nouvelle.")
            else:
                messagebox.showerror("Erreur", "Formation introuvable dans le fichier")

    def _mil_delete(self):
        sel = self._mil_listbox.curselection()
        if not sel:
            messagebox.showerror("Erreur", "Sélectionne une formation")
            return

        formation = self._mil_formations[sel[0]]
        name  = formation["name"]
        fpath = formation["file"]
        tag   = self._mil_tag_var.get().strip().upper()
        is_hmm = bool(re.match(r'^[A-Z]{2,4}_MILITARY_FORMATION_\d+$', name))

        if not messagebox.askyesno("Confirmer", f"Supprimer '{name}' ?"):
            return

        if not os.path.exists(fpath):
            messagebox.showerror("Erreur", "Fichier de formation introuvable")
            return

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # ── Trouver et extraire le bloc create_military_formation ──
        pattern = rf'create_military_formation\s*=\s*\{{[^{{]*?name\s*=\s*{re.escape(name)}'
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            messagebox.showerror("Erreur", f"Formation '{name}' introuvable dans le fichier")
            return

        start = m.start()
        depth = 0
        end = start
        for i in range(start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        block = content[start:end]

        # ── Supprimer le bloc (+ éventuelle ligne vide avant) ──
        pre = content[:start].rstrip('\n')
        content = pre + '\n' + content[end:]

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)

        # ── Si formation HMM : supprimer la localisation + ajuster bâtiment ──
        if is_hmm:
            # Localisation
            mod = self.config.mod_path
            if mod:
                yml_path = os.path.join(mod, "localization", "english",
                                        "00_hmm_military_formation_name_l_english.yml")
                if os.path.exists(yml_path):
                    with open(yml_path, "r", encoding="utf-8-sig") as f:
                        loc = f.read()
                    loc = re.sub(rf'^\s*{re.escape(name)}[^:\n]*:.*\n?', '', loc, flags=re.MULTILINE)
                    with open(yml_path, "w", encoding="utf-8-sig") as f:
                        f.write(loc)

            # Bâtiment : soustraire les unités de la formation supprimée
            total_units = self._mil_count_units_in_block(block)
            state_m = re.search(r'state_region\s*=\s*s:(\w+)', block)
            state   = state_m.group(1) if state_m else ""
            ftype_m = re.search(r'\btype\s*=\s*(army|fleet)\b', block)
            ftype   = ftype_m.group(1) if ftype_m else "army"
            building_type = "building_barrack" if ftype == "army" else "building_naval_base"
            if state and total_units > 0:
                self._mil_create_or_update_building(tag, state, building_type, -total_units)

        self._mil_load_formations()

    # ── Gestion des bâtiments militaires ───────────────────────

    def _mil_count_units_in_block(self, block):
        """Retourne la somme de tous les count= dans un bloc create_military_formation."""
        total = 0
        for m in re.finditer(r'\bcount\s*=\s*(\d+)', block):
            total += int(m.group(1))
        return total

    def _mil_calculate_total_units(self, ftype):
        """Calcule le total des unités selon le type de formation."""
        try:
            if ftype == "army":
                infantry = int(self._mil_infantry_var.get() or 0)
                artillery = int(self._mil_artillery_var.get() or 0)
                cavalry = int(self._mil_cavalry_var.get() or 0)
                return infantry + artillery + cavalry
            else:  # navy
                light = int(self._mil_light_ship_var.get() or 0)
                capital = int(self._mil_capital_ship_var.get() or 0)
                support = int(self._mil_support_ship_var.get() or 0)
                return light + capital + support
        except ValueError:
            return 0

    def _mil_get_building_file(self, state):
        """Trouve le fichier de bâtiments approprié pour un état donné."""
        mod = self.config.mod_path
        if not mod or not state:
            return None
        buildings_dir = os.path.join(mod, "common", "history", "buildings")
        if not os.path.exists(buildings_dir):
            return None
        # Scanner les fichiers pour trouver celui qui contient l'état
        for fname in sorted(os.listdir(buildings_dir)):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(buildings_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                if f"s:{state}=" in content:
                    return fpath
            except Exception as e:
                print(f"Erreur lecture {fname}: {e}")
        # Si pas trouvé, retourner le fichier par défaut
        return os.path.join(buildings_dir, "00_west_europe.txt")

    def _mil_remove_all_buildings_for_tag(self, tag, building_type):
        """Supprime tous les bâtiments du type spécifié pour un TAG dans tous les états."""
        mod = self.config.mod_path
        if not mod or not tag or not building_type:
            return
        
        buildings_dir = os.path.join(mod, "common", "history", "buildings")
        if not os.path.exists(buildings_dir):
            return
        
        # Déterminer le pattern de recherche selon le type de bâtiment
        if "barrack" in building_type:
            building_pattern = r'building[_"a-z]*barracks?'
        else:
            building_pattern = r'building[_"a-z]*naval[_"a-z]*base?'
        
        # Scanner tous les fichiers de bâtiments
        for fname in os.listdir(buildings_dir):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(buildings_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue
            
            modified = False
            
            # Chercher tous les blocs d'états (s:XXX = { ... region_state:TAG = { ... })
            for state_match in re.finditer(r's:(\w+)\s*=\s*\{', content):
                state_code = state_match.group(1)
                brace_start = state_match.end() - 1
                depth = 0
                state_end = brace_start
                for i in range(brace_start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                    if depth == 0:
                        state_end = i
                        break
                
                state_block = content[brace_start:state_end]
                
                # Vérifier si ce state_block contient region_state:TAG
                if f"region_state:{tag}" not in state_block:
                    continue
                
                # Chercher et supprimer tous les create_building du type spécifié
                new_state_block = state_block
                for building_match in re.finditer(r'create_building\s*=\s*\{', state_block):
                    bstart = building_match.start()
                    bdepth = 0
                    bend = bstart
                    for i in range(bstart, len(state_block)):
                        if state_block[i] == '{':
                            bdepth += 1
                        elif state_block[i] == '}':
                            bdepth -= 1
                        if bdepth == 0:
                            bend = i + 1
                            break
                    
                    building_block = state_block[bstart:bend]
                    
                    # Vérifier si c'est le bon type de bâtiment
                    if re.search(building_pattern, building_block, re.IGNORECASE):
                        # Supprimer ce bloc
                        new_state_block = new_state_block[:bstart] + new_state_block[bend:]
                        modified = True
                
                if modified:
                    content = content[:brace_start] + new_state_block + content[state_end:]
            
            if modified:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

    def _mil_create_or_update_building(self, tag, state, building_type, levels):
        """Crée, met à jour ou réduit un bâtiment militaire (levels = delta, peut être négatif)."""
        if not state or not building_type or levels == 0:
            return
        
        fpath = self._mil_get_building_file(state)
        if not fpath or not os.path.exists(fpath):
            print(f"Fichier de bâtiments introuvable pour l'état {state}")
            return
        
        # Lire le contenu existant
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Déterminer le pattern de recherche selon le type de bâtiment
        # building_barracks (avec s) ou building_naval_base
        if "barrack" in building_type:
            building_pattern = r'building[_"a-z]*barracks?'
        else:
            building_pattern = r'building[_"a-z]*naval[_"a-z]*base?'
        
        # Chercher tous les bâtiments militaires existants pour ce tag dans cet état
        # et calculer le niveau total actuel
        state_block_pattern = rf's:{re.escape(state)}\s*=\s*\{{[^}}]*region_state:{re.escape(tag)}\s*=\s*\{{'
        state_match = re.search(state_block_pattern, content, re.DOTALL)
        
        current_total_levels = 0
        existing_building_block = None
        existing_building_start = -1
        
        if state_match:
            # Extraire le bloc region_state
            brace_start = state_match.end() - 1
            depth = 0
            region_end = brace_start
            for i in range(brace_start, len(content)):
                if content[i] == '{':
                    depth += 1
                elif content[i] == '}':
                    depth -= 1
                    if depth == 0:
                        region_end = i
                        break
            
            region_block = content[brace_start:region_end]
            
            # Chercher tous les create_building avec le type de bâtiment militaire
            for bm in re.finditer(r'create_building\s*=\s*\{', region_block):
                bstart = bm.start()
                bdepth = 0
                bend = bstart
                for i in range(bstart, len(region_block)):
                    if region_block[i] == '{':
                        bdepth += 1
                    elif region_block[i] == '}':
                        bdepth -= 1
                        if bdepth == 0:
                            bend = i + 1
                            break
                
                building_block = region_block[bstart:bend]
                
                # Vérifier si c'est un bâtiment militaire du bon type
                if re.search(building_pattern, building_block, re.IGNORECASE):
                    # Extraire le niveau actuel
                    level_match = re.search(r'levels\s*=\s*(\d+)', building_block)
                    if level_match:
                        current_total_levels += int(level_match.group(1))
                    
                    # Garder le premier bloc trouvé pour le mettre à jour
                    if existing_building_block is None:
                        existing_building_block = building_block
                        existing_building_start = bstart
        
        # Calculer le nouveau niveau total (clamp à 0)
        new_total_levels = max(0, current_total_levels + levels)

        if existing_building_block:
            abs_start = brace_start + existing_building_start
            abs_end = abs_start + len(existing_building_block)
            if new_total_levels == 0:
                # Supprimer le bloc create_building entier
                content = content[:abs_start] + content[abs_end:]
            else:
                # Mettre à jour le niveau
                updated_block = re.sub(
                    r'(levels\s*=\s*)\d+',
                    rf'\g<1>{new_total_levels}',
                    existing_building_block
                )
                content = content[:abs_start] + updated_block + content[abs_end:]
        elif levels <= 0:
            # Pas de bâtiment existant et delta négatif : rien à faire
            return
        else:
            # Créer un nouveau bâtiment
            state_pattern = rf'(s:{re.escape(state)}\s*=\s*\{{[^}}]*region_state:{re.escape(tag)}\s*=\s*\{{)'
            state_match = re.search(state_pattern, content, re.DOTALL)
            
            if state_match:
                # Trouver la fin du bloc region_state
                brace_start = state_match.end() - 1
                depth = 0
                insert_pos = brace_start
                for i in range(brace_start, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            insert_pos = i
                            break
                
                building_block = f'''
			create_building={{
				building="{building_type}"
				add_ownership={{
					country={{
						country="c:{tag}"
						levels={levels}
					}}
				}}
				reserves=1
			}}'''
                content = content[:insert_pos] + building_block + content[insert_pos:]
            else:
                # Créer un nouveau bloc state + region_state + building
                if "BUILDINGS" in content:
                    match = re.search(r'(BUILDINGS\s*=\s*\{)', content)
                    if match:
                        brace_start = match.end() - 1
                        depth = 0
                        insert_pos = brace_start
                        for i in range(brace_start, len(content)):
                            if content[i] == '{':
                                depth += 1
                            elif content[i] == '}':
                                depth -= 1
                                if depth == 0:
                                    insert_pos = i
                                    break
                        
                        building_block = f'''
	s:{state}={{
		region_state:{tag}={{
			create_building={{
				building="{building_type}"
				add_ownership={{
					country={{
						country="c:{tag}"
						levels={levels}
					}}
				}}
				reserves=1
			}}
		}}
	}}'''
                        content = content[:insert_pos] + building_block + content[insert_pos:]
        
        # Écrire le contenu mis à jour
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Bâtiment {building_type} pour {tag}/{state}: delta={levels:+d} → levels={new_total_levels}")

    def _mil_delete_all_buildings_for_tag(self):
        """Supprime tous les bâtiments militaires (barracks + naval bases) du TAG après confirmation."""
        tag = self._mil_tag_var.get().strip().upper()
        if not tag:
            messagebox.showerror("Erreur", "Sélectionne d'abord un pays")
            return
        
        if not messagebox.askyesno("Confirmer", 
            f"Supprimer TOUS les bâtiments militaires (barracks + naval bases) du pays {tag} dans tous les états ?"):
            return
        
        # Supprimer les barracks
        self._mil_remove_all_buildings_for_tag(tag, "building_barrack")
        
        # Supprimer les naval bases
        self._mil_remove_all_buildings_for_tag(tag, "building_naval_base")
        
        messagebox.showinfo("OK", f"Tous les bâtiments militaires de {tag} ont été supprimés !")


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
