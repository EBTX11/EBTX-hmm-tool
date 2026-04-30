"""
Map Editor pour Victoria 3
- Modes STATE et PROVINCE
- Mode STATE: sélection par sous-état (comportement original)
- Mode PROVINCE: sélection par province, provinces encadrées en noir
- Transfert de provinces entre pays avec réécriture complète des states
- Mode PEINTURE: switch pour peindre directement province ou sous-état sur clic gauche
- Éditeur Homeland/Claim avec autocomplete sur les cultures
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
import shutil
import numpy as np
from PIL import Image, ImageTk
from modules.history_updater import update_history_files

OCEAN_COLOR   = (30,  45,  80)
UNKNOWN_COLOR = (70, 70, 70)
STATE_BORDER_COLOR = (180, 30, 30)
PROV_BORDER_COLOR  = (0,   0,   0)
SELECT_BOOST  = 70
INITIAL_ZOOM  = 0.22
ZOOM_STEP     = 1.25

MODE_STATE    = "state"
MODE_PROVINCE = "province"


def parse_state_regions(sr_dir):
    prov_to_state  = {}
    state_to_provs = {}
    sea_states     = set()
    prov_pat  = re.compile(r'"(x[0-9A-Fa-f]{6})"')
    state_pat = re.compile(r'^(STATE_\w+)\s*=\s*\{', re.MULTILINE)

    for fname in sorted(os.listdir(sr_dir)):
        if not fname.endswith(".txt"):
            continue
        is_sea_file = "seas" in fname.lower() or "ocean" in fname.lower()
        with open(os.path.join(sr_dir, fname), "r", encoding="utf-8-sig") as fh:
            content = fh.read()

        for sm in state_pat.finditer(content):
            state = sm.group(1)
            start = sm.end()
            depth, i = 1, start
            while i < len(content) and depth > 0:
                if content[i] == "{": depth += 1
                elif content[i] == "}": depth -= 1
                i += 1
            block = content[sm.start():i]
            provs = set()
            for pm in prov_pat.finditer(block):
                p = "x" + pm.group(1)[1:].upper()
                provs.add(p)
                prov_to_state[p] = state
            state_to_provs[state] = provs
            if is_sea_file:
                sea_states.add(state)
    return prov_to_state, state_to_provs, sea_states


def parse_states_file(states_path):
    prov_owner_map = {}
    substates = {}
    if not os.path.exists(states_path):
        return prov_owner_map, substates
    with open(states_path, "r", encoding="utf-8-sig") as fh:
        content = fh.read()
    prov_pat = re.compile(r'x[0-9A-Fa-f]{6}')
    for sm in re.finditer(r's:(STATE_\w+)\s*=\s*\{', content):
        state = sm.group(1)
        start = sm.end()
        depth, i = 1, start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1
        state_block = content[start:i - 1]
        for cs_match in re.finditer(r'create_state\s*=\s*\{', state_block):
            cs_start = cs_match.end()
            depth2, j = 1, cs_start
            while j < len(state_block) and depth2 > 0:
                if state_block[j] == "{": depth2 += 1
                elif state_block[j] == "}": depth2 -= 1
                j += 1
            cs_block = state_block[cs_start:j - 1]
            tag_m = re.search(r'country\s*=\s*c:(\w+)', cs_block)
            if not tag_m:
                continue
            tag = tag_m.group(1)
            provs = set()
            for pm in prov_pat.finditer(cs_block):
                p = "x" + pm.group(0)[1:].upper()
                provs.add(p)
                prov_owner_map[p] = tag
            if provs:
                key = (state, tag)
                substates.setdefault(key, set()).update(provs)
    return prov_owner_map, substates


def parse_country_colors(country_defs_dir):
    colors = {}
    if not os.path.isdir(country_defs_dir):
        return colors
    for fname in os.listdir(country_defs_dir):
        if not fname.endswith(".txt"):
            continue
        try:
            with open(os.path.join(country_defs_dir, fname), "r", encoding="utf-8-sig") as fh:
                content = fh.read()
        except Exception:
            continue
        for tm in re.finditer(r'^([A-Z][A-Z0-9]{2})\s*=\s*\{', content, re.MULTILINE):
            tag = tm.group(1)
            start = tm.end()
            depth, i = 1, start
            while i < len(content) and depth > 0:
                if content[i] == "{": depth += 1
                elif content[i] == "}": depth -= 1
                i += 1
            block = content[start:i]
            cm = re.search(r'color\s*=\s*\{\s*(\d+)\s+(\d+)\s+(\d+)', block)
            if cm:
                colors[tag] = (int(cm.group(1)), int(cm.group(2)), int(cm.group(3)))
    return colors


def _random_country_color(tag):
    import hashlib
    h = hashlib.md5(tag.encode()).digest()
    return (80 + h[0] % 150, 80 + h[1] % 150, 80 + h[2] % 150)


def parse_homelands_claims(states_path):
    """Parse add_homeland et add_claim depuis 00_states.txt."""
    result = {}
    if not os.path.exists(states_path):
        return result
    with open(states_path, "r", encoding="utf-8-sig") as fh:
        content = fh.read()
    state_pat = re.compile(r's:(STATE_\w+)\s*=\s*\{')
    i = 0
    while i < len(content):
        sm = state_pat.search(content, i)
        if not sm:
            break
        state = sm.group(1)
        block_start = sm.end()
        depth, j = 1, block_start
        while j < len(content) and depth > 0:
            if content[j] == '{': depth += 1
            elif content[j] == '}': depth -= 1
            j += 1
        block = content[block_start:j - 1]
        homelands = []
        claims = []
        for hm in re.finditer(r'add_homeland\s*=\s*cu:(\w+)', block):
            homelands.append(hm.group(1))
        for cm in re.finditer(r'add_claim\s*=\s*c:(\w+)', block):
            claims.append(cm.group(1).upper())
        if homelands or claims:
            result[state] = {'homelands': homelands, 'claims': claims}
        i = j
    return result


def parse_cultures(culture_file):
    """Parse toutes les cultures depuis le fichier culture."""
    cultures = []
    if not os.path.exists(culture_file):
        return cultures
    with open(culture_file, "r", encoding="utf-8-sig") as fh:
        content = fh.read()
    for sm in re.finditer(r'^(\w+)\s*=\s*\{', content, re.MULTILINE):
        cultures.append(sm.group(1))
    return sorted(cultures)


def parse_religions(religion_file):
    """Parse toutes les religions depuis le fichier religion."""
    religions = []
    if not os.path.exists(religion_file):
        return religions
    with open(religion_file, "r", encoding="utf-8-sig") as fh:
        content = fh.read()
    for sm in re.finditer(r'^(\w+)\s*=\s*\{', content, re.MULTILINE):
        religions.append(sm.group(1))
    return sorted(religions)


def find_next_tag(country_defs_dir):
    """Trouve le prochain tag EXX libre."""
    max_num = 0
    if not os.path.isdir(country_defs_dir):
        return "E01"
    for fname in os.listdir(country_defs_dir):
        if not fname.endswith(".txt"):
            continue
        try:
            with open(os.path.join(country_defs_dir, fname), "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            for tm in re.finditer(r'^([A-Z])(\d{2})\s*=\s*\{', content, re.MULTILINE):
                prefix = tm.group(1)
                num = int(tm.group(2))
                if prefix == "E":
                    max_num = max(max_num, num)
        except Exception:
            continue
    return f"E{max_num + 1:02d}"


def build_render(provinces_arr, prov_to_state, prov_owner_map, country_colors, sea_states=None, mode="state"):
    H, W = provinces_arr.shape[:2]
    sea_states = sea_states or set()
    r = provinces_arr[:, :, 0].astype(np.uint32)
    g = provinces_arr[:, :, 1].astype(np.uint32)
    b = provinces_arr[:, :, 2].astype(np.uint32)
    prov_ints = (r << 16) | (g << 8) | b
    color_table = np.full((16_777_216, 3), fill_value=list(OCEAN_COLOR), dtype=np.uint8)
    state_names = sorted(s for s in set(prov_to_state.values()) if s not in sea_states)
    state_ids = {s: idx + 1 for idx, s in enumerate(state_names)}
    border_table = np.zeros(16_777_216, dtype=np.uint32)
    fallback_cache = {}
    for prov_hex, state_name in prov_to_state.items():
        try:
            prov_int = int(prov_hex[1:], 16)
        except ValueError:
            continue
        tag = prov_owner_map.get(prov_hex)
        if tag:
            if tag in country_colors:
                color = country_colors[tag]
            else:
                if tag not in fallback_cache:
                    fallback_cache[tag] = _random_country_color(tag)
                color = fallback_cache[tag]
        else:
            color = UNKNOWN_COLOR
        color_table[prov_int] = color
        if state_name not in sea_states:
            border_table[prov_int] = state_ids.get(state_name, 0)
    rendered = color_table[prov_ints]
    border_map = border_table[prov_ints]
    land = border_map > 0
    h_diff = border_map[:, :-1] != border_map[:, 1:]
    v_diff = border_map[:-1, :] != border_map[1:, :]
    h_land = land[:, :-1] & land[:, 1:]
    v_land = land[:-1, :] & land[1:, :]
    state_border = np.zeros((H, W), dtype=bool)
    state_border[:, :-1] |= h_diff & h_land
    state_border[:, 1:]  |= h_diff & h_land
    state_border[:-1, :] |= v_diff & v_land
    state_border[1:, :]  |= v_diff & v_land
    rendered[state_border] = STATE_BORDER_COLOR
    if mode == MODE_PROVINCE:
        prov_border = np.zeros((H, W), dtype=bool)
        ph_diff = prov_ints[:, :-1] != prov_ints[:, 1:]
        pv_diff = prov_ints[:-1, :] != prov_ints[1:, :]
        prov_border[:, :-1] |= ph_diff
        prov_border[:, 1:]  |= ph_diff
        prov_border[:-1, :] |= pv_diff
        prov_border[1:, :]  |= pv_diff
        prov_border &= ~state_border
        rendered[prov_border] = PROV_BORDER_COLOR
    return rendered, prov_ints, state_border


class MapFrame(ttk.Frame):

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._prov_arr = None
        self._prov_ints = None
        self._rendered = None
        self._prov_to_state = {}
        self._state_to_provs = {}
        self._prov_owner_map = {}
        self._substates = {}
        self._country_colors = {}
        self._sea_states = set()
        self._zoom = INITIAL_ZOOM
        self._photo = None
        self._selected = set()
        self._prov_selected = set()
        self._loading = False
        self._mode = MODE_STATE
        self._modified_states = set()
        self._state_border_mask = None
        self._zoomed_arr = None
        self._prov_ints_zoomed = None
        self._zoom_at_cache = None
        self._state_hc = {}
        self._cultures = []
        self._religions = []
        # Variables pour la sélection par rectangle
        self._selection_rect_start = None  # (x, y) du début du rectangle
        self._selection_rect_end = None    # (x, y) de la fin du rectangle
        self._selection_rect_id = None     # ID du rectangle sur le canvas
        
        # Variables pour stocker les derniers paramètres de création de pays
        self._last_country_params = {
            'color': "120 80 180",
            'country_type': "recognized",
            'tier': "kingdom",
            'religion': "",
            'cultures': [],
            'capital': ""
        }
        self._build()

    def _get_mod_map_data_dir(self):
        """Retourne le chemin du dossier map_data du mod."""
        mod = self.config.mod_path
        if not mod:
            return None
        return os.path.join(mod, "map_data")

    def _get_prov_png_path(self):
        """Retourne le chemin de provinces.png dans le mod."""
        map_data_dir = self._get_mod_map_data_dir()
        if not map_data_dir:
            return None
        return os.path.join(map_data_dir, "provinces.png")

    def _get_state_regions_dir(self):
        """Retourne le chemin du dossier state_regions dans le mod."""
        map_data_dir = self._get_mod_map_data_dir()
        if not map_data_dir:
            return None
        return os.path.join(map_data_dir, "state_regions")

    def _get_data_dir(self):
        """Retourne le chemin du dossier data de l'outil (pour cultures, religions, etc.)."""
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

    def _build(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=4)
        ttk.Button(toolbar, text="Charger la carte", command=self._start_load).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Zoom +", command=self._zoom_in).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zoom -", command=self._zoom_out).pack(side="left", padx=2)
        self._zoom_label = ttk.Label(toolbar, text=f"Zoom: {int(self._zoom*100)}%")
        self._zoom_label.pack(side="left", padx=8)
        mode_frame = ttk.Frame(toolbar)
        mode_frame.pack(side="left", padx=20)
        ttk.Label(mode_frame, text="Mode:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self._state_btn = ttk.Button(mode_frame, text="STATE", width=8, command=lambda: self._set_mode(MODE_STATE))
        self._state_btn.pack(side="left", padx=2)
        self._prov_btn = ttk.Button(mode_frame, text="PROVINCE", width=10, command=lambda: self._set_mode(MODE_PROVINCE))
        self._prov_btn.pack(side="left", padx=2)
        # Mode de selection
        sel_frame = ttk.Frame(toolbar)
        sel_frame.pack(side="left", padx=20)
        ttk.Label(sel_frame, text="Selection:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self._normal_btn = ttk.Button(sel_frame, text="NORMAL", width=8, command=lambda: self._set_paint_mode(False))
        self._normal_btn.pack(side="left", padx=2)
        self._paint_btn = ttk.Button(sel_frame, text="PEINTURE", width=10, command=lambda: self._set_paint_mode(True))
        self._paint_btn.pack(side="left", padx=2)
        self._paint_mode_var = tk.BooleanVar(value=False)
        self._status_label = ttk.Label(toolbar, text="Appuie sur 'Charger la carte'", foreground="#888")
        self._status_label.pack(side="left", padx=10)
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)
        map_container = ttk.Frame(main)
        map_container.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(map_container, bg="#1e2030", cursor="crosshair", highlightthickness=0)
        hbar = ttk.Scrollbar(map_container, orient="horizontal", command=self._canvas.xview)
        vbar = ttk.Scrollbar(map_container, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Button-1>", self._on_click_start)
        self._canvas.bind("<B1-Motion>", self._on_click_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_click_release)
        self._canvas.bind("<Control-Button-1>", self._on_ctrl_click)
        self._canvas.bind("<Button-3>", self._on_right_click)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-2>", self._start_pan)
        self._canvas.bind("<B2-Motion>", self._do_pan)
        panel = ttk.Frame(main, width=240)
        panel.pack(side="right", fill="y", padx=6, pady=4)
        panel.pack_propagate(False)
        ttk.Label(panel, text="Selection (etat / TAG)", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        lf = ttk.Frame(panel)
        lf.pack(fill="both", expand=True, pady=4)
        self._sel_listbox = tk.Listbox(lf, height=12, font=("Consolas", 8), selectmode="extended")
        lb_sc = ttk.Scrollbar(lf, command=self._sel_listbox.yview)
        self._sel_listbox.configure(yscrollcommand=lb_sc.set)
        lb_sc.pack(side="right", fill="y")
        self._sel_listbox.pack(fill="both", expand=True)
        ttk.Button(panel, text="Vider la selection", command=self._clear_selection).pack(fill="x", pady=2)

        # --- HOMELAND / CLAIM ---
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(panel, text="Homeland:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        hf = ttk.Frame(panel)
        hf.pack(fill="x", pady=2)
        self._hl_labels_frame = ttk.Frame(hf)
        self._hl_labels_frame.pack(fill="x")
        h_add = ttk.Frame(hf)
        h_add.pack(fill="x", pady=2)
        self._hl_var = tk.StringVar()
        self._hl_entry = tk.Entry(h_add, textvariable=self._hl_var, width=14, font=("Consolas", 9))
        self._hl_entry.pack(side="left", fill="x", expand=True)
        self._hl_entry.bind("<KeyRelease>", self._on_hl_keyrelease)
        ttk.Button(h_add, text="+", width=3, command=lambda: self._add_hc("homeland")).pack(side="left", padx=2)
        # Listbox dans un frame separé pour apparaitre en dessous
        self._hl_listbox_frame = ttk.Frame(hf)
        self._hl_listbox_frame.pack(fill="x")
        self._hl_listbox_frame.pack_forget()
        self._hl_listbox = tk.Listbox(self._hl_listbox_frame, height=5, font=("Consolas", 9), selectmode="single")
        self._hl_listbox.pack(fill="x")
        self._hl_listbox.bind("<<ListboxSelect>>", self._on_hl_select)

        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=3)
        ttk.Label(panel, text="Claim:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        cf = ttk.Frame(panel)
        cf.pack(fill="x", pady=2)
        self._cl_labels_frame = ttk.Frame(cf)
        self._cl_labels_frame.pack(fill="x")
        c_add = ttk.Frame(cf)
        c_add.pack(fill="x", pady=2)
        self._cl_entry = tk.StringVar()
        ttk.Entry(c_add, textvariable=self._cl_entry, width=16, font=("Consolas", 9)).pack(side="left", fill="x", expand=True)
        ttk.Button(c_add, text="+", width=3, command=lambda: self._add_hc("claim")).pack(side="left", padx=2)


        ttk.Button(panel, text="Sauver Homeland/Claim", command=self._save_hc).pack(fill="x", pady=4)

        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(panel, text="Info province", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._info_label = ttk.Label(panel, text="-", font=("Consolas", 8), wraplength=220, justify="left")
        self._info_label.pack(anchor="w", pady=4)
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        self._paint_status = ttk.Label(panel, text="", font=("Segoe UI", 8, "bold"), foreground="#f9e2af")
        self._paint_status.pack(anchor="w", pady=(0, 4))
        ttk.Button(panel, text="Nouveau pays", command=self._open_new_country_popup).pack(fill="x", pady=2)
        ttk.Label(panel, text="Transferer vers TAG :", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._new_tag = tk.StringVar()
        ttk.Entry(panel, textvariable=self._new_tag, width=10, font=("Consolas", 11)).pack(fill="x", pady=4)
        ttk.Button(panel, text="Transferer", command=self._transfer, style="Accent.TButton").pack(fill="x", pady=2)
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Button(panel, text="Sauvegarder (00_states.txt)", command=self._save).pack(fill="x")
        self._save_status = ttk.Label(panel, text="", foreground="#a6e3a1", font=("Segoe UI", 8), wraplength=220)
        self._save_status.pack(anchor="w", pady=2)
        
        # ============================================================
        # STATE CHECK - Section séparée dans le panneau latéral
        # ============================================================
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(panel, text="State Check", font=("Segoe UI", 10, "bold"), foreground="#89b4fa").pack(anchor="w")
        ttk.Label(panel, text="Vérifie provinces dans\nstate_regions", font=("Segoe UI", 7), wraplength=220, justify="left").pack(anchor="w", pady=(0, 4))
        
        # Bouton pour lancer le screening
        self._sc_button = ttk.Button(panel, text="Lancer le screening", command=self._run_state_screening)
        self._sc_button.pack(fill="x", pady=4)
        
        # Zone de résultats
        ttk.Label(panel, text="Résultats:", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 2))
        sc_results_frame = ttk.Frame(panel)
        sc_results_frame.pack(fill="both", expand=True, pady=4)
        self._sc_results_listbox = tk.Listbox(sc_results_frame, height=10, font=("Consolas", 7))
        scroller = ttk.Scrollbar(sc_results_frame, command=self._sc_results_listbox.yview)
        self._sc_results_listbox.configure(yscrollcommand=scroller.set)
        scroller.pack(side="right", fill="y")
        self._sc_results_listbox.pack(fill="both", expand=True)
        
        # Statistiques
        self._sc_stats_label = ttk.Label(panel, text="", font=("Segoe UI", 7), wraplength=220)
        self._sc_stats_label.pack(anchor="w", pady=2)
        
        # Options
        self._sc_backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Sauvegarde auto", variable=self._sc_backup_var).pack(anchor="w", pady=2)
        
        # Bouton pour appliquer les corrections
        self._sc_apply_button = ttk.Button(panel, text="Appliquer les corrections", command=self._apply_state_corrections, state="disabled")
        self._sc_apply_button.pack(fill="x", pady=4)
        
        # Status
        self._sc_status = ttk.Label(panel, text="", font=("Segoe UI", 7), foreground="#a6e3a1")
        self._sc_status.pack(anchor="w", pady=2)
        
        # Variables pour stocker les résultats du screening
        self._sc_missing_provinces = {}
        self._sc_orphelines = {}
        self._sc_missing_states = set()

    def _set_mode(self, mode):
        self._mode = mode
        self._state_btn.configure(style="TButton")
        self._prov_btn.configure(style="TButton")
        if mode == MODE_STATE:
            self._state_btn.configure(style="Accent.TButton")
            self._status_label.config(text="Mode STATE -- Clic = selection | Switch = peindre")
        else:
            self._prov_btn.configure(style="Accent.TButton")
            self._status_label.config(text="Mode PROVINCE -- Clic g. = selection | Clic dr. = recup. TAG | Switch = peintre")
        self._clear_selection()
        if self._prov_arr is not None:
            self._refresh_render()

    def _set_paint_mode(self, paint):
        self._paint_mode_var.set(paint)
        self._normal_btn.configure(style="TButton")
        self._paint_btn.configure(style="TButton")
        if paint:
            self._paint_btn.configure(style="Accent.TButton")
            tag = self._new_tag.get().strip().upper()
            if tag and len(tag) >= 2:
                self._paint_status.config(text=f"Peint. {tag}")
            else:
                self._paint_status.config(text="Peint. ?")
            self.winfo_toplevel().config(cursor="crosshair")
        else:
            self._normal_btn.configure(style="Accent.TButton")
            self._paint_status.config(text="")
            self.winfo_toplevel().config(cursor="arrow")

    def _refresh_render(self):
        if self._prov_arr is None:
            return
        rendered, prov_ints, state_border = build_render(
            self._prov_arr, self._prov_to_state,
            self._prov_owner_map, self._country_colors, self._sea_states,
            mode=self._mode)
        self._rendered = rendered
        self._prov_ints = prov_ints
        self._state_border_mask = state_border
        self._zoom_at_cache = None
        self._display_map()

    def _start_load(self):
        if self._loading:
            return
        self._loading = True
        self._status_label.config(text="Chargement en cours...")
        self._canvas.delete("all")
        self._canvas.create_text(400, 200, text="Chargement de la carte...", fill="#cba6f7", font=("Segoe UI", 14))
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        try:
            mod = self.config.mod_path
            self._after("Parsing state_regions...")
            # Utiliser le state_regions du mod
            state_regions_dir = self._get_state_regions_dir()
            if not state_regions_dir or not os.path.exists(state_regions_dir):
                raise FileNotFoundError(f"Dossier state_regions introuvable dans le mod: {state_regions_dir}")
            prov_to_state, state_to_provs, sea_states = parse_state_regions(state_regions_dir)
            self._prov_to_state = prov_to_state
            self._state_to_provs = state_to_provs
            self._sea_states = sea_states
            self._after("Lecture 00_states.txt...")
            states_path = os.path.join(mod, "common/history/states/00_states.txt") if mod else ""
            if mod and os.path.exists(states_path):
                prov_owner_map, substates = parse_states_file(states_path)
            else:
                vanilla = self.config.vanilla_path
                vpath = os.path.join(vanilla, "game/common/history/states/00_states.txt") if vanilla else ""
                prov_owner_map, substates = parse_states_file(vpath) if os.path.exists(vpath) else ({}, {})
            self._prov_owner_map = prov_owner_map
            self._substates = substates
            self._after("Lecture country_definitions...")
            country_colors = {}
            if mod:
                for d in [
                    os.path.join(mod, "common/country_definitions"),
                    os.path.join(self.config.vanilla_path or "", "game/common/country_definitions"),
                ]:
                    if os.path.isdir(d):
                        country_colors.update(parse_country_colors(d))
            self._country_colors = country_colors
            self._after("Chargement provinces.png...")
            # Utiliser le provinces.png du mod
            prov_png_path = self._get_prov_png_path()
            if not prov_png_path or not os.path.exists(prov_png_path):
                raise FileNotFoundError(f"Fichier provinces.png introuvable dans le mod: {prov_png_path}")
            img = Image.open(prov_png_path).convert("RGB")
            self._prov_arr = np.array(img)
            self._after("Rendu numpy...")
            rendered, prov_ints, state_border = build_render(
                self._prov_arr, prov_to_state, prov_owner_map,
                country_colors, sea_states, mode=self._mode)
            self._rendered = rendered
            self._prov_ints = prov_ints
            self._state_border_mask = state_border
            self._zoom_at_cache = None
            split = sum(1 for s in set(k[0] for k in substates) if len([k for k in substates if k[0] == s]) > 1)
            self._state_hc = parse_homelands_claims(states_path) if states_path and os.path.exists(states_path) else {}
            # Charger les cultures (toujours depuis le dossier data de l'outil)
            data_dir = self._get_data_dir()
            culture_file = os.path.join(data_dir, "cultures", "00_cultures.txt")
            self._cultures = parse_cultures(culture_file) if os.path.exists(culture_file) else []
            # Charger les religions (toujours depuis le dossier data de l'outil)
            religion_file = os.path.join(data_dir, "religions", "religion.txt")
            self._religions = parse_religions(religion_file) if os.path.exists(religion_file) else []
            self.after(0, self._init_hl_combo)
            self.after(0, self._display_map)
            self.after(0, lambda: self._status_label.config(
                text=f"Carte chargee -- {len(prov_to_state)} provinces | "
                     f"{len(state_to_provs)} etats | {split} split states | Mode: {self._mode.upper()}"
            ))
        except Exception as e:
            import traceback
            self.after(0, lambda: self._status_label.config(text=f"Erreur: {e}"))
            self.after(0, lambda: messagebox.showerror("Erreur", traceback.format_exc()))
        finally:
            self._loading = False

    def _after(self, msg):
        self.after(0, lambda m=msg: self._status_label.config(text=m))

    def _rebuild_zoom_cache(self):
        if self._rendered is None:
            return
        H, W = self._rendered.shape[:2]
        new_w = max(1, int(W * self._zoom))
        new_h = max(1, int(H * self._zoom))
        ys = np.linspace(0, H - 1, new_h).astype(np.int32)
        xs = np.linspace(0, W - 1, new_w).astype(np.int32)
        self._zoomed_arr = self._rendered[np.ix_(ys, xs)].copy()
        if self._prov_ints is not None:
            self._prov_ints_zoomed = self._prov_ints[np.ix_(ys, xs)]
        self._zoom_at_cache = self._zoom

    def _fast_update_provinces(self, prov_hex_set, new_tag):
        if self._rendered is None or self._prov_ints is None:
            return
        color = self._country_colors.get(new_tag) or _random_country_color(new_tag)
        prov_ints_list = []
        for ph in prov_hex_set:
            try:
                prov_ints_list.append(int(ph[1:], 16))
            except ValueError:
                pass
        if not prov_ints_list:
            return
        mask = np.isin(self._prov_ints, prov_ints_list)
        if self._state_border_mask is not None:
            mask &= ~self._state_border_mask
        self._rendered[mask] = color
        self._zoom_at_cache = None

    def _display_map(self):
        if self._rendered is None:
            return
        if self._zoom_at_cache != self._zoom or self._zoomed_arr is None:
            self._rebuild_zoom_cache()
        arr = self._zoomed_arr.copy()
        if (self._selected or self._prov_selected) and self._prov_ints_zoomed is not None:
            prov_ints_sel = []
            for (state, tag) in self._selected:
                for ph in self._substates.get((state, tag), set()):
                    try:
                        prov_ints_sel.append(int(ph[1:], 16))
                    except ValueError:
                        pass
            for ph in self._prov_selected:
                try:
                    prov_ints_sel.append(int(ph[1:], 16))
                except ValueError:
                    pass
            if prov_ints_sel:
                mask = np.isin(self._prov_ints_zoomed, prov_ints_sel)
                arr[mask] = np.clip(
                    arr[mask].astype(np.int32) + SELECT_BOOST, 0, 255
                ).astype(np.uint8)
        pil_img = Image.fromarray(arr)
        self._photo = ImageTk.PhotoImage(pil_img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        H, W = arr.shape[:2]
        self._canvas.config(scrollregion=(0, 0, W, H))
        self._zoom_label.config(text=f"Zoom: {int(self._zoom*100)}%")

    def _zoom_in(self):
        self._zoom = min(self._zoom * ZOOM_STEP, 2.0)
        self._display_map()

    def _zoom_out(self):
        self._zoom = max(self._zoom / ZOOM_STEP, 0.05)
        self._display_map()

    def _on_mousewheel(self, event):
        if self._rendered is None:
            return
        self._zoom = min(self._zoom * ZOOM_STEP, 2.0) if event.delta > 0 else max(self._zoom / ZOOM_STEP, 0.05)
        self._display_map()

    def _start_pan(self, event):
        self._canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    def _get_province_at(self, canvas_x, canvas_y):
        if self._prov_arr is None:
            return None, None, None
        abs_x = self._canvas.canvasx(canvas_x)
        abs_y = self._canvas.canvasy(canvas_y)
        ox = max(0, min(int(abs_x / self._zoom), self._prov_arr.shape[1] - 1))
        oy = max(0, min(int(abs_y / self._zoom), self._prov_arr.shape[0] - 1))
        rgb = self._prov_arr[oy, ox]
        prov_hex = "x{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        state = self._prov_to_state.get(prov_hex)
        tag = self._prov_owner_map.get(prov_hex) if state else None
        return state, tag, prov_hex

    def _on_click(self, event):
        if self._rendered is None:
            return
        state, tag, prov_hex = self._get_province_at(event.x, event.y)
        
        # Vérifier si c'est une province terrestre
        if state and state in self._sea_states:
            # Province maritime - ne pas sélectionner
            self._status_label.config(text=f"Province maritime ignorée: {prov_hex}")
            return
        
        if self._mode == MODE_STATE:
            if not state or not tag:
                return
            if self._paint_mode_var.get():
                new_tag = self._new_tag.get().strip().upper()
                if new_tag and len(new_tag) >= 2:
                    old_tag = tag
                    if old_tag != new_tag:
                        self._modified_states.add(state)
                        provs = self._substates.pop((state, old_tag), set())
                        for p in provs:
                            self._prov_owner_map[p] = new_tag
                        self._substates.setdefault((state, new_tag), set()).update(provs)
                        self._selected = {(state, new_tag)}
                        self._fast_update_provinces(provs, new_tag)
                        self._display_map()
                        self._status_label.config(text=f"Peint. {state} [{old_tag}] -> {new_tag}")
                    return
            self._selected.clear()
            self._prov_selected.clear()
            self._selected.add((state, tag))
        else:
            if not prov_hex or not state:
                return
            if self._paint_mode_var.get():
                new_tag = self._new_tag.get().strip().upper()
                if new_tag and len(new_tag) >= 2:
                    old_tag = self._prov_owner_map.get(prov_hex)
                    if old_tag != new_tag:
                        self._modified_states.add(state)
                        self._prov_owner_map[prov_hex] = new_tag
                        if (state, old_tag) in self._substates:
                            self._substates[(state, old_tag)].discard(prov_hex)
                        self._substates.setdefault((state, new_tag), set()).add(prov_hex)
                        self._fast_update_provinces({prov_hex}, new_tag)
                        self._display_map()
                        self._status_label.config(text=f"Peint. {prov_hex} -> {new_tag}")
                    return
            self._selected.clear()
            self._prov_selected.clear()
            self._prov_selected.add(prov_hex)
        self._refresh_ui(state, tag, prov_hex)

    def _on_ctrl_click(self, event):
        if self._rendered is None:
            return
        state, tag, prov_hex = self._get_province_at(event.x, event.y)
        
        # Vérifier si c'est une province terrestre
        if state and state in self._sea_states:
            # Province maritime - ne pas sélectionner
            self._status_label.config(text=f"Province maritime ignorée: {prov_hex}")
            return
        
        if self._mode == MODE_STATE:
            if state and tag:
                key = (state, tag)
                if key in self._selected:
                    self._selected.discard(key)
                else:
                    self._selected.add(key)
        else:
            if prov_hex:
                if prov_hex in self._prov_selected:
                    self._prov_selected.discard(prov_hex)
                else:
                    self._prov_selected.add(prov_hex)
        self._refresh_ui(state, tag, prov_hex)

    def _on_click_start(self, event):
        """Début de la sélection par rectangle."""
        if self._rendered is None:
            return
        
        # Si on est en mode peinture, on utilise l'ancien comportement
        if self._paint_mode_var.get():
            self._on_click(event)
            return
        
        # Sinon, on démarre une sélection par rectangle
        self._selection_rect_start = (event.x, event.y)
        self._selection_rect_end = (event.x, event.y)
        
        # Créer un rectangle de sélection
        if self._selection_rect_id:
            self._canvas.delete(self._selection_rect_id)
        
        self._selection_rect_id = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#cba6f7", width=2, dash=(4, 2)
        )

    def _on_click_drag(self, event):
        """Déplacement pendant la sélection par rectangle."""
        if self._selection_rect_start is None or self._selection_rect_id is None:
            return
        
        self._selection_rect_end = (event.x, event.y)
        
        # Mettre à jour le rectangle
        x1, y1 = self._selection_rect_start
        x2, y2 = self._selection_rect_end
        self._canvas.coords(self._selection_rect_id, x1, y1, x2, y2)

    def _on_click_release(self, event):
        """Fin de la sélection par rectangle."""
        if self._selection_rect_start is None or self._selection_rect_id is None:
            return
        
        # Supprimer le rectangle
        self._canvas.delete(self._selection_rect_id)
        self._selection_rect_id = None
        
        # Récupérer les coordonnées du rectangle
        x1, y1 = self._selection_rect_start
        x2, y2 = self._selection_rect_end
        
        # Normaliser les coordonnées
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        
        # Vérifier si c'est un clic simple (rectangle trop petit)
        if abs(right - left) < 5 and abs(bottom - top) < 5:
            # Clic simple - utiliser l'ancien comportement
            self._on_click(event)
        else:
            # Sélection par rectangle
            self._select_by_rectangle(left, top, right, bottom)
        
        self._selection_rect_start = None
        self._selection_rect_end = None

    def _select_by_rectangle(self, left, top, right, bottom):
        """Sélectionne toutes les provinces terrestres dans le rectangle."""
        if self._rendered is None or self._prov_arr is None:
            return
        
        # Convertir les coordonnées canvas en coordonnées image
        abs_left = self._canvas.canvasx(left)
        abs_top = self._canvas.canvasy(top)
        abs_right = self._canvas.canvasx(right)
        abs_bottom = self._canvas.canvasy(bottom)
        
        # Convertir en coordonnées image (en tenant compte du zoom)
        ox1 = max(0, min(int(abs_left / self._zoom), self._prov_arr.shape[1] - 1))
        oy1 = max(0, min(int(abs_top / self._zoom), self._prov_arr.shape[0] - 1))
        ox2 = max(0, min(int(abs_right / self._zoom), self._prov_arr.shape[1] - 1))
        oy2 = max(0, min(int(abs_bottom / self._zoom), self._prov_arr.shape[0] - 1))
        
        # S'assurer que ox1 <= ox2 et oy1 <= oy2
        if ox1 > ox2:
            ox1, ox2 = ox2, ox1
        if oy1 > oy2:
            oy1, oy2 = oy2, oy1
        
        # Collecter toutes les provinces uniques dans le rectangle
        selected_provs = set()
        selected_states = set()
        
        for y in range(oy1, oy2 + 1):
            for x in range(ox1, ox2 + 1):
                rgb = self._prov_arr[y, x]
                prov_hex = "x{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
                state = self._prov_to_state.get(prov_hex)
                
                # Vérifier si c'est une province terrestre
                if state and state not in self._sea_states:
                    if self._mode == MODE_PROVINCE:
                        selected_provs.add(prov_hex)
                    elif self._mode == MODE_STATE:
                        tag = self._prov_owner_map.get(prov_hex)
                        if tag:
                            selected_states.add((state, tag))
        
        # Mettre à jour la sélection
        if self._mode == MODE_PROVINCE:
            self._prov_selected.update(selected_provs)
        elif self._mode == MODE_STATE:
            self._selected.update(selected_states)
        
        # Rafraîchir l'interface
        if selected_provs or selected_states:
            self._refresh_ui()
            self._status_label.config(
                text=f"Sélection par rectangle: {len(selected_provs) if self._mode == MODE_PROVINCE else len(selected_states)} éléments"
            )

    def _on_right_click(self, event):
        if self._rendered is None:
            return
        state, tag, prov_hex = self._get_province_at(event.x, event.y)
        if tag:
            self._new_tag.set(tag)
            self._paint_status.config(text=f"Peint. {tag}")
            self._paint_mode_var.set(True)
            self.winfo_toplevel().config(cursor="crosshair")
            self._status_label.config(text=f"TAG recupere: {tag} -- Switch actif -> Clic g. pour peindre")
        elif prov_hex:
            self._status_label.config(text=f"{prov_hex} n'a pas de pays")

    def _refresh_ui(self, last_state=None, last_tag=None, last_prov=None):
        self._sel_listbox.delete(0, "end")
        if self._mode == MODE_STATE:
            for (state, tag) in sorted(self._selected):
                n_prov = len(self._substates.get((state, tag), set()))
                split = len([k for k in self._substates if k[0] == state]) > 1
                self._sel_listbox.insert("end", f"{state} {'[SPLIT]' if split else ''}  [{tag}]  ({n_prov}p)")
        else:
            for prov in sorted(self._prov_selected):
                tag = self._prov_owner_map.get(prov, "?")
                state = self._prov_to_state.get(prov, "?")
                self._sel_listbox.insert("end", f"{prov}  [{tag}]  ({state})")
        if last_state:
            split_info = ""
            if self._mode == MODE_STATE:
                all_parts = [(k, len(v)) for k, v in self._substates.items() if k[0] == last_state]
                if len(all_parts) > 1:
                    parts_str = "  |  ".join(f"{t}({n}p)" for (_, t), n in all_parts)
                    split_info = f"\nSPLIT: {parts_str}"
            self._info_label.config(
                text=f"Province : {last_prov}\nEtat     : {last_state}\nPays     : {last_tag or '?'}{split_info}"
            )
            self._refresh_hc_ui(last_state)
        elif last_prov:
            tag = self._prov_owner_map.get(last_prov, "?")
            state = self._prov_to_state.get(last_prov, "?")
            self._info_label.config(text=f"Province : {last_prov}\nEtat     : {state}\nPays     : {tag}")
        self._display_map()

    def _clear_selection(self):
        self._selected.clear()
        self._prov_selected.clear()
        self._sel_listbox.delete(0, "end")
        self._info_label.config(text="-")
        self._refresh_hc_ui(None)
        self._display_map()

    def _refresh_hc_ui(self, state_name):
        for w in self._hl_labels_frame.winfo_children():
            w.destroy()
        for w in self._cl_labels_frame.winfo_children():
            w.destroy()
        if not state_name:
            return
        data = self._state_hc.get(state_name, {})
        homelands = data.get('homelands', [])
        claims = data.get('claims', [])
        for hl in homelands:
            self._make_hc_label(self._hl_labels_frame, hl, lambda x=hl: self._remove_hc("homeland", x))
        for cl in claims:
            self._make_hc_label(self._cl_labels_frame, cl, lambda x=cl: self._remove_hc("claim", x))

    def _make_hc_label(self, parent, text, remove_cmd):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=text, font=("Consolas", 8)).pack(side="left")
        ttk.Button(row, text="X", width=2, command=remove_cmd).pack(side="right")

    def _remove_hc(self, kind, value):
        state = self._get_selected_state()
        if not state:
            return
        key = 'homelands' if kind == 'homeland' else 'claims'
        data = self._state_hc.setdefault(state, {'homelands': [], 'claims': []})
        if value in data[key]:
            data[key].remove(value)
        self._refresh_hc_ui(state)

    def _on_hl_keyrelease(self, event):
        value = self._hl_var.get().lower()
        self._hl_listbox.delete(0, 'end')
        if value:
            matches = [c for c in self._cultures if c.lower().startswith(value)]
            for m in matches[:20]:
                self._hl_listbox.insert('end', m)
            if matches:
                self._hl_listbox_frame.pack(fill='x', expand=True)
        else:
            self._hl_listbox_frame.pack_forget()

    def _on_hl_select(self, event):
        sel = self._hl_listbox.curselection()
        if sel:
            self._hl_var.set(self._hl_listbox.get(sel[0]))
            self._hl_listbox_frame.pack_forget()

    def _init_hl_combo(self):
        self._hl_listbox.delete(0, 'end')
        for c in self._cultures[:20]:
            self._hl_listbox.insert('end', c)

    def _add_hc(self, kind):
        state = self._get_selected_state()
        if not state:
            messagebox.showwarning("Attention", "Selectionne d'abord un etat")
            return
        if kind == 'homeland':
            value = self._hl_var.get().strip()
            self._hl_var.set("")
        else:
            value = self._cl_entry.get().strip().upper()
            self._cl_entry.set("")
        if not value:
            return
        key = 'homelands' if kind == 'homeland' else 'claims'
        data = self._state_hc.setdefault(state, {'homelands': [], 'claims': []})
        if value not in data[key]:
            data[key].append(value)
        self._refresh_hc_ui(state)

    def _get_selected_state(self):
        if self._selected:
            return next(iter(self._selected))[0]
        if self._prov_selected:
            p = next(iter(self._prov_selected))
            return self._prov_to_state.get(p)
        return None

    def _save_hc(self):
        state = self._get_selected_state()
        if not state:
            messagebox.showwarning("Attention", "Selectionne d'abord un etat")
            return
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return
        states_path = os.path.join(mod, "common/history/states/00_states.txt")
        if not os.path.exists(states_path):
            messagebox.showerror("Erreur", f"Fichier introuvable:\n{states_path}")
            return
        _bkdir = os.path.join(os.path.dirname(states_path), "_backup")
        os.makedirs(_bkdir, exist_ok=True)
        shutil.copy(states_path, os.path.join(_bkdir, os.path.basename(states_path)))
        self._update_hc_in_file(states_path, state)
        self._hl_var.set("")
        self._cl_entry.set("")
        messagebox.showinfo("Sauvegarde", f"Homeland/Claim sauvegardes pour {state}")

    def _update_hc_in_file(self, states_path, state_name):
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        state_pat = re.compile(rf's:{re.escape(state_name)}\s*=\s*\{{')
        sm = state_pat.search(content)
        if not sm:
            messagebox.showerror("Erreur", f"Etat {state_name} non trouve dans le fichier")
            return
        block_start = sm.end()
        before = content[:sm.start()]
        last_nl = before.rfind('\n')
        indent = before[last_nl + 1:] if last_nl >= 0 else ''
        depth, i = 1, block_start
        while i < len(content) and depth > 0:
            if content[i] == '{': depth += 1
            elif content[i] == '}': depth -= 1
            i += 1
        block_end = i - 1
        old_block = content[block_start:block_end]
        cleaned = re.sub(r'\s*add_homeland\s*=\s*cu:\w+\s*', '', old_block)
        cleaned = re.sub(r'\s*add_claim\s*=\s*c:\w+\s*', '', cleaned)
        cleaned = cleaned.rstrip()
        data = self._state_hc.get(state_name, {'homelands': [], 'claims': []})
        new_lines = []
        for hl in data.get('homelands', []):
            new_lines.append(f"{indent}    add_homeland = cu:{hl}")
        for cl in data.get('claims', []):
            new_lines.append(f"{indent}    add_claim = c:{cl}")
        new_block = cleaned
        if new_lines:
            new_block = cleaned + '\n' + '\n'.join(new_lines)
        new_content = content[:sm.start()] + f"s:{state_name} = {{\n" + new_block + '\n' + indent + '}' + content[i:]
        with open(states_path, "w", encoding="utf-8-sig") as fh:
            fh.write(new_content)

    def _transfer(self):
        new_tag = self._new_tag.get().strip().upper()
        if not new_tag or len(new_tag) < 2:
            messagebox.showerror("Erreur", "Entre un TAG valide")
            return
        if self._mode == MODE_STATE:
            self._transfer_states(new_tag)
        else:
            self._transfer_provinces(new_tag)

    def _transfer_states(self, new_tag):
        if not self._selected:
            messagebox.showwarning("Attention", "Selectionne d'abord des sous-etats")
            return
        all_moved_provs = set()
        for (state, old_tag) in list(self._selected):
            self._modified_states.add(state)
            provs = self._substates.pop((state, old_tag), set())
            for prov_hex in provs:
                self._prov_owner_map[prov_hex] = new_tag
            self._substates.setdefault((state, new_tag), set()).update(provs)
            all_moved_provs.update(provs)
        self._fast_update_provinces(all_moved_provs, new_tag)
        self._selected = {(state, new_tag) for (state, _) in self._selected}
        self._refresh_ui()
        self._save_status.config(text=f"{len(self._selected)} sous-etat(s) modifie(s) (non sauvegarde)")

    def _transfer_provinces(self, new_tag):
        if not self._prov_selected:
            messagebox.showwarning("Attention", "Selectionne d'abord des provinces")
            return
        painted = 0
        # D'abord, collecter tous les états et anciens tags affectés
        affected_states = set()
        old_tags_by_state = {}
        
        for prov_hex in list(self._prov_selected):
            old_tag = self._prov_owner_map.get(prov_hex)
            state = self._prov_to_state.get(prov_hex)
            if not state or not old_tag:
                continue
            affected_states.add(state)
            if state not in old_tags_by_state:
                old_tags_by_state[state] = set()
            old_tags_by_state[state].add(old_tag)
        
        # Transférer chaque province
        for prov_hex in list(self._prov_selected):
            old_tag = self._prov_owner_map.get(prov_hex)
            state = self._prov_to_state.get(prov_hex)
            if not state or not old_tag:
                continue
            self._modified_states.add(state)
            self._prov_owner_map[prov_hex] = new_tag
            if (state, old_tag) in self._substates:
                self._substates[(state, old_tag)].discard(prov_hex)
            self._substates.setdefault((state, new_tag), set()).add(prov_hex)
            painted += 1
        
        # Nettoyer les entrées vides dans self._substates
        for state in affected_states:
            for old_tag in old_tags_by_state.get(state, set()):
                key = (state, old_tag)
                if key in self._substates and not self._substates[key]:
                    del self._substates[key]
        
        self._prov_selected.clear()
        self._refresh_render()
        self._save_status.config(text=f"{painted} province(s) modifiee(s) (non sauvegarde)")
        self._status_label.config(text=f"Mode PROVINCE -- {painted} provinces transferees vers {new_tag}")

    def _save(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return
        states_path = os.path.join(mod, "common/history/states/00_states.txt")
        if not os.path.exists(states_path):
            messagebox.showerror("Erreur", f"Fichier introuvable:\n{states_path}")
            return
        n = len(self._modified_states)
        if n == 0:
            messagebox.showinfo("Sauvegarde", "Aucune modification a sauvegarder.")
            return
        states_snapshot = set(self._modified_states)
        substates_snapshot = {k: set(v) for k, v in self._substates.items()}
        _bkdir = os.path.join(os.path.dirname(states_path), "_backup")
        os.makedirs(_bkdir, exist_ok=True)
        shutil.copy(states_path, os.path.join(_bkdir, os.path.basename(states_path)))
        self._rebuild_states_file(states_path)
        try:
            updated_files = update_history_files(mod, states_snapshot, substates_snapshot)
        except Exception as e:
            import traceback
            messagebox.showerror("Erreur pops/buildings", traceback.format_exc())
            updated_files = 0
        self._save_status.config(text=f"{n} state(s) sauvegarde(s) !")
        detail = f"{n} state(s) réécrits dans 00_states.txt"
        if updated_files > 0:
            detail += f"\n{updated_files} fichier(s) pops/buildings mis à jour"
        messagebox.showinfo("Sauvegarde", detail + "\n(backups créés)")

    def _rebuild_states_file(self, states_path):
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        new_content = []
        i = 0
        while i < len(content):
            sm = re.search(r's:(STATE_\w+)\s*=\s*\{', content[i:])
            if sm:
                state_name = sm.group(1)
                start_of_state = i + sm.start()
                block_start = i + sm.end()
                depth, j = 1, block_start
                while j < len(content) and depth > 0:
                    if content[j] == "{": depth += 1
                    elif content[j] == "}": depth -= 1
                    j += 1
                if state_name in self._modified_states:
                    before = content[i:start_of_state]
                    last_nl = before.rfind('\n')
                    indent = before[last_nl + 1:] if last_nl >= 0 else ''
                    state_block = content[block_start:j - 1]
                    new_state = self._build_state_block(state_name, state_block, indent)
                    new_content.append(content[i:start_of_state])
                    new_content.append(new_state)
                else:
                    new_content.append(content[i:j])
                i = j
            else:
                new_content.append(content[i:])
                break
        with open(states_path, "w", encoding="utf-8-sig") as fh:
            fh.write("".join(new_content))
        self._modified_states.clear()

    def _build_state_block(self, state_name, original_block, indent=""):
        rest_of_block = original_block
        for cs_match in reversed(list(re.finditer(r'create_state\s*=\s*\{', original_block))):
            cs_end = cs_match.end()
            depth, j = 1, cs_end
            while j < len(original_block) and depth > 0:
                if original_block[j] == "{": depth += 1
                elif original_block[j] == "}": depth -= 1
                j += 1
            rest_of_block = rest_of_block[:cs_match.start()] + rest_of_block[j:]
        other_content = rest_of_block.strip()
        lines = [f"s:{state_name} = {{"]
        new_create_states = {}
        for (state, tag), provs in self._substates.items():
            if state == state_name and provs:
                new_create_states.setdefault(tag, set()).update(provs)
        for tag in sorted(new_create_states.keys()):
            provs = sorted(new_create_states[tag])
            provs_str = " ".join(provs)
            lines.append(f"{indent}    create_state = {{")
            lines.append(f"{indent}        country = c:{tag}")
            lines.append(f"{indent}        owned_provinces = {{ {provs_str} }}")
            lines.append(f"{indent}    }}")
        if other_content:
            for line in other_content.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(f"{indent}    {stripped}")
                else:
                    lines.append("")
        lines.append(f"{indent}}}")
        return "\n".join(lines)

    def _open_new_country_popup(self):
            import random
            state = self._get_selected_state()
            if not state:
                messagebox.showwarning("Attention", "Selectionne d'abord un etat pour la capitale")
                return

            popup = tk.Toplevel(self.winfo_toplevel())
            popup.title("Nouveau pays")
            popup.geometry("380x540")
            popup.configure(bg="#1e2030")
            popup.grab_set()

            # Style pour le popup
            style = ttk.Style(popup)
            style.theme_use('clam')

            # Variables
            tag_var = tk.StringVar()
            name_var = tk.StringVar()
            capital_var = tk.StringVar(value=state)
            color_var = tk.StringVar(value="120 80 180")
            country_type_var = tk.StringVar(value="recognized")
            tier_var = tk.StringVar(value="kingdom")
            religion_var = tk.StringVar()
            cultures_var = tk.StringVar()
            culture_labels = []
            religion_labels = []

            # ============ TITRE ============
            title_lbl = tk.Label(popup, text="Nouveau pays", font=("Segoe UI", 14, "bold"), bg="#1e2030", fg="#cba6f7")
            title_lbl.pack(pady=(15, 10))

            # Container frame
            cont = tk.Frame(popup, bg="#1e2030")
            cont.pack(fill="both", expand=True, padx=15)

            # ============ LIGNE 1: TAG + Auto ============
            row = 0
            tk.Label(cont, text="TAG:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            tag_entry = ttk.Entry(cont, textvariable=tag_var, width=10, font=("Consolas", 10))
            tag_entry.grid(row=row, column=1, sticky="w", pady=6)
            ttk.Button(cont, text="Auto", width=6, command=lambda: self._auto_gen_tag(tag_var)).grid(row=row, column=2, padx=(5, 0), pady=6)

            # ============ LIGNE 2: Nom ============
            row += 1
            tk.Label(cont, text="Nom:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            tk.Entry(cont, textvariable=name_var, width=28, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9)).grid(row=row, column=1, columnspan=2, sticky="w", pady=6)

            # ============ LIGNE 3: Capital ============
            row += 1
            tk.Label(cont, text="Capital:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            tk.Entry(cont, textvariable=capital_var, width=20, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9)).grid(row=row, column=1, columnspan=2, sticky="w", pady=6)

            # ============ LIGNE 4: Couleur + Aleatoire ============
            row += 1
            tk.Label(cont, text="Couleur:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            color_frame = tk.Frame(cont, bg="#1e2030")
            color_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
            tk.Entry(color_frame, textvariable=color_var, width=10, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9)).pack(side="left")
            ttk.Button(color_frame, text="Aleatoire", command=lambda: self._rand_color(color_var)).pack(side="left", padx=5)

            # ============ LIGNE 5: Country Type ============
            row += 1
            tk.Label(cont, text="Type:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            type_combo = ttk.Combobox(cont, textvariable=country_type_var, values=["recognized", "unrecognized", "colonial", "decentralized"], width=18, state="readonly")
            type_combo.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)

            # ============ LIGNE 6: Tier ============
            row += 1
            tk.Label(cont, text="Tier:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            tier_combo = ttk.Combobox(cont, textvariable=tier_var, values=["empire", "hegemony", "kingdom", "grand_principality", "principality", "city_state"], width=18, state="readonly")
            tier_combo.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)

            # ============ LIGNE 7: Religion ============
            row += 1
            tk.Label(cont, text="Religion:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=6)
            rel_frame = tk.Frame(cont, bg="#1e2030")
            rel_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
            rel_entry = tk.Entry(rel_frame, textvariable=religion_var, width=14, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9))
            rel_entry.pack(side="left")
            rel_entry.bind("<KeyRelease>", lambda e: self._filter_popup(e, self._religions, rel_listbox, religion_var, rel_lb_frame))
            tk.Button(rel_frame, text="+", bg="#45475a", fg="#cdd6f4", width=3, command=lambda: self._add_to_list(religion_var, religion_labels, rel_labels_frame)).pack(side="left", padx=2)
            rel_lb_frame = tk.Frame(cont, bg="#1e2030")
            rel_lb_frame.grid(row=row+1, column=1, columnspan=2, sticky="w", padx=0)
            rel_lb_frame.grid_remove()
            rel_listbox = tk.Listbox(rel_lb_frame, height=4, bg="#313244", fg="#cdd6f4", font=("Consolas", 8), selectbackground="#585b70")
            rel_listbox.pack(side="left")
            rel_listbox.bind("<<ListboxSelect>>", lambda e: self._on_popup_sel(e, rel_listbox, religion_var, rel_lb_frame))
            rel_labels_frame = tk.Frame(cont, bg="#1e2030")
            rel_labels_frame.grid(row=row+2, column=1, columnspan=2, sticky="w", pady=2)

            # ============ LIGNE 8: Cultures ============
            row += 3
            tk.Label(cont, text="Cultures:", bg="#1e2030", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="nw", pady=6)
            cult_frame = tk.Frame(cont, bg="#1e2030")
            cult_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
            cult_entry = tk.Entry(cult_frame, textvariable=cultures_var, width=14, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9))
            cult_entry.pack(side="left")
            cult_entry.bind("<KeyRelease>", lambda e: self._filter_popup(e, self._cultures, cult_listbox, cultures_var, cult_lb_frame))
            tk.Button(cult_frame, text="+", bg="#45475a", fg="#cdd6f4", width=3, command=lambda: self._add_to_list(cultures_var, culture_labels, cult_labels_frame)).pack(side="left", padx=2)
            cult_lb_frame = tk.Frame(cont, bg="#1e2030")
            cult_lb_frame.grid(row=row+1, column=1, columnspan=2, sticky="w", padx=0)
            cult_lb_frame.grid_remove()
            cult_listbox = tk.Listbox(cult_lb_frame, height=4, bg="#313244", fg="#cdd6f4", font=("Consolas", 8), selectbackground="#585b70")
            cult_listbox.pack(side="left")
            cult_listbox.bind("<<ListboxSelect>>", lambda e: self._on_popup_sel(e, cult_listbox, cultures_var, cult_lb_frame))
            cult_labels_frame = tk.Frame(cont, bg="#1e2030")
            cult_labels_frame.grid(row=row+2, column=1, columnspan=2, sticky="w", pady=2)

            # Status label
            status_lbl = tk.Label(popup, text="", bg="#1e2030", fg="#f38ba8", font=("Segoe UI", 8))
            status_lbl.pack(pady=5)

            def _create_country():
                tag = tag_var.get().strip().upper()
                name = name_var.get().strip()
                capital = capital_var.get().strip()
                color = color_var.get().strip()
                ctype = country_type_var.get()
                tier = tier_var.get()
                religion = religion_labels[0] if religion_labels else (religion_var.get().strip() if religion_var.get().strip() else "")
                cultures = culture_labels.copy()

                if len(tag) < 2:
                    status_lbl.config(text="TAG doit avoir au moins 2 caracteres")
                    return
                if not capital:
                    status_lbl.config(text="Capital requise")
                    return
                if not cultures:
                    status_lbl.config(text="Ajoute au moins une culture")
                    return

                mod = self.config.mod_path
                if not mod:
                    status_lbl.config(text="Configure le dossier mod d'abord (Config)")
                    return

                # Creer country definitions
                def_dir = os.path.join(mod, "common", "country_definitions")
                os.makedirs(def_dir, exist_ok=True)
                def_file = os.path.join(def_dir, "99_hmm_countries.txt")

                # Verifier si TAG existe deja
                if os.path.exists(def_file):
                    with open(def_file, "r", encoding="utf-8-sig") as f:
                        if re.search(rf'^{re.escape(tag)}\s*=', f.read(), re.MULTILINE):
                            status_lbl.config(text=f"TAG {tag} existe deja")
                            return

                # Construire le block pays
                country_block = f"{tag} = {{\n"
                country_block += f"    color = {{ {color} }}\n"
                country_block += f"    country_type = {ctype}\n"
                country_block += f"    tier = {tier}\n"
                country_block += f"    cultures = {{ {' '.join(cultures)} }}\n"
                country_block += f"    capital = {capital}\n"
                if religion:
                    country_block += f"    religion = {religion}\n"
                country_block += f"}}\n"

                # Ecrire au top du fichier
                if os.path.exists(def_file):
                    with open(def_file, "r", encoding="utf-8-sig") as f:
                        old_content = f.read()
                    new_content = country_block + old_content
                else:
                    new_content = country_block

                with open(def_file, "w", encoding="utf-8-sig") as f:
                    f.write(new_content)

                # Localisation
                if name:
                    loc_dir = os.path.join(mod, "localization", "english")
                    os.makedirs(loc_dir, exist_ok=True)
                    loc_file = os.path.join(loc_dir, "00_hmm_countries_l_english.yml")

                    loc_entry = f"{tag}:0 \"{name}\"\n{tag}_ADJ:0 \"{name}\"\n\n"

                    if os.path.exists(loc_file):
                        with open(loc_file, "r", encoding="utf-8-sig") as f:
                            content = f.read()
                        if content.startswith("l_english:"):
                            content = content.split("\n", 1)[1]
                        new_loc = "l_english:\n\n" + loc_entry + content
                    else:
                        new_loc = "l_english:\n\n" + loc_entry

                    with open(loc_file, "w", encoding="utf-8-sig") as f:
                        f.write(new_loc)

                # Ajouter couleur au cache
                color_parts = color.split()
                if len(color_parts) == 3:
                    self._country_colors[tag] = (int(color_parts[0]), int(color_parts[1]), int(color_parts[2]))

                # Sauvegarder les derniers paramètres (sauf TAG et nom)
                self._last_country_params = {
                    'color': color,
                    'country_type': ctype,
                    'tier': tier,
                    'religion': religion,
                    'cultures': cultures.copy(),
                    'capital': capital
                }

                self._new_tag.set(tag)
                self._display_map()
                popup.destroy()
                messagebox.showinfo("Succes", f"Pays {tag} cree avec succes !")

            def _load_last_params():
                """Charge les derniers paramètres dans les champs (sauf TAG et nom)."""
                color_var.set(self._last_country_params['color'])
                country_type_var.set(self._last_country_params['country_type'])
                tier_var.set(self._last_country_params['tier'])
                
                # Réinitialiser les labels de religion et cultures
                for w in rel_labels_frame.winfo_children():
                    w.destroy()
                for w in cult_labels_frame.winfo_children():
                    w.destroy()
                
                religion_labels.clear()
                culture_labels.clear()
                
                # Charger la religion
                rel = self._last_country_params['religion']
                if rel:
                    religion_var.set(rel)
                    religion_labels.append(rel)
                    lbl = ttk.Label(rel_labels_frame, text=rel, font=("Consolas", 8))
                    lbl.pack(side="left", padx=2)
                
                # Charger les cultures
                for cult in self._last_country_params['cultures']:
                    culture_labels.append(cult)
                    lbl = ttk.Label(cult_labels_frame, text=cult, font=("Consolas", 8))
                    lbl.pack(side="left", padx=2)
                
                # Charger la capitale si vide
                if not capital_var.get().strip():
                    capital_var.set(self._last_country_params['capital'])
                
                status_lbl.config(text="Derniers paramètres chargés (sauf TAG et nom)")

            # Boutons
            btn_frame = tk.Frame(popup, bg="#1e2030")
            btn_frame.pack(pady=15)
            tk.Button(btn_frame, text="Creer le pays", bg="#45475a", fg="#cdd6f4", font=("Segoe UI", 10, "bold"), width=14, height=1, command=_create_country).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Reprendre derniers", bg="#585b70", fg="#cdd6f4", font=("Segoe UI", 9), width=14, height=1, command=_load_last_params).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Annuler", bg="#45475a", fg="#cdd6f4", font=("Segoe UI", 10), width=10, height=1, command=popup.destroy).pack(side="left", padx=5)

    def _auto_gen_tag(self, tag_var):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return
        def_dir = os.path.join(mod, "common", "country_definitions")
        os.makedirs(def_dir, exist_ok=True)
        tag = find_next_tag(def_dir)
        tag_var.set(tag)

    def _rand_color(self, color_var):
        import random
        r = random.randint(40, 220)
        g = random.randint(40, 220)
        b = random.randint(40, 220)
        color_var.set(f"{r} {g} {b}")

    def _filter_popup(self, event, data_list, listbox, var, frame):
        value = var.get().lower()
        listbox.delete(0, 'end')
        if value:
            matches = [c for c in data_list if c.lower().startswith(value)]
            for m in matches[:15]:
                listbox.insert('end', m)
            if matches:
                frame.grid()
        else:
            frame.grid_remove()

    def _on_popup_sel(self, event, listbox, var, frame):
        sel = listbox.curselection()
        if sel:
            var.set(listbox.get(sel[0]))
            frame.grid_remove()

    def _add_to_list(self, entry_var, labels_list, parent_frame):
        value = entry_var.get().strip()
        if not value:
            return
        if value not in labels_list:
            labels_list.append(value)
            entry_var.set("")
            # Afficher le label
            lbl = ttk.Label(parent_frame, text=value, font=("Consolas", 8))
            lbl.pack(side="left", padx=2)

    # ============================================================
    # STATE CHECK - Méthodes pour le screening des provinces
    # ============================================================

    def _run_state_screening(self):
        """Lance le screening des provinces avec analyse détaillée."""
        mod = self.config.mod_path
        if not mod:
            self._sc_status.config(text="Erreur: Configure le dossier mod", foreground="#f38ba8")
            return
        
        # Chemins
        states_path = os.path.join(mod, "common/history/states/00_states.txt")
        sr_dir = self._get_state_regions_dir()
        
        if not os.path.exists(states_path):
            self._sc_status.config(text=f"Erreur: 00_states.txt introuvable", foreground="#f38ba8")
            return
        if not sr_dir or not os.path.exists(sr_dir):
            self._sc_status.config(text=f"Erreur: state_regions introuvable", foreground="#f38ba8")
            return
        
        self._sc_button.config(state="disabled")
        self._sc_results_listbox.delete(0, "end")
        self._sc_status.config(text="Analyse en cours...", foreground="#89b4fa")
        self._sc_stats_label.config(text="")
        
        # Parser 00_states.txt
        states_provinces = self._parse_states_provinces(states_path)
        
        # Parser state_regions - créer une map province -> état
        sr_provinces = self._parse_state_regions_provinces(sr_dir)
        
        # Créer une map {province: état} pour toutes les provinces dans state_regions
        prov_to_state_map = {}
        for state_name, provs in sr_provinces.items():
            for p in provs:
                prov_to_state_map[p] = state_name
        
        # Analyser chaque province dans 00_states.txt
        provinces_to_move = {}  # {state_name: {correct_state: [provinces]}}
        provinces_to_add = {}   # {state_name: [provinces]}
        missing_states = set()  # États dans 00_states.txt qui n'existent pas dans state_regions
        
        total_checked = 0
        
        for state_name, provs in states_provinces.items():
            total_checked += 1
            
            # Vérifier si l'état existe dans state_regions
            if state_name not in sr_provinces:
                missing_states.add(state_name)
                continue
            
            for p in provs:
                if p in prov_to_state_map:
                    # Province existe dans state_regions, mais dans quel état ?
                    correct_state = prov_to_state_map[p]
                    if correct_state != state_name:
                        # Mauvais état - déplacer dans 00_states.txt
                        if state_name not in provinces_to_move:
                            provinces_to_move[state_name] = {}
                        if correct_state not in provinces_to_move[state_name]:
                            provinces_to_move[state_name][correct_state] = []
                        provinces_to_move[state_name][correct_state].append(p)
                else:
                    # Province orpheline - n'existe dans aucun état de state_regions
                    if state_name not in provinces_to_add:
                        provinces_to_add[state_name] = []
                    provinces_to_add[state_name].append(p)
        
        # Afficher les résultats
        total_to_move = sum(len(provs) for states in provinces_to_move.values() for provs in states.values())
        total_to_add = sum(len(provs) for provs in provinces_to_add.values())
        
        self._sc_results_listbox.insert("end", "=== RESULTATS ===")
        self._sc_results_listbox.insert("end", f"Etats analises: {total_checked}")
        
        # Catégorie 1 : Provinces à déplacer (mauvais état)
        self._sc_results_listbox.insert("end", f"=== A DEPLACER ({total_to_move}) ===")
        if provinces_to_move:
            for wrong_state in sorted(provinces_to_move.keys()):
                for correct_state in sorted(provinces_to_move[wrong_state].keys()):
                    provs = provinces_to_move[wrong_state][correct_state]
                    self._sc_results_listbox.insert("end", f"  {wrong_state} -> {correct_state}: {len(provs)} p")
                    for p in sorted(provs)[:5]:
                        self._sc_results_listbox.insert("end", f"    - {p}")
                    if len(provs) > 5:
                        self._sc_results_listbox.insert("end", f"    ... et {len(provs)-5} autres")
        else:
            self._sc_results_listbox.insert("end", "  (Aucune)")
        
        self._sc_results_listbox.insert("end", "")
        
        # Catégorie 2 : Provinces à ajouter (orphelines)
        self._sc_results_listbox.insert("end", f"=== A AJOUTER ({total_to_add}) ===")
        if provinces_to_add:
            for state_name in sorted(provinces_to_add.keys()):
                provs = provinces_to_add[state_name]
                self._sc_results_listbox.insert("end", f"  {state_name}: {len(provs)} p")
                for p in sorted(provs)[:5]:
                    self._sc_results_listbox.insert("end", f"    + {p}")
                if len(provs) > 5:
                    self._sc_results_listbox.insert("end", f"    ... et {len(provs)-5} autres")
        else:
            self._sc_results_listbox.insert("end", "  (Aucune)")
        
        self._sc_results_listbox.insert("end", "")
        
        # Catégorie 3 : États manquants
        self._sc_results_listbox.insert("end", f"=== MANQUANTS ({len(missing_states)}) ===")
        if missing_states:
            for s in sorted(missing_states)[:10]:
                self._sc_results_listbox.insert("end", f"  ! {s}")
            if len(missing_states) > 10:
                self._sc_results_listbox.insert("end", f"  ... et {len(missing_states)-10} autres")
        else:
            self._sc_results_listbox.insert("end", "  (Aucun)")
        
        # Stocker les résultats pour les corrections
        self._sc_missing_provinces = provinces_to_move
        self._sc_orphelines = provinces_to_add
        self._sc_missing_states = missing_states
        
        # Mettre à jour le statut
        if total_to_move > 0 or total_to_add > 0:
            self._sc_apply_button.config(state="normal")
            self._sc_status.config(text=f" Pret: {total_to_move} dep, {total_to_add} aj", foreground="#f9e2af")
        else:
            self._sc_apply_button.config(state="disabled")
            if len(missing_states) > 0:
                self._sc_status.config(text=f"Termine - {len(missing_states)} etat(s) manquants", foreground="#f9e2af")
            else:
                self._sc_status.config(text="Analyse terminee - Tout est OK !", foreground="#a6e3a1")
        
        self._sc_stats_label.config(text=f"Dep: {total_to_move} | Aj: {total_to_add} | Manq: {len(missing_states)}")
        self._sc_button.config(state="normal")

    def _parse_states_provinces(self, states_path):
        """Parse 00_states.txt et retourne un dict {state_name: set_of_provinces}."""
        result = {}
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        
        prov_pat = re.compile(r'x[0-9A-Fa-f]{6}')
        for sm in re.finditer(r's:(STATE_\w+)\s*=\s*\{', content):
            state = sm.group(1)
            start = sm.end()
            depth, i = 1, start
            while i < len(content) and depth > 0:
                if content[i] == "{": depth += 1
                elif content[i] == "}": depth -= 1
                i += 1
            state_block = content[start:i - 1]
            
            provs = set()
            for pm in prov_pat.finditer(state_block):
                p = "x" + pm.group(0)[1:].upper()
                provs.add(p)
            
            if provs:
                result[state] = provs
        
        return result

    def _parse_state_regions_provinces(self, sr_dir):
        """Parse les fichiers state_regions et retourne un dict {state_name: set_of_provinces}."""
        result = {}
        # Regex pour les deux formats : "x123456" ou x123456
        prov_pat = re.compile(r'"?x[0-9A-Fa-f]{6}"?')
        state_pat = re.compile(r'^(STATE_\w+)\s*=\s*\{', re.MULTILINE)
        
        for fname in sorted(os.listdir(sr_dir)):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(sr_dir, fname), "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            
            for sm in state_pat.finditer(content):
                state = sm.group(1)
                start = sm.end()
                depth, i = 1, start
                while i < len(content) and depth > 0:
                    if content[i] == "{": depth += 1
                    elif content[i] == "}": depth -= 1
                    i += 1
                block = content[sm.start():i]
                provs = set()
                for pm in prov_pat.finditer(block):
                    p = pm.group(0).strip('"').upper()
                    provs.add(p)
                result[state] = provs
        
        return result

    def _apply_state_corrections(self):
        """Applique les corrections en ajoutant les provinces manquantes aux fichiers state_regions."""
        if not self._sc_missing_provinces and not self._sc_orphelines:
            return
        
        mod = self.config.mod_path
        sr_dir = self._get_state_regions_dir()
        
        if not mod or not sr_dir or not os.path.exists(sr_dir):
            self._sc_status.config(text="Erreur: Dossiers non configures", foreground="#f38ba8")
            return
        
        # Sauvegarde si cochée
        if self._sc_backup_var.get():
            backup_dir = sr_dir + "_backup"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            for fname in os.listdir(sr_dir):
                if fname.endswith(".txt"):
                    src = os.path.join(sr_dir, fname)
                    dst = os.path.join(backup_dir, fname)
                    shutil.copy2(src, dst)
            self._sc_results_listbox.insert("end", "")
            self._sc_results_listbox.insert("end", f"Sauvegarde creee: {backup_dir}")
        
        # Appliquer les corrections pour provinces_to_move
        corrections_made = 0
        
        for state_name, data in self._sc_missing_provinces.items():
            for correct_state, provs in data.items():
                file_path = self._find_state_regions_file(sr_dir, correct_state)
                if not file_path:
                    self._sc_results_listbox.insert("end", f"ATTENTION: {correct_state} non trouve")
                    continue
                self._add_provinces_to_state(file_path, correct_state, provs)
                corrections_made += len(provs)
        
        # Appliquer les corrections pour provinces_orphelines
        for state_name, provs in self._sc_orphelines.items():
            file_path = self._find_state_regions_file(sr_dir, state_name)
            if not file_path:
                self._sc_results_listbox.insert("end", f"ATTENTION: {state_name} non trouve")
                continue
            self._add_provinces_to_state(file_path, state_name, provs)
            corrections_made += len(provs)
        
        self._sc_status.config(text=f"Corrections appliquees: {corrections_made} p", foreground="#a6e3a1")
        self._sc_apply_button.config(state="disabled")
        
        messagebox.showinfo("State Check", f"{corrections_made} province(s) ajoutee(s) aux fichiers state_regions.\nSauvegardes creees si cochée.")

    def _find_state_regions_file(self, sr_dir, state_name):
        """Trouve le fichier state_regions qui contient l'état spécifié."""
        state_pat = re.compile(r'^(STATE_\w+)\s*=\s*\{', re.MULTILINE)
        
        for fname in sorted(os.listdir(sr_dir)):
            if not fname.endswith(".txt"):
                continue
            fpath = os.path.join(sr_dir, fname)
            with open(fpath, "r", encoding="utf-8-sig") as fh:
                content = fh.read()
            
            for sm in state_pat.finditer(content):
                if sm.group(1) == state_name:
                    return fpath
        
        return None

    def _add_provinces_to_state(self, file_path, state_name, provinces_to_add):
        """Ajoute les provinces spécifiées à un état dans le fichier state_regions."""
        with open(file_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()
        
        # Trouver le bloc de l'état
        state_pat = re.compile(rf'^{re.escape(state_name)}\s*=\s*\{{', re.MULTILINE)
        sm = state_pat.search(content)
        
        if not sm:
            return
        
        block_start = sm.end()
        depth, i = 1, block_start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1
        
        # Chercher la ligne "provinces = {"
        prov_line_match = re.search(r'provinces\s*=\s*\{', content[block_start:i])
        
        if not prov_line_match:
            return
        
        prov_line_start = block_start + prov_line_match.end()
        
        # Trouver la fin de la liste de provinces
        depth2, j = 1, prov_line_start
        while j < i and depth2 > 0:
            if content[j] == "{": depth2 += 1
            elif content[j] == "}": depth2 -= 1
            j += 1
        
        # Insérer les nouvelles provinces avant la fermeture
        existing_provs = content[prov_line_start:j-1]
        
        # Parser les provinces existantes (les deux formats: "x123456" et x123456)
        prov_pat = re.compile(r'"?x[0-9A-Fa-f]{6}"?')
        existing_set = set()
        for pm in prov_pat.finditer(existing_provs):
            p = pm.group(0).strip('"').upper()
            existing_set.add(p)
        
        # Ajouter les provinces manquantes
        new_provs = []
        for p in provinces_to_add:
            if p not in existing_set:
                new_provs.append(f'"{p}"')
        
        if new_provs:
            # Insérer les nouvelles provinces
            new_provs_str = " " + " ".join(new_provs) + " "
            new_content = content[:prov_line_start] + new_provs_str + existing_provs + content[j-1:]
            
            with open(file_path, "w", encoding="utf-8-sig") as fh:
                fh.write(new_content)
            
            self._sc_results_listbox.insert("end", f"+ {state_name}: {len(new_provs)} p ajoute(s)")
