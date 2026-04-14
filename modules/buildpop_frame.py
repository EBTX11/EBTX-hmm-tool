"""
Panel Building/Pop pour Victoria 3
- Carte avec couleurs pays + frontieres rouges
- Clic sur un etat pour le selectionner
- Selecteur de TAG pour les split states (plusieurs proprietaires)
- Editeur pops et batiments par region_state:TAG
- Sauvegarde independante pops / batiments
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
import shutil
import numpy as np
from PIL import Image, ImageTk

from modules.map_frame import (
    parse_state_regions, parse_states_file, parse_country_colors,
    _random_country_color, build_render,
    PROV_PNG, SR_DIR,
    INITIAL_ZOOM, ZOOM_STEP,
)

SELECT_BOOST = 60


# ─────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────

def _block_end(content, start):
    depth, i = 1, start
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
        i += 1
    return i


def _parse_rs_pops(rs_content):
    """Extrait [(culture, size)] depuis le contenu d'un region_state."""
    pops = []
    seen = set()
    for pm in re.finditer(r'create_pop\s*=\s*\{', rs_content):
        pe = _block_end(rs_content, pm.end())
        pop = rs_content[pm.end():pe - 1]
        cm = re.search(r'culture\s*=\s*(\w+)', pop)
        sz = re.search(r'size\s*=\s*(\d+)', pop)
        if cm and sz and cm.group(1) not in seen:
            seen.add(cm.group(1))
            pops.append((cm.group(1), int(sz.group(1))))
    # Aggreger si meme culture presente plusieurs fois
    totals = {}
    order = []
    for c, s in pops:
        if c not in totals:
            order.append(c)
            totals[c] = 0
        totals[c] += s
    return [(c, totals[c]) for c in order]


def _parse_rs_buildings(rs_content):
    """Extrait [(full_name, level)] depuis le contenu d'un region_state.
    Gere building="building_X" et levels=N (add_ownership) ou level=N (direct).
    """
    buildings = []
    seen = set()
    for bm in re.finditer(r'create_building\s*=\s*\{', rs_content):
        be = _block_end(rs_content, bm.end())
        bldg = rs_content[bm.end():be - 1]
        bn = re.search(r'building\s*=\s*"?(\w+)"?', bldg)
        if not bn:
            continue
        full_name = bn.group(1)
        if full_name in seen:
            continue
        seen.add(full_name)
        lv = re.search(r'\blevels\s*=\s*(\d+)', bldg)
        if not lv:
            lv = re.search(r'\blevel\s*=\s*(\d+)', bldg)
        level = int(lv.group(1)) if lv else 1
        buildings.append((full_name, level))
    return buildings


# ─────────────────────────────────────────────────────────────
# PARSEURS POPS / BUILDINGS  →  {state: {tag: [items]}}
# ─────────────────────────────────────────────────────────────

def parse_pops_files(pops_dir):
    """Retourne {state: {tag: [(culture, size)]}} depuis tous les fichiers."""
    result = {}
    if not os.path.isdir(pops_dir):
        return result
    for fname in sorted(os.listdir(pops_dir)):
        if not fname.endswith('.txt'):
            continue
        try:
            with open(os.path.join(pops_dir, fname), 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception:
            continue
        for sm in re.finditer(r's:(STATE_\w+)\s*=\s*\{', content):
            state = sm.group(1)
            end = _block_end(content, sm.end())
            state_block = content[sm.end():end - 1]
            state_data = {}
            for rs in re.finditer(r'region_state:(\w+)\s*=\s*\{', state_block):
                tag = rs.group(1)
                rs_end = _block_end(state_block, rs.end())
                rs_content = state_block[rs.end():rs_end - 1]
                pops = _parse_rs_pops(rs_content)
                if pops:
                    state_data[tag] = pops
            if state_data:
                result[state] = state_data
    return result


def parse_buildings_files(buildings_dir):
    """Retourne {state: {tag: [(full_name, level)]}} depuis tous les fichiers."""
    result = {}
    if not os.path.isdir(buildings_dir):
        return result
    for fname in sorted(os.listdir(buildings_dir)):
        if not fname.endswith('.txt'):
            continue
        try:
            with open(os.path.join(buildings_dir, fname), 'r', encoding='utf-8-sig') as f:
                content = f.read()
        except Exception:
            continue
        for sm in re.finditer(r's:(STATE_\w+)\s*=\s*\{', content):
            state = sm.group(1)
            end = _block_end(content, sm.end())
            state_block = content[sm.end():end - 1]
            state_data = {}
            for rs in re.finditer(r'region_state:(\w+)\s*=\s*\{', state_block):
                tag = rs.group(1)
                rs_end = _block_end(state_block, rs.end())
                rs_content = state_block[rs.end():rs_end - 1]
                buildings = _parse_rs_buildings(rs_content)
                if buildings:
                    state_data[tag] = buildings
            if state_data:
                result[state] = state_data
    return result


def _find_state_file(state, folder):
    pat = re.compile(rf's:{re.escape(state)}\s*=\s*\{{')
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith('.txt'):
            continue
        path = os.path.join(folder, fname)
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                if pat.search(f.read()):
                    return path
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────
# FRAME PRINCIPALE
# ─────────────────────────────────────────────────────────────

class BuildPopFrame(ttk.Frame):

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config

        self._prov_arr          = None
        self._prov_ints         = None
        self._rendered          = None
        self._state_border_mask = None
        self._zoomed_arr        = None
        self._prov_ints_zoomed  = None
        self._zoom_at_cache     = None
        self._photo             = None
        self._zoom              = INITIAL_ZOOM
        self._loading           = False

        self._prov_to_state     = {}
        self._state_to_provs    = {}
        self._sea_states        = set()
        self._prov_owner_map    = {}
        self._substates         = {}
        self._country_colors    = {}

        # {state: {tag: [(culture,size)]}}
        self._pops_data         = {}
        # {state: {tag: [(building,level)]}}
        self._buildings_data    = {}

        self._selected_state    = None
        self._selected_tag      = None
        self._tag_btns          = {}   # tag -> button widget

        self._edited_pops       = None  # [(culture, size)]
        self._edited_buildings  = None  # [(building, level)]

        self._build()

    # ── CONSTRUCTION ─────────────────────────────────────────

    def _build(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=4)
        ttk.Button(toolbar, text="Charger la carte",
                   command=self._start_load).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Zoom +", command=self._zoom_in).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zoom -", command=self._zoom_out).pack(side="left", padx=2)
        self._zoom_label = ttk.Label(toolbar, text=f"Zoom: {int(self._zoom*100)}%")
        self._zoom_label.pack(side="left", padx=8)
        self._status_label = ttk.Label(toolbar,
                                        text="Appuie sur 'Charger la carte'",
                                        foreground="#888")
        self._status_label.pack(side="left", padx=10)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # Carte gauche
        map_cont = ttk.Frame(main)
        map_cont.pack(side="left", fill="both", expand=True)
        self._canvas = tk.Canvas(map_cont, bg="#1e2030",
                                  cursor="crosshair", highlightthickness=0)
        hbar = ttk.Scrollbar(map_cont, orient="horizontal", command=self._canvas.xview)
        vbar = ttk.Scrollbar(map_cont, orient="vertical",   command=self._canvas.yview)
        self._canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right",  fill="y")
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Button-1>",   self._on_click)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-2>",   self._start_pan)
        self._canvas.bind("<B2-Motion>",  self._do_pan)

        # Panneau droit
        panel = ttk.Frame(main, width=320)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)
        self._build_right_panel(panel)

    def _build_right_panel(self, parent):
        # Etat selectionne
        ttk.Label(parent, text="Etat :",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        self._state_label = ttk.Label(parent, text="(cliquer sur un etat)",
                                       font=("Consolas", 9), foreground="#cba6f7")
        self._state_label.pack(anchor="w", padx=8)

        # Selecteur TAG (split states)
        ttk.Label(parent, text="Sous-etat (TAG) :",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        self._tag_frame = ttk.Frame(parent)
        self._tag_frame.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(self._tag_frame, text="—", foreground="#6c7086",
                  font=("Segoe UI", 8)).pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=4, pady=4)

        # Zone scrollable (pops + buildings)
        sc = ttk.Frame(parent)
        sc.pack(fill="both", expand=True)
        self._side_canvas = tk.Canvas(sc, bg="#1e1e2e", highlightthickness=0)
        vsb = ttk.Scrollbar(sc, orient="vertical", command=self._side_canvas.yview)
        self._side_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._side_canvas.pack(side="left", fill="both", expand=True)

        self._scroll_frame = ttk.Frame(self._side_canvas)
        self._scroll_win = self._side_canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw")
        self._scroll_frame.bind(
            "<Configure>",
            lambda e: self._side_canvas.configure(
                scrollregion=self._side_canvas.bbox("all")))
        self._side_canvas.bind(
            "<Configure>",
            lambda e: self._side_canvas.itemconfig(self._scroll_win, width=e.width))
        self._scroll_frame.bind(
            "<Enter>",
            lambda e: self._side_canvas.bind_all("<MouseWheel>", self._side_scroll))
        self._scroll_frame.bind(
            "<Leave>",
            lambda e: self._side_canvas.unbind_all("<MouseWheel>"))

        sf = self._scroll_frame

        # ── POPS ─────────────────────────────────────────────
        ttk.Label(sf, text="POPULATIONS",
                  font=("Segoe UI", 9, "bold"),
                  foreground="#cba6f7").pack(anchor="w", padx=6, pady=(8, 2))
        self._pops_frame = ttk.Frame(sf)
        self._pops_frame.pack(fill="x", padx=6)

        add_pf = ttk.Frame(sf)
        add_pf.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(add_pf, text="Culture :", font=("Segoe UI", 8)).pack(side="left")
        self._new_cult_var = tk.StringVar()
        ttk.Entry(add_pf, textvariable=self._new_cult_var,
                  width=12, font=("Consolas", 8)).pack(side="left", padx=(2, 4))
        ttk.Label(add_pf, text="Taille :", font=("Segoe UI", 8)).pack(side="left")
        self._new_size_var = tk.StringVar(value="1000")
        ttk.Entry(add_pf, textvariable=self._new_size_var,
                  width=7, font=("Consolas", 8)).pack(side="left", padx=(2, 4))
        ttk.Button(add_pf, text="+", width=3, command=self._add_pop).pack(side="left")

        ttk.Separator(sf, orient="horizontal").pack(fill="x", padx=4, pady=8)

        # ── BATIMENTS ────────────────────────────────────────
        ttk.Label(sf, text="BATIMENTS",
                  font=("Segoe UI", 9, "bold"),
                  foreground="#cba6f7").pack(anchor="w", padx=6, pady=(0, 2))
        self._bldg_frame = ttk.Frame(sf)
        self._bldg_frame.pack(fill="x", padx=6)

        add_bf = ttk.Frame(sf)
        add_bf.pack(fill="x", padx=6, pady=(4, 8))
        ttk.Label(add_bf, text="Batiment :", font=("Segoe UI", 8)).pack(side="left")
        self._new_bldg_var = tk.StringVar()
        ttk.Entry(add_bf, textvariable=self._new_bldg_var,
                  width=15, font=("Consolas", 8)).pack(side="left", padx=(2, 4))
        ttk.Label(add_bf, text="Niv :", font=("Segoe UI", 8)).pack(side="left")
        self._new_lvl_var = tk.StringVar(value="1")
        ttk.Entry(add_bf, textvariable=self._new_lvl_var,
                  width=4, font=("Consolas", 8)).pack(side="left", padx=(2, 4))
        ttk.Button(add_bf, text="+", width=3, command=self._add_building).pack(side="left")

        # ── SAVE ─────────────────────────────────────────────
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=4)
        self._save_status = ttk.Label(parent, text="",
                                       foreground="#a6e3a1",
                                       font=("Segoe UI", 8), wraplength=300)
        self._save_status.pack(anchor="w", padx=8, pady=(4, 0))
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", padx=8, pady=6)
        ttk.Button(btn_row, text="Sauver Pops",
                   command=self._save_pops,
                   style="Accent.TButton").pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(btn_row, text="Sauver Batiments",
                   command=self._save_buildings,
                   style="Accent.TButton").pack(side="left", expand=True, fill="x")

    def _side_scroll(self, event):
        self._side_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── SELECTEUR TAG ─────────────────────────────────────────

    def _rebuild_tag_selector(self, state):
        """Reconstruit les boutons TAG selon les owners de l'etat."""
        for w in self._tag_frame.winfo_children():
            w.destroy()
        self._tag_btns = {}

        tags = sorted({tag for (s, tag) in self._substates if s == state})
        if not tags:
            ttk.Label(self._tag_frame, text="(aucun owner dans 00_states.txt)",
                      foreground="#f38ba8", font=("Segoe UI", 8)).pack(anchor="w")
            return

        for tag in tags:
            btn = ttk.Button(self._tag_frame, text=tag,
                             command=lambda t=tag: self._select_tag(t))
            btn.pack(side="left", padx=(0, 3))
            self._tag_btns[tag] = btn

        # Auto-selectionner le premier TAG
        self._select_tag(tags[0])

    def _select_tag(self, tag):
        # Sauvegarder les edits en cours avant de changer de TAG
        if self._selected_tag and self._edited_pops is not None:
            self._flush_edits_to_data(self._selected_state, self._selected_tag)

        self._selected_tag = tag

        # Mettre en evidence le bouton actif
        for t, btn in self._tag_btns.items():
            btn.configure(style="Accent.TButton" if t == tag else "TButton")

        # Charger les donnees de ce TAG
        state = self._selected_state
        self._edited_pops = list(
            self._pops_data.get(state, {}).get(tag, []))
        self._edited_buildings = list(
            self._buildings_data.get(state, {}).get(tag, []))

        self._refresh_pops_list()
        self._refresh_bldg_list()
        self._save_status.config(text="")

    def _flush_edits_to_data(self, state, tag):
        """Persiste les valeurs UI dans _pops_data/_buildings_data avant changement de TAG."""
        pops = self._collect_pops()
        blds = self._collect_buildings()
        if state not in self._pops_data:
            self._pops_data[state] = {}
        self._pops_data[state][tag] = pops
        if state not in self._buildings_data:
            self._buildings_data[state] = {}
        self._buildings_data[state][tag] = blds

    # ── LISTES DYNAMIQUES ────────────────────────────────────

    def _refresh_pops_list(self):
        for w in self._pops_frame.winfo_children():
            w.destroy()
        if not self._edited_pops:
            ttk.Label(self._pops_frame, text="(aucune pop)",
                      foreground="#6c7086", font=("Segoe UI", 8)).pack(anchor="w")
            return
        for i, (culture, size) in enumerate(self._edited_pops):
            row = ttk.Frame(self._pops_frame)
            row.pack(fill="x", pady=1)
            c_var = tk.StringVar(value=culture)
            s_var = tk.StringVar(value=str(size))
            ttk.Entry(row, textvariable=c_var, width=14,
                      font=("Consolas", 8)).pack(side="left", padx=(0, 2))
            ttk.Entry(row, textvariable=s_var, width=7,
                      font=("Consolas", 8)).pack(side="left", padx=(0, 2))
            row._cv = c_var
            row._sv = s_var
            ttk.Button(row, text="✕", width=2,
                       command=lambda idx=i: self._remove_pop(idx)).pack(side="left")

    def _refresh_bldg_list(self):
        for w in self._bldg_frame.winfo_children():
            w.destroy()
        if not self._edited_buildings:
            ttk.Label(self._bldg_frame, text="(aucun batiment)",
                      foreground="#6c7086", font=("Segoe UI", 8)).pack(anchor="w")
            return
        for i, (building, level) in enumerate(self._edited_buildings):
            row = ttk.Frame(self._bldg_frame)
            row.pack(fill="x", pady=1)
            display = building[len("building_"):] if building.startswith("building_") else building
            b_var = tk.StringVar(value=display)
            l_var = tk.StringVar(value=str(level))
            ttk.Entry(row, textvariable=b_var, width=18,
                      font=("Consolas", 8)).pack(side="left", padx=(0, 2))
            ttk.Entry(row, textvariable=l_var, width=4,
                      font=("Consolas", 8)).pack(side="left", padx=(0, 2))
            row._bv = b_var
            row._lv = l_var
            ttk.Button(row, text="✕", width=2,
                       command=lambda idx=i: self._remove_building(idx)).pack(side="left")

    # ── COLLECTE ─────────────────────────────────────────────

    def _collect_pops(self):
        result = []
        for row in self._pops_frame.winfo_children():
            if hasattr(row, '_cv'):
                c = row._cv.get().strip()
                s = row._sv.get().strip()
                if c:
                    try:
                        result.append((c, int(s)))
                    except ValueError:
                        result.append((c, 0))
        return result

    def _collect_buildings(self):
        result = []
        for row in self._bldg_frame.winfo_children():
            if hasattr(row, '_bv'):
                b = row._bv.get().strip()
                l = row._lv.get().strip()
                if b:
                    full = b if b.startswith("building_") else f"building_{b}"
                    try:
                        result.append((full, int(l)))
                    except ValueError:
                        result.append((full, 1))
        return result

    # ── ADD / REMOVE ─────────────────────────────────────────

    def _add_pop(self):
        if self._edited_pops is None:
            self._edited_pops = []
        self._edited_pops = self._collect_pops()
        c = self._new_cult_var.get().strip()
        if not c:
            return
        try:
            size = int(self._new_size_var.get())
        except ValueError:
            size = 1000
        self._edited_pops.append((c, size))
        self._new_cult_var.set("")
        self._refresh_pops_list()

    def _remove_pop(self, idx):
        self._edited_pops = self._collect_pops()
        if 0 <= idx < len(self._edited_pops):
            self._edited_pops.pop(idx)
        self._refresh_pops_list()

    def _add_building(self):
        if self._edited_buildings is None:
            self._edited_buildings = []
        self._edited_buildings = self._collect_buildings()
        b = self._new_bldg_var.get().strip()
        if not b:
            return
        try:
            level = int(self._new_lvl_var.get())
        except ValueError:
            level = 1
        full = b if b.startswith("building_") else f"building_{b}"
        self._edited_buildings.append((full, level))
        self._new_bldg_var.set("")
        self._new_lvl_var.set("1")
        self._refresh_bldg_list()

    def _remove_building(self, idx):
        self._edited_buildings = self._collect_buildings()
        if 0 <= idx < len(self._edited_buildings):
            self._edited_buildings.pop(idx)
        self._refresh_bldg_list()

    # ── CHARGEMENT CARTE ─────────────────────────────────────

    def _start_load(self):
        if self._loading:
            return
        self._loading = True
        self._status_label.config(text="Chargement en cours...")
        self._canvas.delete("all")
        self._canvas.create_text(400, 200, text="Chargement...",
                                  fill="#cba6f7", font=("Segoe UI", 14))
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _msg(self, text):
        self.after(0, lambda t=text: self._status_label.config(text=t))

    def _load_thread(self):
        try:
            mod = self.config.mod_path

            self._msg("Parsing state_regions...")
            prov_to_state, state_to_provs, sea_states = parse_state_regions(SR_DIR)
            self._prov_to_state  = prov_to_state
            self._state_to_provs = state_to_provs
            self._sea_states     = sea_states

            self._msg("Lecture 00_states.txt...")
            if mod:
                states_path = os.path.join(mod, "common/history/states/00_states.txt")
                prov_owner_map, substates = parse_states_file(states_path)
            else:
                prov_owner_map, substates = {}, {}
            self._prov_owner_map = prov_owner_map
            self._substates      = substates

            self._msg("Lecture couleurs pays...")
            colors = {}
            if mod:
                for d in [
                    os.path.join(mod, "common/country_definitions"),
                    os.path.join(self.config.vanilla_path or "",
                                 "game/common/country_definitions"),
                ]:
                    if os.path.isdir(d):
                        colors.update(parse_country_colors(d))
            self._country_colors = colors

            self._msg("Lecture pops...")
            if mod:
                self._pops_data = parse_pops_files(
                    os.path.join(mod, "common/history/pops"))

            self._msg("Lecture batiments...")
            if mod:
                self._buildings_data = parse_buildings_files(
                    os.path.join(mod, "common/history/buildings"))

            self._msg("Chargement provinces.png...")
            img = Image.open(PROV_PNG).convert("RGB")
            self._prov_arr = np.array(img)

            self._msg("Rendu numpy...")
            rendered, prov_ints, state_border = build_render(
                self._prov_arr, prov_to_state, prov_owner_map, colors, sea_states)
            self._rendered          = rendered
            self._prov_ints         = prov_ints
            self._state_border_mask = state_border
            self._zoom_at_cache     = None

            n_split = sum(
                1 for s in set(k[0] for k in substates)
                if len([k for k in substates if k[0] == s]) > 1
            )
            self.after(0, self._display_map)
            self.after(0, lambda: self._status_label.config(
                text=(f"Carte chargee — {len(prov_to_state)} provinces | "
                      f"{len(state_to_provs)} etats | {n_split} split states | "
                      f"{len(self._pops_data)} etats avec pops | "
                      f"{len(self._buildings_data)} etats avec batiments")
            ))
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._status_label.config(text=f"Erreur: {e}"))
            self.after(0, lambda: messagebox.showerror("Erreur chargement", tb))
        finally:
            self._loading = False

    # ── RENDU ────────────────────────────────────────────────

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

    def _display_map(self):
        if self._rendered is None:
            return
        if self._zoom_at_cache != self._zoom or self._zoomed_arr is None:
            self._rebuild_zoom_cache()
        arr = self._zoomed_arr.copy()

        # Surligner uniquement les provinces du TAG selectionne
        if self._selected_state and self._selected_tag and self._prov_ints_zoomed is not None:
            key = (self._selected_state, self._selected_tag)
            provs = self._substates.get(key, set())
            sel_ints = []
            for ph in provs:
                try:
                    sel_ints.append(int(ph[1:], 16))
                except ValueError:
                    pass
            if sel_ints:
                mask = np.isin(self._prov_ints_zoomed, sel_ints)
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

    # ── INTERACTIONS ─────────────────────────────────────────

    def _get_province_at(self, cx, cy):
        if self._prov_arr is None:
            return None
        ax = self._canvas.canvasx(cx)
        ay = self._canvas.canvasy(cy)
        ox = max(0, min(int(ax / self._zoom), self._prov_arr.shape[1] - 1))
        oy = max(0, min(int(ay / self._zoom), self._prov_arr.shape[0] - 1))
        rgb = self._prov_arr[oy, ox]
        return "x{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _on_click(self, event):
        if self._rendered is None:
            return
        prov_hex = self._get_province_at(event.x, event.y)
        if prov_hex is None:
            return
        state = self._prov_to_state.get(prov_hex)
        if not state or state in self._sea_states:
            return

        # Detecter le TAG owner de la province cliquee
        clicked_tag = self._prov_owner_map.get(prov_hex)

        if state != self._selected_state:
            # Nouveau state : reconstruire le selecteur TAG
            self._selected_state = state
            self._state_label.config(text=state)
            self._rebuild_tag_selector(state)
            # Si on connait le TAG clique, le selectionner directement
            if clicked_tag and clicked_tag in self._tag_btns:
                self._select_tag(clicked_tag)
        else:
            # Meme state : juste changer de TAG si besoin
            if clicked_tag and clicked_tag in self._tag_btns:
                if clicked_tag != self._selected_tag:
                    self._select_tag(clicked_tag)

    def _zoom_in(self):
        self._zoom = min(self._zoom * ZOOM_STEP, 2.0)
        self._display_map()

    def _zoom_out(self):
        self._zoom = max(self._zoom / ZOOM_STEP, 0.05)
        self._display_map()

    def _on_mousewheel(self, event):
        if self._rendered is None:
            return
        self._zoom = (min(self._zoom * ZOOM_STEP, 2.0)
                      if event.delta > 0
                      else max(self._zoom / ZOOM_STEP, 0.05))
        self._display_map()

    def _start_pan(self, event):
        self._canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    # ── SAUVEGARDE ───────────────────────────────────────────

    def _check_ready(self):
        if not self._selected_state or not self._selected_tag:
            messagebox.showwarning("Attention",
                                   "Selectionne un etat puis un TAG")
            return False
        if not self.config.mod_path:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return False
        return True

    def _all_tags_for_state(self, state):
        return sorted({tag for (s, tag) in self._substates if s == state})

    def _write_pops_file(self, state, edited_tag, pops, folder):
        """Reecrit le bloc s:STATE en preservant tous les autres TAGs."""
        all_tags = self._all_tags_for_state(state)
        if not all_tags:
            return False, f"Aucun owner pour {state}"

        path = _find_state_file(state, folder)
        if path is None:
            path = os.path.join(folder, "99_buildpop_pops.txt")

        content = ""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            shutil.copy(path, path + '.backup')

        T = '\t'
        lines = [f"s:{state} = {{"]
        for tag in all_tags:
            if tag == edited_tag:
                tag_pops = pops
            else:
                tag_pops = self._pops_data.get(state, {}).get(tag, [])
            lines.append(f"{T}region_state:{tag} = {{")
            for culture, size in tag_pops:
                lines.append(f"{T}{T}create_pop = {{")
                lines.append(f"{T}{T}{T}culture = {culture}")
                lines.append(f"{T}{T}{T}size = {size}")
                lines.append(f"{T}{T}}}")
            lines.append(f"{T}}}")
        lines.append("}")
        new_block = "\n".join(lines)

        pat = re.compile(rf's:{re.escape(state)}\s*=\s*\{{')
        sm = pat.search(content)
        if sm:
            end = _block_end(content, sm.end())
            new_content = content[:sm.start()] + new_block + content[end:]
        else:
            new_content = content + ("\n" if content else "") + new_block + "\n"

        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(new_content)
        return True, path

    def _write_buildings_file(self, state, edited_tag, buildings, folder):
        """Reecrit le bloc s:STATE batiments en preservant tous les autres TAGs."""
        all_tags = self._all_tags_for_state(state)
        if not all_tags:
            return False, f"Aucun owner pour {state}"

        path = _find_state_file(state, folder)
        if path is None:
            path = os.path.join(folder, "99_buildpop_buildings.txt")

        content = ""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            shutil.copy(path, path + '.backup')

        T = '\t'
        lines = [f"s:{state} = {{"]
        for tag in all_tags:
            if tag == edited_tag:
                tag_blds = buildings
            else:
                tag_blds = self._buildings_data.get(state, {}).get(tag, [])
            lines.append(f"{T}region_state:{tag} = {{")
            for building, level in tag_blds:
                lines.append(f"{T}{T}create_building = {{")
                lines.append(f"{T}{T}{T}building = \"{building}\"")
                lines.append(f"{T}{T}{T}add_ownership = {{")
                lines.append(f"{T}{T}{T}{T}country = {{")
                lines.append(f"{T}{T}{T}{T}{T}country = \"c:{tag}\"")
                lines.append(f"{T}{T}{T}{T}{T}levels = {level}")
                lines.append(f"{T}{T}{T}{T}}}")
                lines.append(f"{T}{T}{T}}}")
                lines.append(f"{T}{T}{T}reserves = 1")
                lines.append(f"{T}{T}}}")
            lines.append(f"{T}}}")
        lines.append("}")
        new_block = "\n".join(lines)

        pat = re.compile(rf's:{re.escape(state)}\s*=\s*\{{')
        sm = pat.search(content)
        if sm:
            end = _block_end(content, sm.end())
            new_content = content[:sm.start()] + new_block + content[end:]
        else:
            new_content = content + ("\n" if content else "") + new_block + "\n"

        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(new_content)
        return True, path

    def _save_pops(self):
        if not self._check_ready():
            return
        state = self._selected_state
        tag   = self._selected_tag
        pops  = self._collect_pops()
        if not pops:
            self._save_status.config(text="Aucune pop a sauvegarder")
            return
        pops_dir = os.path.join(self.config.mod_path, "common/history/pops")
        if not os.path.isdir(pops_dir):
            messagebox.showerror("Erreur", f"Dossier introuvable :\n{pops_dir}")
            return
        ok, info = self._write_pops_file(state, tag, pops, pops_dir)
        if ok:
            if state not in self._pops_data:
                self._pops_data[state] = {}
            self._pops_data[state][tag] = pops
            self._save_status.config(
                text=f"Pops OK [{tag}] -> {os.path.basename(info)}")

    def _save_buildings(self):
        if not self._check_ready():
            return
        state     = self._selected_state
        tag       = self._selected_tag
        buildings = self._collect_buildings()
        if not buildings:
            self._save_status.config(text="Aucun batiment a sauvegarder")
            return
        bldgs_dir = os.path.join(self.config.mod_path, "common/history/buildings")
        if not os.path.isdir(bldgs_dir):
            messagebox.showerror("Erreur", f"Dossier introuvable :\n{bldgs_dir}")
            return
        ok, info = self._write_buildings_file(state, tag, buildings, bldgs_dir)
        if ok:
            if state not in self._buildings_data:
                self._buildings_data[state] = {}
            self._buildings_data[state][tag] = buildings
            self._save_status.config(
                text=f"Batiments OK [{tag}] -> {os.path.basename(info)}")
