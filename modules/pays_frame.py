import tkinter as tk
from tkinter import ttk, messagebox
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
        self._tab_tech(nb)
        self._tab_techno_generale(nb)
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

    # ---------------- TABS ----------------

    def _tab_generale(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Generale")

        ttk.Label(f, text="Informations generales du pays").pack(pady=10)

    def _tab_lois(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Lois")

        ttk.Label(f, text="Gestion des lois").pack(pady=10)

    def _tab_tech(self, nb):
        f = TechFrame(nb, self.config)
        nb.add(f, text="Technologie")

    def _tab_techno_generale(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="Technologie générale")

        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Charger 00_major_tags.txt", command=self._load_major_tags).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Sauvegarder", command=self._save_major_tags).pack(side="left", padx=5)
        self._major_tags_status = ttk.Label(btn_frame, text="")
        self._major_tags_status.pack(side="left", padx=10)

        base_frame = ttk.LabelFrame(f, text="Défaut (BASE:)")
        base_frame.pack(fill="x", padx=10, pady=(5, 10))

        base_content = ttk.Frame(base_frame)
        base_content.pack(fill="x", padx=5, pady=5)

        self._effect_combo = ttk.Combobox(base_content, width=30, state="readonly")
        self._effect_combo.pack(side="left", padx=5)
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
        self._effect_combo['values'] = self._effect_combo_items


        outer = ttk.Frame(f)
        outer.pack(fill="both", expand=True, padx=10, pady=5)

        hmm_frame = ttk.LabelFrame(outer, text="Technologie HMM")
        hmm_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        regular_frame = ttk.LabelFrame(outer, text="Technologie Standard")
        regular_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self._hmm_canvas = tk.Canvas(hmm_frame)
        self._hmm_scrollbar = ttk.Scrollbar(hmm_frame, orient="vertical", command=self._hmm_canvas.yview)
        self._hmm_sections_frame = ttk.Frame(self._hmm_canvas)
        self._hmm_sections_frame.bind(
            "<Configure>",
            lambda e: self._hmm_canvas.configure(scrollregion=self._hmm_canvas.bbox("all"))
        )
        self._hmm_canvas_window = self._hmm_canvas.create_window((0, 0), window=self._hmm_sections_frame, anchor="nw")
        self._hmm_canvas.configure(yscrollcommand=self._hmm_scrollbar.set)
        self._hmm_canvas.bind("<Configure>", lambda e: self._hmm_canvas.itemconfig(self._hmm_canvas_window, width=e.width))
        self._hmm_scrollbar.pack(side="right", fill="y")
        self._hmm_canvas.pack(side="left", fill="both", expand=True)

        self._regular_canvas = tk.Canvas(regular_frame)
        self._regular_scrollbar = ttk.Scrollbar(regular_frame, orient="vertical", command=self._regular_canvas.yview)
        self._regular_sections_frame = ttk.Frame(self._regular_canvas)
        self._regular_sections_frame.bind(
            "<Configure>",
            lambda e: self._regular_canvas.configure(scrollregion=self._regular_canvas.bbox("all"))
        )
        self._regular_canvas_window = self._regular_canvas.create_window((0, 0), window=self._regular_sections_frame, anchor="nw")
        self._regular_canvas.configure(yscrollcommand=self._regular_scrollbar.set)
        self._regular_canvas.bind("<Configure>", lambda e: self._regular_canvas.itemconfig(self._regular_canvas_window, width=e.width))
        self._regular_scrollbar.pack(side="right", fill="y")
        self._regular_canvas.pack(side="left", fill="both", expand=True)

        self._hmm_section_data = []
        self._regular_section_data = []
        self._major_tags_filepath = None

    def _load_major_tags(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        filepath = os.path.join(mod, "common", "history", "countries", "00_major_tags.txt")
        if not os.path.exists(filepath):
            messagebox.showerror("Erreur", f"Fichier introuvable:\n{filepath}")
            return

        for widget in self._hmm_sections_frame.winfo_children():
            widget.destroy()
        for widget in self._regular_sections_frame.winfo_children():
            widget.destroy()
        self._hmm_section_data = []
        self._regular_section_data = []

        sections = []
        current_header = None
        current_tags = []
        base_line = ""

        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                if raw.upper().startswith("BASE:"):
                    base_line = raw.split("BASE:", 1)[1].strip()
                    continue
                if raw.startswith("#"):
                    if current_header is not None:
                        sections.append((current_header, list(current_tags)))
                    current_header = raw
                    current_tags = []
                    continue
                current_tags.append(raw)

        if current_header is not None:
            sections.append((current_header, list(current_tags)))

        self._base_var.set(base_line)
        self._major_tags_filepath = filepath

        def header_to_effect(header):
            upper = header.upper()
            tier_match = re.search(r'TIER_(\d)', upper)
            tier = tier_match.group(1) if tier_match else "?"
            if "_TECH_HMM" in upper:
                return f"effect_starting_technology_tier_{tier}_tech_hmm = yes"
            elif "_TECH" in upper:
                return f"effect_starting_technology_tier_{tier}_tech = yes"
            return header.lstrip("# ")

        def is_hmm(effect):
            return "_tech_hmm" in effect.lower()

        hmm_count = 0
        regular_count = 0

        for header, tags in sections:
            effect = header_to_effect(header)
            is_hmm_effect = is_hmm(effect)

            if is_hmm_effect:
                parent_frame = self._hmm_sections_frame
                lf = ttk.LabelFrame(parent_frame, text=effect)
                lf.pack(fill="x", padx=5, pady=3)

                txt = tk.Text(lf, height=4, font=("Consolas", 9), wrap="word")
                txt.pack(fill="both", expand=True, padx=5, pady=3)
                txt.insert("1.0", "\n".join(tags))

                self._hmm_section_data.append((header, effect, txt))
                hmm_count += 1
            else:
                parent_frame = self._regular_sections_frame

                txt = tk.Text(parent_frame, height=4, font=("Consolas", 9), wrap="word")
                txt.pack(fill="x", padx=5, pady=(3, 0))
                txt.insert("1.0", "\n".join(tags))

                lf = ttk.LabelFrame(parent_frame, text=effect)
                lf.pack(fill="x", padx=5, pady=(0, 3))
                lf.pack_forget()

                self._regular_section_data.append((header, effect, txt, lf))
                regular_count += 1

        for header, effect, txt, lf in self._regular_section_data:
            lf.pack(fill="x", padx=5, pady=(3, 0))

        self._major_tags_status.config(text=f"HMM: {hmm_count}, Std: {regular_count}")

    def _save_major_tags(self):
        if not self._major_tags_filepath or (not self._hmm_section_data and not self._regular_section_data):
            messagebox.showerror("Erreur", "Chargez d'abord le fichier")
            return

        lines = []
        base = self._base_var.get().strip()
        if base:
            lines.append(f"BASE: {base}")
            lines.append("")

        for header, effect, txt in self._hmm_section_data:
            lines.append(header)
            content = txt.get("1.0", "end").strip()
            for tag in content.split("\n"):
                tag = tag.strip()
                if tag:
                    lines.append(tag)
            lines.append("")

        for header, effect, txt, lf in self._regular_section_data:
            lines.append(header)
            content = txt.get("1.0", "end").strip()
            for tag in content.split("\n"):
                tag = tag.strip()
                if tag:
                    lines.append(tag)
            lines.append("")

        with open(self._major_tags_filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        self._major_tags_status.config(text="Sauvegardé !")
        messagebox.showinfo("OK", "00_major_tags.txt sauvegardé")

