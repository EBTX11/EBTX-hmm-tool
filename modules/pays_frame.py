import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import random

from modules.tech_frame import TechFrame

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


# ============================================================
# UTILITAIRES PARTAGEES
# ============================================================

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


# ============================================================
# FRAME PRINCIPALE - PAYS
# ============================================================

class PaysFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        ttk.Label(self, text="Outils Pays", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        self._tab_creer(nb)
        self._tab_modifier(nb)
        self._tab_dyn_name(nb)
        self._tab_historique(nb)
        self._tab_tech(nb)

    # ----------------------------------------------------------
    # TAB 1 : CREER UN PAYS
    # ----------------------------------------------------------

    def _tab_creer(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Creer pays  ")

        form = ttk.LabelFrame(f, text="Nouveau pays")
        form.pack(fill="x", padx=20, pady=15)

        fields = [
            ("TAG (3 lettres)", "tag"),
            ("Nom du pays", "name"),
            ("Culture", "culture"),
            ("Capitale (STATE_XXX)", "capital"),
        ]

        self._cc = {}
        for label, key in fields:
            row = ttk.Frame(form)
            row.pack(fill="x", padx=10, pady=3)
            ttk.Label(row, text=label, width=22, anchor="w").pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var, width=30).pack(side="left")
            self._cc[key] = var

        row = ttk.Frame(form)
        row.pack(fill="x", padx=10, pady=3)
        ttk.Label(row, text="Type de pays", width=22, anchor="w").pack(side="left")
        self._cc["type"] = tk.StringVar(value="recognized")
        ttk.OptionMenu(row, self._cc["type"], "recognized",
                       "recognized", "unrecognized", "colonial", "decentralized").pack(side="left")

        ttk.Button(f, text="Creer le pays", command=self._create_country).pack(pady=10)

    def _create_country(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure d'abord le dossier mod (Config)")
            return

        tag = self._cc["tag"].get().upper().strip()
        name = self._cc["name"].get().strip()
        culture = self._cc["culture"].get().strip()
        capital = self._cc["capital"].get().strip()
        country_type = self._cc["type"].get()

        if not tag or not name:
            messagebox.showerror("Erreur", "TAG et Nom sont obligatoires")
            return
        if len(tag) != 3:
            messagebox.showerror("Erreur", "Le TAG doit contenir exactement 3 lettres")
            return

        country_def_path = os.path.join(mod, "common/country_definitions/99_hmm_countries.txt")
        if tag_exists(tag, country_def_path):
            messagebox.showerror("Erreur", f"Le TAG '{tag}' existe deja !")
            return

        r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
        color_str = f"{r} {g} {b}"

        # 1. country_definitions
        os.makedirs(os.path.dirname(country_def_path), exist_ok=True)
        block = f"""
{tag} = {{
\tcolor = {{ {color_str} }}
\tcountry_type = {country_type}
\ttier = kingdom
\tcultures = {{ {culture} }}
\tcapital = {capital}
}}
"""
        if os.path.exists(country_def_path):
            with open(country_def_path, "r", encoding="utf-8-sig") as fh:
                existing = fh.read()
            with open(country_def_path, "w", encoding="utf-8-sig") as fh:
                fh.write(block + "\n" + existing)
        else:
            with open(country_def_path, "w", encoding="utf-8-sig") as fh:
                fh.write(block)

        # 2. localisation
        loc_path = os.path.join(mod, "localization/english/00_hmm_countries_l_english.yml")
        os.makedirs(os.path.dirname(loc_path), exist_ok=True)
        loc_entry = f'  {tag}:0 "{name}"\n  {tag}_ADJ:0 "{name}"\n'
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as fh:
                existing = fh.read()
            with open(loc_path, "w", encoding="utf-8-sig") as fh:
                fh.write("l_english:\n" + loc_entry + existing.replace("l_english:\n", ""))
        else:
            with open(loc_path, "w", encoding="utf-8-sig") as fh:
                fh.write("l_english:\n" + loc_entry)

        # 3. history
        hist_path = os.path.join(mod, f"common/history/countries/{tag} - {name}.txt")
        os.makedirs(os.path.dirname(hist_path), exist_ok=True)
        with open(hist_path, "w", encoding="utf-8-sig") as fh:
            fh.write(f"COUNTRIES = {{\n\tc:{tag} = {{\n\t}}\n}}\n")

        messagebox.showinfo("Succes", f"{name} ({tag}) cree !\nCouleur: {color_str}")
        for v in self._cc.values():
            if isinstance(v, tk.StringVar) and v != self._cc["type"]:
                v.set("")

    # ----------------------------------------------------------
    # TAB 2 : MODIFIER LOIS D'UN PAYS
    # ----------------------------------------------------------

    def _tab_modifier(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Modifier lois  ")

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

        self._mod_status.config(text=f"Charge: {os.path.basename(file_path)}")

    def _apply_laws(self):
        if not self._current_law_file:
            messagebox.showerror("Erreur", "Charge d'abord un pays")
            return
        new_laws = [v.get() for v in self._law_vars.values() if v.get()]
        if not new_laws:
            messagebox.showerror("Erreur", "Aucune loi selectionnee")
            return

        tag = self._mod_tag.get().strip().upper()
        with open(self._current_law_file, "r", encoding="utf-8") as fh:
            content = fh.read()

        content = self._replace_laws(content, new_laws, tag)
        with open(self._current_law_file, "w", encoding="utf-8") as fh:
            fh.write(content)
        messagebox.showinfo("OK", "Lois mises a jour !")

    def _replace_laws(self, content, new_laws, tag):
        match = re.search(rf'c:{tag}\s*\??=\s*{{', content, re.IGNORECASE)
        if not match:
            return content
        start = match.end()
        brace = 1
        i = start
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

    # ----------------------------------------------------------
    # TAB 3 : NOM DYNAMIQUE
    # ----------------------------------------------------------

    def _tab_dyn_name(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Nom dynamique  ")

        form = ttk.LabelFrame(f, text="Ajouter un nom dynamique")
        form.pack(fill="x", padx=20, pady=15)

        row1 = ttk.Frame(form)
        row1.pack(fill="x", padx=10, pady=5)
        ttk.Label(row1, text="TAG", width=20, anchor="w").pack(side="left")
        self._dyn_tag = tk.StringVar()
        ttk.Entry(row1, textvariable=self._dyn_tag, width=15).pack(side="left")

        row2 = ttk.Frame(form)
        row2.pack(fill="x", padx=10, pady=5)
        ttk.Label(row2, text="Nom dynamique", width=20, anchor="w").pack(side="left")
        self._dyn_name = tk.StringVar()
        ttk.Entry(row2, textvariable=self._dyn_name, width=35).pack(side="left")

        ttk.Button(f, text="Ajouter nom dynamique", command=self._create_dyn_name).pack(pady=10)

    def _create_dyn_name(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return
        tag = self._dyn_tag.get().upper().strip()
        dyn_name = self._dyn_name.get().strip()
        if not tag or not dyn_name:
            messagebox.showerror("Erreur", "Champs obligatoires manquants")
            return

        dyn_path = os.path.join(mod, "common/dynamic_country_names/00_mm_dynamic_country_names.txt")
        os.makedirs(os.path.dirname(dyn_path), exist_ok=True)
        block = f"""
{tag} = {{
\tdynamic_country_name = {{
\t\tname = dyn_c_{tag}_01
\t\tadjective = {tag}_ADJ
\t\tis_main_tag_only = yes
\t\tpriority = 5
\t\ttrigger = {{
\t\t\thas_game_rule = historical_map_mod_enabled
\t\t}}
\t}}
}}
"""
        if os.path.exists(dyn_path):
            with open(dyn_path, "r", encoding="utf-8-sig") as fh:
                existing = fh.read()
            with open(dyn_path, "w", encoding="utf-8-sig") as fh:
                fh.write(block + "\n" + existing)
        else:
            with open(dyn_path, "w", encoding="utf-8-sig") as fh:
                fh.write(block)

        loc_path = os.path.join(mod, "localization/english/00_mm_countries_l_english.yml")
        os.makedirs(os.path.dirname(loc_path), exist_ok=True)
        loc_entry = f'  dyn_c_{tag}_01:0 "{dyn_name}"\n  {tag}_ADJ:0 "{dyn_name}"\n'
        if os.path.exists(loc_path):
            with open(loc_path, "r", encoding="utf-8-sig") as fh:
                existing = fh.read()
            existing = existing.replace("l_english:\n", "")
            with open(loc_path, "w", encoding="utf-8-sig") as fh:
                fh.write("l_english:\n" + loc_entry + existing)
        else:
            with open(loc_path, "w", encoding="utf-8-sig") as fh:
                fh.write("l_english:\n" + loc_entry)

        messagebox.showinfo("Succes", f"Nom dynamique ajoute pour {tag} !")
        self._dyn_tag.set("")
        self._dyn_name.set("")

    # ----------------------------------------------------------
    # TAB 4 : HISTORIQUE PAYS
    # ----------------------------------------------------------

    def _tab_historique(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Historique pays  ")

        info = ttk.Label(f, text="Genere un fichier historique pays depuis le template.", font=("Segoe UI", 9))
        info.pack(pady=(15, 5))

        tpl_path = os.path.join(DATA_DIR, "template_country.txt")
        tpl_info = ttk.Label(f, text=f"Template: {tpl_path}", font=("Segoe UI", 8), foreground="#888")
        tpl_info.pack()

        row = ttk.Frame(f)
        row.pack(fill="x", padx=20, pady=15)
        ttk.Label(row, text="TAG", width=12, anchor="w").pack(side="left")
        self._hist_tag = tk.StringVar()
        ttk.Entry(row, textvariable=self._hist_tag, width=15).pack(side="left")

        ttk.Button(f, text="Generer historique", command=self._generate_history).pack(pady=8)
        self._hist_status = ttk.Label(f, text="")
        self._hist_status.pack()

    def _generate_history(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord")
            return

        tag = self._hist_tag.get().strip().upper()
        if not tag:
            messagebox.showerror("Erreur", "Entre un TAG")
            return

        tpl_path = os.path.join(DATA_DIR, "template_country.txt")
        if not os.path.exists(tpl_path):
            messagebox.showerror("Erreur", "template_country.txt introuvable dans data/")
            return

        with open(tpl_path, "r", encoding="utf-8") as fh:
            template = fh.read()

        if "{TAG}" not in template:
            messagebox.showerror("Erreur", "Le template ne contient pas {TAG}")
            return

        # Recuperer le nom du pays depuis la localisation
        country_name = tag
        loc_file = os.path.join(mod, "localization", "english", "00_hmm_countries_l_english.yml")
        if os.path.exists(loc_file):
            with open(loc_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    if f"{tag}:" in line:
                        parts = line.split('"')
                        if len(parts) >= 2:
                            country_name = parts[1]
                        break

        target_dir = os.path.join(mod, "common", "history", "countries")
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"{tag} - {country_name}.txt")

        if os.path.exists(file_path):
            if not messagebox.askyesno("Attention", f"Le fichier existe deja. Ecraser ?"):
                return

        content = template.replace("{TAG}", tag)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        self._hist_status.config(text=f"Cree: {os.path.basename(file_path)}")
        messagebox.showinfo("Succes", f"Fichier historique cree !")
        self._hist_tag.set("")

    # ----------------------------------------------------------
    # TAB 5 : TECHNOLOGIE
    # ----------------------------------------------------------

    def _tab_tech(self, nb):
        f = TechFrame(nb, self.config)
        nb.add(f, text="  Technologie  ")
