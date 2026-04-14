"""
Map Editor pour Victoria 3
- Modes STATE et PROVINCE
- Mode STATE: sélection par sous-état (comportement original)
- Mode PROVINCE: sélection par province, provinces encadrées en noir
- Transfert de provinces entre pays avec réécriture complète des states
- Mode PEINTURE: switch pour peindre directement province ou sous-état sur clic gauche
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
import shutil
import numpy as np
from PIL import Image, ImageTk

DATA_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROV_PNG  = os.path.join(DATA_DIR, "map_data", "provinces.png")
SR_DIR    = os.path.join(DATA_DIR, "map_data", "state_regions")

OCEAN_COLOR   = (30,  45,  80)
UNKNOWN_COLOR = (70,  70,  70)
STATE_BORDER_COLOR = (180, 30,  30)
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
    return rendered, prov_ints


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
        self._build()

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
        self._canvas.bind("<Button-1>", self._on_click)
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
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(panel, text="Info province", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._info_label = ttk.Label(panel, text="-", font=("Consolas", 8), wraplength=220, justify="left")
        self._info_label.pack(anchor="w", pady=4)
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        switch_frame = ttk.Frame(panel)
        switch_frame.pack(fill="x", pady=(0, 4))
        ttk.Label(switch_frame, text="Mode :", font=("Segoe UI", 9, "bold")).pack(side="left")
        self._paint_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(switch_frame, text="Peinture", variable=self._paint_mode_var, command=self._on_paint_mode_toggle).pack(side="right")
        self._paint_status = ttk.Label(switch_frame, text="", font=("Segoe UI", 8, "bold"), foreground="#f9e2af")
        self._paint_status.pack(side="right", padx=(0, 6))
        ttk.Label(panel, text="Transferer vers TAG :", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._new_tag = tk.StringVar()
        ttk.Entry(panel, textvariable=self._new_tag, width=10, font=("Consolas", 11)).pack(fill="x", pady=4)
        ttk.Button(panel, text="Transferer", command=self._transfer, style="Accent.TButton").pack(fill="x", pady=2)
        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Button(panel, text="Sauvegarder (00_states.txt)", command=self._save).pack(fill="x")
        self._save_status = ttk.Label(panel, text="", foreground="#a6e3a1", font=("Segoe UI", 8), wraplength=220)
        self._save_status.pack(anchor="w", pady=2)

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

    def _on_paint_mode_toggle(self):
        if self._paint_mode_var.get():
            tag = self._new_tag.get().strip().upper()
            if tag and len(tag) >= 2:
                self._paint_status.config(text=f"Peint. {tag}")
            else:
                self._paint_status.config(text="Peint. ?")
            self.winfo_toplevel().config(cursor="crosshair")
        else:
            self._paint_status.config(text="")
            self.winfo_toplevel().config(cursor="crosshair")

    def _refresh_render(self):
        if self._prov_arr is None:
            return
        rendered, prov_ints = build_render(
            self._prov_arr, self._prov_to_state,
            self._prov_owner_map, self._country_colors, self._sea_states,
            mode=self._mode)
        self._rendered = rendered
        self._prov_ints = prov_ints
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
            prov_to_state, state_to_provs, sea_states = parse_state_regions(SR_DIR)
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
            img = Image.open(PROV_PNG).convert("RGB")
            self._prov_arr = np.array(img)
            self._after("Rendu numpy...")
            rendered, prov_ints = build_render(
                self._prov_arr, prov_to_state, prov_owner_map,
                country_colors, sea_states, mode=self._mode)
            self._rendered = rendered
            self._prov_ints = prov_ints
            split = sum(1 for s in set(k[0] for k in substates) if len([k for k in substates if k[0] == s]) > 1)
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

    def _display_map(self):
        if self._rendered is None:
            return
        arr = self._rendered.copy()
        if self._selected:
            mask = np.zeros(arr.shape[:2], dtype=bool)
            for (state, tag) in self._selected:
                for prov_hex in self._substates.get((state, tag), set()):
                    try:
                        prov_int = int(prov_hex[1:], 16)
                    except ValueError:
                        continue
                    mask |= (self._prov_ints == prov_int)
            arr[mask] = np.clip(arr[mask].astype(np.int32) + SELECT_BOOST, 0, 255).astype(np.uint8)
        if self._prov_selected:
            mask = np.zeros(arr.shape[:2], dtype=bool)
            for prov_hex in self._prov_selected:
                try:
                    prov_int = int(prov_hex[1:], 16)
                except ValueError:
                    continue
                mask |= (self._prov_ints == prov_int)
            arr[mask] = np.clip(arr[mask].astype(np.int32) + SELECT_BOOST, 0, 255).astype(np.uint8)
        H, W = arr.shape[:2]
        new_w = max(1, int(W * self._zoom))
        new_h = max(1, int(H * self._zoom))
        pil_img = Image.fromarray(arr).resize((new_w, new_h), Image.NEAREST)
        self._photo = ImageTk.PhotoImage(pil_img)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.config(scrollregion=(0, 0, new_w, new_h))
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
        if self._mode == MODE_STATE:
            if not state or not tag:
                return
            if self._paint_mode_var.get():
                new_tag = self._new_tag.get().strip().upper()
                if new_tag and len(new_tag) >= 2:
                    old_tag = tag
                    if old_tag != new_tag:
                        for p in self._substates.get((state, tag), set()):
                            self._prov_owner_map[p] = new_tag
                        provs = self._substates.pop((state, tag), set())
                        self._substates.setdefault((state, new_tag), set()).update(provs)
                        self._selected = {(state, new_tag)}
                        self._refresh_render()
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
                        self._prov_owner_map[prov_hex] = new_tag
                        if (state, old_tag) in self._substates:
                            self._substates[(state, old_tag)].discard(prov_hex)
                        self._substates.setdefault((state, new_tag), set()).add(prov_hex)
                        self._refresh_render()
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
        self._display_map()

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
        for (state, old_tag) in list(self._selected):
            for prov_hex in self._substates.get((state, old_tag), set()):
                self._prov_owner_map[prov_hex] = new_tag
            provs = self._substates.pop((state, old_tag), set())
            self._substates.setdefault((state, new_tag), set()).update(provs)
        rendered, _ = build_render(
            self._prov_arr, self._prov_to_state,
            self._prov_owner_map, self._country_colors, self._sea_states,
            mode=self._mode)
        self._rendered = rendered
        self._selected = {(state, new_tag) for (state, _) in self._selected}
        self._refresh_ui()
        self._save_status.config(text=f"{len(self._selected)} sous-etat(s) modifie(s) (non sauvegarde)")

    def _transfer_provinces(self, new_tag):
        if not self._prov_selected:
            messagebox.showwarning("Attention", "Selectionne d'abord des provinces")
            return
        painted = 0
        for prov_hex in list(self._prov_selected):
            old_tag = self._prov_owner_map.get(prov_hex)
            state = self._prov_to_state.get(prov_hex)
            if not state or not old_tag:
                continue
            self._prov_owner_map[prov_hex] = new_tag
            if (state, old_tag) in self._substates:
                self._substates[(state, old_tag)].discard(prov_hex)
            self._substates.setdefault((state, new_tag), set()).add(prov_hex)
            painted += 1
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
        shutil.copy(states_path, states_path + ".backup")
        self._rebuild_states_file(states_path)
        self._save_status.config(text="Sauvegarde complete !")
        messagebox.showinfo("Sauvegarde", "00_states.txt ecrit completement\n(backup cree)")

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
                state_block = content[block_start:j - 1]
                new_state = self._build_state_block(state_name, state_block)
                new_content.append(content[i:start_of_state])
                new_content.append(new_state)
                i = j
            else:
                new_content.append(content[i:])
                break
        with open(states_path, "w", encoding="utf-8-sig") as fh:
            fh.write("".join(new_content))

    def _build_state_block(self, state_name, original_block):
        # Retirer les create_state existants, garder le reste (add_claim, etc.)
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
            lines.append(f"    create_state = {{")
            lines.append(f"        country = c:{tag}")
            lines.append(f"        owned_provinces = {{ {provs_str} }}")
            lines.append(f"    }}")

        if other_content:
            for line in other_content.splitlines():
                lines.append(f"    {line}" if line.strip() else line)

        lines.append("}")
        return "\n".join(lines) + "\n"
