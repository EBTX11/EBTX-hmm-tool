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
        self._tab_character(nb)
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
        match = re.search(r'\(([A-Z]{3})\)', selected_text)
        if match:
            self._selected_country_tag = match.group(1)
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
        ttk.Button(top, text="Sauvegarder", command=self._save_general_data).pack(side="right", padx=5)

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

        color_row = ttk.Frame(s1)
        color_row.grid(row=2, column=0, columnspan=4, sticky="w", pady=4)
        ttk.Label(color_row, text="Color:", anchor="w").pack(side="left", padx=(0, 6))
        self._gen_color_preview = tk.Label(color_row, width=5, bg="#646464", relief="solid", cursor="hand2")
        self._gen_color_preview.pack(side="left", padx=(0, 6))
        self._gen_color_preview.bind("<Button-1>", self._pick_color)
        ttk.Button(color_row, text="Color Picker", command=self._pick_color).pack(side="left")

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

        ttk.Label(s3, text="Capital State:", anchor="w").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s3, textvariable=self._gen_capital).grid(row=3, column=1, columnspan=3, sticky="ew", pady=4)

        # ── Ruler Designer ─────────────────────────────────────
        s4 = ttk.LabelFrame(gi, text="Ruler Designer", padding=(10, 6))
        s4.pack(fill="x", padx=10, pady=4)
        s4.columnconfigure(1, weight=1)
        s4.columnconfigure(3, weight=1)

        ttk.Label(s4, text="First Name:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_first).grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s4, text="Last Name:", anchor="w").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_last).grid(row=0, column=3, sticky="ew", pady=4)

        ttk.Label(s4, text="Interest Group:", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_ig).grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=4)
        ttk.Label(s4, text="Ideology:", anchor="w").grid(row=1, column=2, sticky="w", padx=(0, 6), pady=4)
        ttk.Entry(s4, textvariable=self._gen_ruler_ideology).grid(row=1, column=3, sticky="ew", pady=4)

        ttk.Checkbutton(s4, text="Female", variable=self._gen_ruler_female).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=4)

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
        loc_path = os.path.join(mod, "localization", "english", "00_hmm_countries_l_english.yml")
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                loc = f.read()
            m = re.search(rf'^\s*{tag}:0\s+"([^"]*)"', loc, re.MULTILINE)
            if m:
                self._gen_name.set(m.group(1))
            m = re.search(rf'^\s*{tag}_ADJ:0\s+"([^"]*)"', loc, re.MULTILINE)
            if m:
                self._gen_adj.set(m.group(1))

        # ── Country Definition ──
        def_dir = os.path.join(mod, "common", "country_definitions")
        if os.path.exists(def_dir):
            for fname in os.listdir(def_dir):
                fpath = os.path.join(def_dir, fname)
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                m = re.search(rf'\b{tag}\s*=\s*{{([^}}]*(?:{{[^}}]*}}[^}}]*)*)}}', content, re.DOTALL)
                if m:
                    block = m.group(1)
                    cm = re.search(r'color\s*=\s*\{[^\d]*(\d+)[^\d]+(\d+)[^\d]+(\d+)', block)
                    if cm:
                        self._gen_color_rgb = [int(cm.group(i)) for i in range(1, 4)]
                        hex_col = "#{:02x}{:02x}{:02x}".format(*self._gen_color_rgb)
                        self._gen_color_preview.config(bg=hex_col)
                    tm = re.search(r'tier\s*=\s*(\w+)', block)
                    if tm:
                        self._gen_tier.set(tm.group(1))
                    ctm = re.search(r'country_type\s*=\s*(\w+)', block)
                    if ctm:
                        self._gen_type.set(ctm.group(1))
                    capm = re.search(r'capital\s*=\s*(\w+)', block)
                    if capm:
                        self._gen_capital.set(capm.group(1))
                    cults = re.findall(r'cultures\s*=\s*\{([^}]*)\}', block)
                    if cults:
                        self._gen_cultures_lb.delete(0, tk.END)
                        for c in cults[0].split():
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
                    rm = re.search(r'set_state_religion\s*=\s*(?:religion:)?(\w+)', content)
                    if rm:
                        self._gen_religion.set(rm.group(1))
                    break

        self._gen_status.config(text=f"Chargé : {tag}", foreground="#6af")

    def _save_general_data(self):
        mod = self.config.mod_path
        tag = self._gen_tag_var.get().strip().upper()
        if not mod or not tag:
            messagebox.showerror("Erreur", "Aucun pays sélectionné")
            return

        # ── Localisation ──
        loc_path = os.path.join(mod, "localization", "english", "00_hmm_countries_l_english.yml")
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as f:
                loc = f.read()
            name = self._gen_name.get().strip()
            adj  = self._gen_adj.get().strip()
            if name:
                loc = re.sub(rf'(\s*{tag}:0\s+")[^"]*(")', rf'\g<1>{name}\2', loc)
            if adj:
                loc = re.sub(rf'(\s*{tag}_ADJ:0\s+")[^"]*(")', rf'\g<1>{adj}\2', loc)
            with open(loc_path, "w", encoding="utf-8-sig") as f:
                f.write(loc)

        # ── Country Definition ──
        def_dir = os.path.join(mod, "common", "country_definitions")
        if os.path.exists(def_dir):
            for fname in os.listdir(def_dir):
                fpath = os.path.join(def_dir, fname)
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                if re.search(rf'\b{tag}\s*=\s*{{', content):
                    r, g, b = self._gen_color_rgb
                    content = re.sub(
                        rf'({tag}\s*=\s*{{[^}}]*color\s*=\s*{{)[^}}]*(}})',
                        rf'\g<1> {r} {g} {b} \2', content, flags=re.DOTALL)
                    content = re.sub(rf'(tier\s*=\s*)\w+', rf'\g<1>{self._gen_tier.get()}', content)
                    content = re.sub(rf'(country_type\s*=\s*)\w+', rf'\g<1>{self._gen_type.get()}', content)
                    content = re.sub(rf'(capital\s*=\s*)\w+', rf'\g<1>{self._gen_capital.get()}', content)
                    cults = list(self._gen_cultures_lb.get(0, tk.END))
                    if cults:
                        content = re.sub(
                            r'(cultures\s*=\s*\{)[^}]*(\})',
                            rf'\g<1> {" ".join(cults)} \2', content)
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
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 12))
        self._mod_status = ttk.Label(top, text="Sélectionne un pays dans la liste", foreground="#888")
        self._mod_status.pack(side="left")
        ttk.Button(top, text="Appliquer les lois", command=self._apply_laws).pack(side="right", padx=5)

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
        self._dipl_hist_file = ""

        # ── Barre du haut ──────────────────────────────────────
        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=(10, 6))

        ttk.Label(top, text="Country Tag:").pack(side="left")
        ttk.Entry(top, textvariable=self._dipl_tag_var, width=8,
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 10))
        ttk.Button(top, text="Load Data", command=self._load_diplomacy_data).pack(side="left")
        self._dipl_status = ttk.Label(top, text="", foreground="#888")
        self._dipl_status.pack(side="left", padx=10)

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
                                         font=("Segoe UI", 9), height=10)
        subj_sb = ttk.Scrollbar(subj_lf, command=self._dipl_subj_lb.yview)
        self._dipl_subj_lb.config(yscrollcommand=subj_sb.set)
        self._dipl_subj_lb.pack(side="left", fill="both", expand=True)
        subj_sb.pack(side="right", fill="y")
        ttk.Button(subj_lf, text="Remove Selected",
                   command=lambda: self._dipl_remove(self._dipl_subj_lb)).pack(fill="x", pady=(4, 0))

        # Hostile / Truces
        host_lf = ttk.LabelFrame(lists_frame, text="Hostile / Truces", padding=(6, 4))
        host_lf.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._dipl_host_lb = tk.Listbox(host_lf, selectmode=tk.SINGLE, activestyle="none",
                                         font=("Segoe UI", 9), height=10)
        host_sb = ttk.Scrollbar(host_lf, command=self._dipl_host_lb.yview)
        self._dipl_host_lb.config(yscrollcommand=host_sb.set)
        self._dipl_host_lb.pack(side="left", fill="both", expand=True)
        host_sb.pack(side="right", fill="y")
        ttk.Button(host_lf, text="Remove Selected",
                   command=lambda: self._dipl_remove(self._dipl_host_lb)).pack(fill="x", pady=(4, 0))

        # ── Add New Relationship ───────────────────────────────
        add_lf = ttk.LabelFrame(f, text="Add New Relationship", padding=(10, 6))
        add_lf.pack(fill="x", padx=10, pady=(10, 4))

        self._dipl_target_var  = tk.StringVar()
        self._dipl_rel_type    = tk.StringVar(value="subject")
        self._dipl_subj_type   = tk.StringVar(value="colony")

        add_row = ttk.Frame(add_lf)
        add_row.pack(fill="x")

        ttk.Label(add_row, text="Target Tag:").pack(side="left")
        ttk.Entry(add_row, textvariable=self._dipl_target_var, width=8).pack(side="left", padx=(4, 14))

        ttk.Radiobutton(add_row, text="Subject", variable=self._dipl_rel_type,
                        value="subject").pack(side="left", padx=2)
        ttk.Radiobutton(add_row, text="Hostile/Truce", variable=self._dipl_rel_type,
                        value="hostile").pack(side="left", padx=2)

        subj_types = ["colony", "puppet", "dominion", "protectorate",
                      "personal_union", "tributary", "vassal"]
        ttk.Combobox(add_row, textvariable=self._dipl_subj_type, values=subj_types,
                     width=16, state="readonly").pack(side="left", padx=(10, 6))
        ttk.Button(add_row, text="Create",
                   command=self._dipl_add_relationship).pack(side="left", padx=4)

        # ── Set Relations ──────────────────────────────────────
        rel_lf = ttk.LabelFrame(f, text="Set Relations", padding=(10, 6))
        rel_lf.pack(fill="x", padx=10, pady=(4, 10))

        self._dipl_rel_target = tk.StringVar()
        self._dipl_rel_value  = tk.StringVar(value="0")

        rel_row = ttk.Frame(rel_lf)
        rel_row.pack(fill="x")
        ttk.Label(rel_row, text="Target Tag:").pack(side="left")
        ttk.Entry(rel_row, textvariable=self._dipl_rel_target, width=8).pack(side="left", padx=(4, 16))
        ttk.Label(rel_row, text="Value (-100 to 100):").pack(side="left")
        ttk.Entry(rel_row, textvariable=self._dipl_rel_value, width=6).pack(side="left", padx=(4, 10))
        ttk.Button(rel_row, text="Set Relation",
                   command=self._dipl_set_relation).pack(side="left")

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

        hist_dir = os.path.join(mod, "common", "history", "countries")
        self._dipl_hist_file = ""
        if os.path.exists(hist_dir):
            for fname in os.listdir(hist_dir):
                if fname.upper().startswith(tag):
                    self._dipl_hist_file = os.path.join(hist_dir, fname)
                    break

        if not self._dipl_hist_file:
            self._dipl_status.config(text=f"Fichier introuvable pour {tag}", foreground="#f66")
            return

        with open(self._dipl_hist_file, "r", encoding="utf-8") as f:
            content = f.read()

        self._dipl_subj_lb.delete(0, tk.END)
        self._dipl_host_lb.delete(0, tk.END)

        # Sujets
        for m in re.finditer(
            r'create_subject\s*=\s*\{[^}]*subject_type\s*=\s*(\w+)[^}]*subject\s*=\s*c:(\w+)[^}]*\}',
            content, re.DOTALL
        ):
            self._dipl_subj_lb.insert(tk.END, f"{m.group(2)} ({m.group(1)})")

        # Relations hostiles (valeur négative)
        for m in re.finditer(
            r'set_relations\s*=\s*\{[^}]*country\s*=\s*c:(\w+)[^}]*value\s*=\s*(-\d+)[^}]*\}',
            content, re.DOTALL
        ):
            self._dipl_host_lb.insert(tk.END, f"{m.group(1)} ({m.group(2)})")

        self._dipl_status.config(
            text=f"Chargé : {tag}  |  {self._dipl_subj_lb.size()} sujets, "
                 f"{self._dipl_host_lb.size()} hostiles",
            foreground="#6af")

    def _dipl_remove(self, listbox):
        sel = listbox.curselection()
        if sel:
            listbox.delete(sel[0])

    def _dipl_add_relationship(self):
        target = self._dipl_target_var.get().strip().upper()
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        rel = self._dipl_rel_type.get()
        if rel == "subject":
            subj_type = self._dipl_subj_type.get()
            self._dipl_subj_lb.insert(tk.END, f"{target} ({subj_type})")
        else:
            self._dipl_host_lb.insert(tk.END, f"{target} (hostile)")
        self._dipl_target_var.set("")
        self._dipl_save()

    def _dipl_set_relation(self):
        target = self._dipl_rel_target.get().strip().upper()
        try:
            value = int(self._dipl_rel_value.get())
            value = max(-100, min(100, value))
        except ValueError:
            messagebox.showerror("Erreur", "Valeur invalide (entier -100 à 100)")
            return
        if not target:
            messagebox.showerror("Erreur", "Entre un Target Tag")
            return
        if not self._dipl_hist_file:
            messagebox.showerror("Erreur", "Charge d'abord un pays")
            return

        with open(self._dipl_hist_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Supprimer entrée existante pour ce tag
        content = re.sub(
            rf'set_relations\s*=\s*\{{[^}}]*country\s*=\s*c:{target}[^}}]*\}}',
            '', content, flags=re.DOTALL)

        # Insérer la nouvelle relation
        new_entry = f"\n\t\tset_relations = {{ country = c:{target} value = {value} }}"
        tag = self._dipl_tag_var.get().strip().upper()
        content = re.sub(
            rf'(c:{tag}\s*\??=\s*{{)',
            rf'\1{new_entry}',
            content, count=1)

        with open(self._dipl_hist_file, "w", encoding="utf-8") as f:
            f.write(content)

        if value < 0:
            self._dipl_host_lb.insert(tk.END, f"{target} ({value})")
        self._dipl_status.config(text=f"Relation {target} → {value} sauvegardée", foreground="#6f6")

    def _dipl_save(self):
        if not self._dipl_hist_file:
            return
        tag = self._dipl_tag_var.get().strip().upper()

        with open(self._dipl_hist_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Supprimer tous les create_subject existants
        content = re.sub(r'\s*create_subject\s*=\s*\{[^}]*\}', '', content, flags=re.DOTALL)

        # Reconstruire depuis la listbox
        new_subjects = ""
        for entry in self._dipl_subj_lb.get(0, tk.END):
            m = re.match(r'(\w+)\s*\((\w+)\)', entry)
            if m:
                new_subjects += (f"\n\t\tcreate_subject = {{ "
                                 f"subject_type = {m.group(2)} subject = c:{m.group(1)} }}")

        content = re.sub(
            rf'(c:{tag}\s*\??=\s*{{)',
            rf'\1{new_subjects}',
            content, count=1)

        with open(self._dipl_hist_file, "w", encoding="utf-8") as f:
            f.write(content)

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

        ttk.Label(top, text="Target Tag:").pack(side="left")
        ttk.Entry(top, textvariable=self._pb_tag_var, width=8).pack(side="left", padx=(4, 14))
        ttk.Label(top, text="OR Select Bloc:").pack(side="left")
        self._pb_select_cb = ttk.Combobox(top, textvariable=self._pb_select_var,
                                           state="readonly", width=28)
        self._pb_select_cb.pack(side="left", padx=(4, 6))
        self._pb_select_cb.bind("<<ComboboxSelected>>", self._pb_on_select)
        ttk.Button(top, text="Refresh List", command=self._pb_refresh_list).pack(side="left", padx=4)

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

        # ── Create Military Formation ──────────────────────────
        create_lf = ttk.LabelFrame(f, text="Create Military Formation", padding=(12, 8))
        create_lf.pack(fill="x", padx=10, pady=(10, 4))

        row1 = ttk.Frame(create_lf)
        row1.pack(fill="x", pady=3)
        ttk.Label(row1, text="Country Tag:", width=14, anchor="w").pack(side="left")
        ttk.Entry(row1, textvariable=self._mil_tag_var, width=8).pack(side="left", padx=(0, 20))
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

        mgr_top = ttk.Frame(manage_lf)
        mgr_top.pack(fill="x", pady=(0, 4))
        ttk.Label(mgr_top, text="Tag to Manage:").pack(side="left")
        self._mil_manage_tag = tk.StringVar()
        ttk.Entry(mgr_top, textvariable=self._mil_manage_tag, width=8).pack(side="left", padx=(4, 8))
        ttk.Button(mgr_top, text="Load Formations",
                   command=self._mil_load_formations).pack(side="left")

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
        tag = self._mil_manage_tag.get().strip().upper()
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

    def _tab_character(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Character")
        ttk.Label(f, text="Onglet Character", font=("Segoe UI", 12, "bold")).pack(pady=20)

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

        self._execute_button = ttk.Button(base_content, text="Exécuter", command=self._execute_tech_update)
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
