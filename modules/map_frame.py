"""
Map Editor pour Victoria 3
- Affiche provinces.png coloriee par pays (d'apres 00_states.txt du mod)
- Gere les split states (plusieurs pays dans un meme etat)
- Clic = selectionne le sous-etat sous le curseur (state_name, tag)
- Ctrl+Clic = multi-selection
- Transfert de sous-etats vers un autre TAG + sauvegarde dans 00_states.txt
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
import numpy as np
from PIL import Image, ImageTk

DATA_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROV_PNG  = os.path.join(DATA_DIR, "map_data", "provinces.png")
SR_DIR    = os.path.join(DATA_DIR, "map_data", "state_regions")

OCEAN_COLOR   = (30,  45,  80)
UNKNOWN_COLOR = (70,  70,  70)
BORDER_COLOR  = (180, 30,  30)   # rouge bordure entre sous-etats
SELECT_BOOST  = 70               # luminosite ajoutee a la selection
INITIAL_ZOOM  = 0.22
ZOOM_STEP     = 1.25


# ============================================================
# PARSEURS
# ============================================================

def parse_state_regions(sr_dir):
    """
    Retourne:
      prov_to_state : {province_hex: STATE_NAME}
      state_to_provs: {STATE_NAME: set(province_hex)}
    """
    prov_to_state  = {}
    state_to_provs = {}
    prov_pat  = re.compile(r'"(x[0-9A-Fa-f]{6})"')
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
                p = "x" + pm.group(1)[1:].upper()
                provs.add(p)
                prov_to_state[p] = state
            state_to_provs[state] = provs

    return prov_to_state, state_to_provs


def parse_states_file(states_path):
    """
    Parse 00_states.txt avec support des split states.

    Retourne:
      prov_owner_map : {province_hex: TAG}
          → ownership par province (gere les split states)
      substates      : {(STATE_NAME, TAG): set(province_hex)}
          → regroupement par sous-etat pour la selection/highlight
    """
    prov_owner_map = {}
    substates      = {}

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

        # Chaque create_state = { country = c:TAG  owned_provinces = { ... } }
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
    """Retourne {TAG: (R, G, B)}"""
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


# ============================================================
# RENDU NUMPY
# ============================================================

def _random_country_color(tag):
    """Couleur aleatoire stable par hash du TAG."""
    import hashlib
    h = hashlib.md5(tag.encode()).digest()
    return (80 + h[0] % 150, 80 + h[1] % 150, 80 + h[2] % 150)


def build_render(provinces_arr, prov_to_state, prov_owner_map, country_colors):
    """
    Construit le rendu (H, W, 3).
    - Couleur par province selon son TAG proprietaire
    - Bordure rouge entre sous-etats (state, tag) differents
    """
    H, W = provinces_arr.shape[:2]

    r = provinces_arr[:, :, 0].astype(np.uint32)
    g = provinces_arr[:, :, 1].astype(np.uint32)
    b = provinces_arr[:, :, 2].astype(np.uint32)
    prov_ints = (r << 16) | (g << 8) | b   # (H, W)

    # --- Tables de lookup ---
    color_table    = np.full((16_777_216, 3), fill_value=list(OCEAN_COLOR), dtype=np.uint8)
    substate_table = np.zeros(16_777_216, dtype=np.uint32)   # 0 = ocean

    # Construire ID numerique par sous-etat (state_name, tag)
    # Cle = toutes les combinaisons presentes dans les deux dicts
    all_substates = set()
    for prov_hex, state_name in prov_to_state.items():
        tag = prov_owner_map.get(prov_hex)
        all_substates.add((state_name, tag))   # tag peut etre None

    substate_ids = {ss: idx + 1 for idx, ss in enumerate(sorted(
        all_substates, key=lambda x: (x[0], x[1] or "")
    ))}

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

        color_table[prov_int]    = color
        substate_table[prov_int] = substate_ids.get((state_name, tag), 0)

    # Appliquer
    rendered     = color_table[prov_ints]       # (H, W, 3)
    substate_map = substate_table[prov_ints]    # (H, W) — ID sous-etat par pixel

    # --- Bordures entre sous-etats differents ---
    land    = substate_map > 0
    h_diff  = substate_map[:, :-1] != substate_map[:, 1:]
    v_diff  = substate_map[:-1, :] != substate_map[1:, :]
    h_land  = land[:, :-1] & land[:, 1:]
    v_land  = land[:-1, :] & land[1:, :]

    border  = np.zeros((H, W), dtype=bool)
    border[:, :-1] |= h_diff & h_land
    border[:, 1:]  |= h_diff & h_land
    border[:-1, :] |= v_diff & v_land
    border[1:, :]  |= v_diff & v_land

    rendered[border] = BORDER_COLOR

    return rendered, prov_ints


# ============================================================
# SAUVEGARDE 00_STATES
# ============================================================

def transfer_substates_in_file(states_path, transfers):
    """
    transfers : liste de (state_name, old_tag, new_tag)
    Modifie UNIQUEMENT le bloc create_state { country = c:old_tag } de chaque etat.
    """
    with open(states_path, "r", encoding="utf-8-sig") as fh:
        content = fh.read()

    for state_name, old_tag, new_tag in transfers:
        sm = re.search(rf's:{re.escape(state_name)}\s*=\s*\{{', content)
        if not sm:
            continue

        # Trouver la fin du bloc etat
        start = sm.end()
        depth, i = 1, start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1
        state_end = i - 1
        state_block = content[start:state_end]

        # Trouver le create_state qui contient country = c:old_tag
        new_state_block = state_block
        for cs_match in re.finditer(r'create_state\s*=\s*\{', state_block):
            cs_start = cs_match.end()
            depth2, j = 1, cs_start
            while j < len(state_block) and depth2 > 0:
                if state_block[j] == "{": depth2 += 1
                elif state_block[j] == "}": depth2 -= 1
                j += 1
            cs_full  = state_block[cs_match.start():j]
            cs_inner = state_block[cs_start:j - 1]

            tag_m = re.search(r'country\s*=\s*c:(\w+)', cs_inner)
            if tag_m and tag_m.group(1) == old_tag:
                new_cs = cs_full.replace(
                    f'country = c:{old_tag}',
                    f'country = c:{new_tag}',
                    1
                )
                new_state_block = new_state_block.replace(cs_full, new_cs, 1)
                break

        content = content[:start] + new_state_block + content[state_end:]

    with open(states_path, "w", encoding="utf-8-sig") as fh:
        fh.write(content)


# ============================================================
# FRAME CARTE
# ============================================================

class MapFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config

        # Donnees carte
        self._prov_arr       = None   # numpy (H, W, 3)
        self._prov_ints      = None   # numpy (H, W)
        self._rendered       = None   # numpy (H, W, 3)
        self._prov_to_state  = {}     # {prov_hex: state_name}
        self._state_to_provs = {}     # {state_name: set(prov_hex)}
        self._prov_owner_map = {}     # {prov_hex: TAG}  ← par province
        self._substates      = {}     # {(state, tag): set(prov_hex)}
        self._country_colors = {}

        # UI
        self._zoom     = INITIAL_ZOOM
        self._photo    = None
        self._selected = set()    # set de (state_name, tag)
        self._pending  = {}       # {(state_name, old_tag): new_tag}
        self._loading  = False

        self._build()

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------

    def _build(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=8, pady=4)

        ttk.Button(toolbar, text="Charger la carte", command=self._start_load).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Zoom +", command=self._zoom_in).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zoom -", command=self._zoom_out).pack(side="left", padx=2)
        self._zoom_label = ttk.Label(toolbar, text=f"Zoom: {int(self._zoom*100)}%")
        self._zoom_label.pack(side="left", padx=8)
        self._status_label = ttk.Label(toolbar, text="Appuie sur 'Charger la carte'", foreground="#888")
        self._status_label.pack(side="left", padx=10)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # Canvas
        map_container = ttk.Frame(main)
        map_container.pack(side="left", fill="both", expand=True)

        self._canvas = tk.Canvas(map_container, bg="#1e2030", cursor="crosshair",
                                  highlightthickness=0)
        hbar = ttk.Scrollbar(map_container, orient="horizontal", command=self._canvas.xview)
        vbar = ttk.Scrollbar(map_container, orient="vertical",   command=self._canvas.yview)
        self._canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right",  fill="y")
        self._canvas.pack(fill="both", expand=True)

        self._canvas.bind("<Button-1>",         self._on_click)
        self._canvas.bind("<Control-Button-1>", self._on_ctrl_click)
        self._canvas.bind("<MouseWheel>",        self._on_mousewheel)
        self._canvas.bind("<Button-2>",          self._start_pan)
        self._canvas.bind("<B2-Motion>",         self._do_pan)

        # Panneau droite
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
        self._info_label = ttk.Label(panel, text="-", font=("Consolas", 8),
                                      wraplength=220, justify="left")
        self._info_label.pack(anchor="w", pady=4)

        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(panel, text="Transferer vers TAG :", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._new_tag = tk.StringVar()
        ttk.Entry(panel, textvariable=self._new_tag, width=10,
                  font=("Consolas", 11)).pack(fill="x", pady=4)
        ttk.Button(panel, text="Transferer", command=self._transfer,
                   style="Accent.TButton").pack(fill="x", pady=2)

        ttk.Separator(panel, orient="horizontal").pack(fill="x", pady=5)
        ttk.Button(panel, text="Sauvegarder (00_states.txt)", command=self._save).pack(fill="x")
        self._save_status = ttk.Label(panel, text="", foreground="#a6e3a1", font=("Segoe UI", 8),
                                       wraplength=220)
        self._save_status.pack(anchor="w", pady=2)

    # ----------------------------------------------------------
    # CHARGEMENT
    # ----------------------------------------------------------

    def _start_load(self):
        if self._loading:
            return
        self._loading = True
        self._status_label.config(text="Chargement en cours...")
        self._canvas.delete("all")
        self._canvas.create_text(400, 200, text="Chargement de la carte...",
                                  fill="#cba6f7", font=("Segoe UI", 14))
        threading.Thread(target=self._load_thread, daemon=True).start()

    def _load_thread(self):
        try:
            mod = self.config.mod_path

            self._after("Parsing state_regions...")
            prov_to_state, state_to_provs = parse_state_regions(SR_DIR)
            self._prov_to_state  = prov_to_state
            self._state_to_provs = state_to_provs

            self._after("Lecture 00_states.txt (split states inclus)...")
            states_path = os.path.join(mod, "common/history/states/00_states.txt") if mod else ""
            if mod and os.path.exists(states_path):
                prov_owner_map, substates = parse_states_file(states_path)
            else:
                vanilla = self.config.vanilla_path
                vpath   = os.path.join(vanilla, "game/common/history/states/00_states.txt") if vanilla else ""
                prov_owner_map, substates = parse_states_file(vpath) if os.path.exists(vpath) else ({}, {})
            self._prov_owner_map = prov_owner_map
            self._substates      = substates

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

            self._after("Rendu numpy (couleurs + bordures)...")
            rendered, prov_ints = build_render(
                self._prov_arr, prov_to_state, prov_owner_map, country_colors
            )
            self._rendered  = rendered
            self._prov_ints = prov_ints

            # Stats split states
            split = sum(1 for s in set(k[0] for k in substates) if
                        len([k for k in substates if k[0] == s]) > 1)

            self.after(0, lambda: self._display_map())
            self.after(0, lambda: self._status_label.config(
                text=f"Carte chargee — {len(prov_to_state)} provinces | "
                     f"{len(state_to_provs)} etats | {split} split states"
            ))

        except Exception as e:
            import traceback
            msg = traceback.format_exc()
            self.after(0, lambda: self._status_label.config(text=f"Erreur: {e}"))
            self.after(0, lambda: messagebox.showerror("Erreur chargement", msg))
        finally:
            self._loading = False

    def _after(self, msg):
        self.after(0, lambda m=msg: self._status_label.config(text=m))

    # ----------------------------------------------------------
    # AFFICHAGE
    # ----------------------------------------------------------

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
            arr[mask] = np.clip(
                arr[mask].astype(np.int32) + SELECT_BOOST, 0, 255
            ).astype(np.uint8)

        H, W   = arr.shape[:2]
        new_w  = max(1, int(W * self._zoom))
        new_h  = max(1, int(H * self._zoom))

        pil_img    = Image.fromarray(arr).resize((new_w, new_h), Image.NEAREST)
        self._photo = ImageTk.PhotoImage(pil_img)

        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.config(scrollregion=(0, 0, new_w, new_h))
        self._zoom_label.config(text=f"Zoom: {int(self._zoom*100)}%")

    # ----------------------------------------------------------
    # ZOOM / PAN
    # ----------------------------------------------------------

    def _zoom_in(self):
        self._zoom = min(self._zoom * ZOOM_STEP, 2.0)
        self._display_map()

    def _zoom_out(self):
        self._zoom = max(self._zoom / ZOOM_STEP, 0.05)
        self._display_map()

    def _on_mousewheel(self, event):
        if self._rendered is None:
            return
        self._zoom = min(self._zoom * ZOOM_STEP, 2.0) if event.delta > 0 \
                     else max(self._zoom / ZOOM_STEP, 0.05)
        self._display_map()

    def _start_pan(self, event):
        self._canvas.scan_mark(event.x, event.y)

    def _do_pan(self, event):
        self._canvas.scan_dragto(event.x, event.y, gain=1)

    # ----------------------------------------------------------
    # SELECTION
    # ----------------------------------------------------------

    def _get_substate_at(self, canvas_x, canvas_y):
        """
        Retourne (state_name, tag, prov_hex) pour la position canvas.
        Tient compte de l'ownership PAR PROVINCE (split states).
        """
        if self._prov_arr is None:
            return None, None, None

        abs_x = self._canvas.canvasx(canvas_x)
        abs_y = self._canvas.canvasy(canvas_y)
        ox = max(0, min(int(abs_x / self._zoom), self._prov_arr.shape[1] - 1))
        oy = max(0, min(int(abs_y / self._zoom), self._prov_arr.shape[0] - 1))

        rgb     = self._prov_arr[oy, ox]
        prov_hex = "x{:02X}{:02X}{:02X}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        state   = self._prov_to_state.get(prov_hex)
        tag     = self._prov_owner_map.get(prov_hex) if state else None
        return state, tag, prov_hex

    def _on_click(self, event):
        if self._rendered is None:
            return
        state, tag, prov_hex = self._get_substate_at(event.x, event.y)
        self._selected.clear()
        if state and tag:
            self._selected.add((state, tag))
        self._refresh_ui(state, tag, prov_hex)

    def _on_ctrl_click(self, event):
        if self._rendered is None:
            return
        state, tag, prov_hex = self._get_substate_at(event.x, event.y)
        if state and tag:
            key = (state, tag)
            if key in self._selected:
                self._selected.discard(key)
            else:
                self._selected.add(key)
        self._refresh_ui(state, tag, prov_hex)

    def _refresh_ui(self, last_state=None, last_tag=None, last_prov=None):
        self._sel_listbox.delete(0, "end")
        for (state, tag) in sorted(self._selected):
            pending = self._pending.get((state, tag))
            current = pending or tag
            n_prov  = len(self._substates.get((state, tag), set()))
            split   = len([k for k in self._substates if k[0] == state]) > 1
            split_marker = " [SPLIT]" if split else ""
            self._sel_listbox.insert("end", f"{state}{split_marker}  [{current}]  ({n_prov}p)")

        if last_state:
            # Verifier si l'etat est split
            all_parts = [(k, len(v)) for k, v in self._substates.items() if k[0] == last_state]
            if len(all_parts) > 1:
                parts_str = "  |  ".join(f"{t}({n}p)" for (_, t), n in all_parts)
                split_info = f"\nSPLIT STATE: {parts_str}"
            else:
                split_info = ""
            pending = self._pending.get((last_state, last_tag))
            extra   = f"  (-> {pending})" if pending else ""
            self._info_label.config(
                text=f"Province : {last_prov}\nEtat     : {last_state}\nPays     : {last_tag or '?'}{extra}{split_info}"
            )

        self._display_map()

    def _clear_selection(self):
        self._selected.clear()
        self._sel_listbox.delete(0, "end")
        self._info_label.config(text="-")
        self._display_map()

    # ----------------------------------------------------------
    # TRANSFERT
    # ----------------------------------------------------------

    def _transfer(self):
        if not self._selected:
            messagebox.showwarning("Attention", "Selectionne d'abord des sous-etats sur la carte")
            return
        new_tag = self._new_tag.get().strip().upper()
        if not new_tag or len(new_tag) < 2:
            messagebox.showerror("Erreur", "Entre un TAG valide")
            return

        for (state, old_tag) in self._selected:
            # Mettre a jour prov_owner_map
            for prov_hex in self._substates.get((state, old_tag), set()):
                self._prov_owner_map[prov_hex] = new_tag
            # Deplacer le sous-etat dans substates
            provs = self._substates.pop((state, old_tag), set())
            self._substates.setdefault((state, new_tag), set()).update(provs)
            # Marquer comme pending
            self._pending[(state, old_tag)] = new_tag

        # Re-rendre avec les nouvelles couleurs
        rendered, _ = build_render(
            self._prov_arr, self._prov_to_state,
            self._prov_owner_map, self._country_colors
        )
        self._rendered = rendered

        # Mettre a jour la selection avec les nouvelles cles
        self._selected = {(state, new_tag) for (state, _) in self._selected}

        self._refresh_ui()
        self._save_status.config(
            text=f"{len(self._pending)} sous-etat(s) modifie(s) (non sauvegarde)"
        )

    # ----------------------------------------------------------
    # SAUVEGARDE
    # ----------------------------------------------------------

    def _save(self):
        if not self._pending:
            messagebox.showinfo("Info", "Aucune modification en attente")
            return

        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        states_path = os.path.join(mod, "common/history/states/00_states.txt")
        if not os.path.exists(states_path):
            messagebox.showerror("Erreur", f"Fichier introuvable:\n{states_path}")
            return

        import shutil
        shutil.copy(states_path, states_path + ".backup")

        # Construire la liste des transferts (state, old_tag, new_tag)
        transfers = [(state, old_tag, new_tag)
                     for (state, old_tag), new_tag in self._pending.items()]

        transfer_substates_in_file(states_path, transfers)

        count = len(transfers)
        self._pending.clear()
        self._save_status.config(text=f"Sauvegarde ! {count} sous-etat(s) mis a jour")
        messagebox.showinfo("Sauvegarde",
                            f"{count} modification(s) ecrites dans 00_states.txt\n(backup cree)")
