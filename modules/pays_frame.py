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

        self._law_groups = {}
        self._law_vars = {}
        self._current_law_file = ""

        self._parse_laws()

        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=10)

        ttk.Label(top, text="TAG :").pack(side="left")
        self._mod_tag = tk.StringVar()
        ttk.Entry(top, textvariable=self._mod_tag, width=8).pack(side="left", padx=5)
        ttk.Button(top, text="Charger pays", command=self._load_country_laws).pack(side="left", padx=5)
        self._mod_status = ttk.Label(top, text="")
        self._mod_status.pack(side="left", padx=10)

        canvas = tk.Canvas(f, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        self._law_scroll_frame = ttk.Frame(canvas)

        self._law_scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._law_scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        self._build_law_grid()

        ttk.Button(f, text="Appliquer les lois", command=self._apply_laws).pack(pady=8)

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

        groups = sorted(self._law_groups.keys())
        col_frame = None
        for i, group in enumerate(groups):
            if i % 10 == 0:
                col_frame = ttk.Frame(self._law_scroll_frame)
                col_frame.pack(side="left", padx=10, anchor="n")
            row = ttk.Frame(col_frame)
            row.pack(anchor="w", pady=2)
            ttk.Label(row, text=group, font=("Segoe UI", 8)).pack(anchor="w")
            var = tk.StringVar()
            self._law_vars[group] = var
            options = [""] + self._law_groups[group]
            om = ttk.OptionMenu(row, var, *options)
            om.config(width=30)
            om.pack(anchor="w")

    def _load_country_laws(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
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
            self._law_vars[g].set("")
        for law in laws_found:
            for group, values in self._law_groups.items():
                if law in values:
                    self._law_vars[group].set(law)

        self._mod_status.config(text=f"Chargé: {os.path.basename(file_path)}")

    def _apply_laws(self):
        if not self._current_law_file:
            messagebox.showerror("Erreur", "Charge d'abord un pays")
            return
        new_laws = [v.get() for v in self._law_vars.values() if v.get()]
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

    def _tab_tech(self, nb):
        f = TechFrame(nb, self.config)
        nb.add(f, text="Technologie")

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
