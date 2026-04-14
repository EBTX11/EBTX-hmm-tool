import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
from collections import defaultdict


class ProvinceFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        ttk.Label(self, text="Outils Provinces", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        self._tab_verification(nb)
        self._tab_correction(nb)
        self._tab_search(nb)

    # ----------------------------------------------------------
    # UTILITAIRE PARTAGEE
    # ----------------------------------------------------------

    def _make_log(self, parent):
        log = tk.Text(parent, height=12, state="disabled", font=("Consolas", 9))
        log.pack(fill="both", expand=True, padx=15, pady=8)
        return log

    def _log_write(self, log, msg):
        log.configure(state="normal")
        log.insert("end", msg + "\n")
        log.see("end")
        log.configure(state="disabled")

    def _log_clear(self, log):
        log.configure(state="normal")
        log.delete("1.0", "end")
        log.configure(state="disabled")

    # ----------------------------------------------------------
    # TAB 1 : VERIFICATION DES PROVINCES
    # ----------------------------------------------------------

    def _tab_verification(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Verification  ")

        info = ttk.Label(f, text=(
            "Verifie que les provinces dans history/states/\n"
            "correspondent aux state_regions du mod ou vanilla."
        ), justify="center")
        info.pack(pady=10)

        row = ttk.Frame(f)
        row.pack(fill="x", padx=15, pady=5)
        ttk.Label(row, text="Dossier state_regions:", width=22).pack(side="left")
        self._veri_regions_path = tk.StringVar()
        ttk.Entry(row, textvariable=self._veri_regions_path, width=40).pack(side="left")
        ttk.Button(row, text="...", width=3,
                   command=lambda: self._browse_dir(self._veri_regions_path)).pack(side="left", padx=3)

        row2 = ttk.Frame(f)
        row2.pack(fill="x", padx=15, pady=5)
        ttk.Label(row2, text="Fichier 00_states.txt:", width=22).pack(side="left")
        self._veri_states_path = tk.StringVar()
        ttk.Entry(row2, textvariable=self._veri_states_path, width=40).pack(side="left")
        ttk.Button(row2, text="...", width=3,
                   command=lambda: self._browse_file(self._veri_states_path)).pack(side="left", padx=3)

        ttk.Button(f, text="Lancer la verification", command=self._run_verification).pack(pady=8)
        self._veri_log = self._make_log(f)

    def _run_verification(self):
        regions_folder = self._veri_regions_path.get()
        states_file = self._veri_states_path.get()

        if not regions_folder or not states_file:
            messagebox.showerror("Erreur", "Selectionne les deux chemins")
            return
        if not os.path.isdir(regions_folder) or not os.path.isfile(states_file):
            messagebox.showerror("Erreur", "Chemins invalides")
            return

        self._log_clear(self._veri_log)

        # Charger les provinces valides depuis state_regions
        region_provinces = defaultdict(set)
        state_pattern = re.compile(r'(STATE_[A-Z_]+)\s*=\s*{')
        provinces_pattern = re.compile(r'"(x[0-9A-F]{6})"', re.IGNORECASE)
        current_state = None

        for fname in os.listdir(regions_folder):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(regions_folder, fname), encoding="utf-8") as fh:
                for line in fh:
                    sm = state_pattern.search(line)
                    if sm:
                        current_state = sm.group(1)
                    if "provinces" in line and current_state:
                        for p in provinces_pattern.findall(line):
                            region_provinces[current_state].add(p.upper())

        self._log_write(self._veri_log, f"{len(region_provinces)} state_regions charges")

        # Verifier history states
        state_history_pattern = re.compile(r's:(STATE_[A-Z_]+)\s*=\s*{')
        province_pattern = re.compile(r'x[0-9A-F]{6}', re.IGNORECASE)

        with open(states_file, encoding="utf-8") as fh:
            content = fh.read()

        errors = 0
        current_state = None
        for line in content.split("\n"):
            sm = state_history_pattern.search(line)
            if sm:
                current_state = sm.group(1)
            provs = province_pattern.findall(line)
            for p in provs:
                p = p.upper()
                if current_state and p not in region_provinces.get(current_state, set()):
                    self._log_write(self._veri_log, f"ERREUR: {p} dans {current_state} mais pas dans state_regions")
                    errors += 1

        if errors == 0:
            self._log_write(self._veri_log, "Aucune erreur detectee !")
        else:
            self._log_write(self._veri_log, f"\n{errors} province(s) incorrecte(s) detectee(s)")

    # ----------------------------------------------------------
    # TAB 2 : CORRECTION AUTOMATIQUE
    # ----------------------------------------------------------

    def _tab_correction(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Correction  ")

        info = ttk.Label(f, text=(
            "Supprime les provinces mal assignees dans 00_states.txt\n"
            "et genere un fichier corrige."
        ), justify="center")
        info.pack(pady=10)

        row = ttk.Frame(f)
        row.pack(fill="x", padx=15, pady=5)
        ttk.Label(row, text="Dossier state_regions:", width=22).pack(side="left")
        self._corr_regions_path = tk.StringVar()
        ttk.Entry(row, textvariable=self._corr_regions_path, width=40).pack(side="left")
        ttk.Button(row, text="...", width=3,
                   command=lambda: self._browse_dir(self._corr_regions_path)).pack(side="left", padx=3)

        row2 = ttk.Frame(f)
        row2.pack(fill="x", padx=15, pady=5)
        ttk.Label(row2, text="Fichier 00_states.txt:", width=22).pack(side="left")
        self._corr_states_path = tk.StringVar()
        ttk.Entry(row2, textvariable=self._corr_states_path, width=40).pack(side="left")
        ttk.Button(row2, text="...", width=3,
                   command=lambda: self._browse_file(self._corr_states_path)).pack(side="left", padx=3)

        row3 = ttk.Frame(f)
        row3.pack(fill="x", padx=15, pady=5)
        ttk.Label(row3, text="Fichier de sortie:", width=22).pack(side="left")
        self._corr_output_path = tk.StringVar()
        ttk.Entry(row3, textvariable=self._corr_output_path, width=40).pack(side="left")
        ttk.Button(row3, text="...", width=3,
                   command=lambda: self._browse_save(self._corr_output_path)).pack(side="left", padx=3)

        ttk.Button(f, text="Corriger les provinces", command=self._run_correction).pack(pady=8)
        self._corr_log = self._make_log(f)

    def _run_correction(self):
        regions_folder = self._corr_regions_path.get()
        states_file = self._corr_states_path.get()
        output_file = self._corr_output_path.get()

        if not all([regions_folder, states_file, output_file]):
            messagebox.showerror("Erreur", "Selectionne tous les chemins")
            return

        self._log_clear(self._corr_log)

        # Charger la verite depuis state_regions
        province_to_state = {}
        state_pattern = re.compile(r'(STATE_[A-Z_]+)\s*=\s*{')
        provinces_pattern = re.compile(r'"(x[0-9A-F]{6})"', re.IGNORECASE)
        current_state = None

        for fname in os.listdir(regions_folder):
            if not fname.endswith(".txt"):
                continue
            with open(os.path.join(regions_folder, fname), encoding="utf-8") as fh:
                for line in fh:
                    sm = state_pattern.search(line)
                    if sm:
                        current_state = sm.group(1)
                    if "provinces" in line and current_state:
                        for p in provinces_pattern.findall(line):
                            province_to_state[p.upper()] = current_state

        self._log_write(self._corr_log, f"{len(province_to_state)} provinces dans state_regions")

        # Corriger 00_states.txt
        state_history_pattern = re.compile(r's:(STATE_[A-Z_]+)\s*=\s*{')
        province_pattern = re.compile(r'x[0-9A-F]{6}', re.IGNORECASE)

        output_lines = []
        removed = 0
        current_state = None
        inside_provinces = False

        with open(states_file, encoding="utf-8") as fh:
            for line in fh:
                sm = state_history_pattern.search(line)
                if sm:
                    current_state = sm.group(1)

                if "owned_provinces" in line:
                    inside_provinces = True
                    output_lines.append(line)
                    continue

                if inside_provinces and "}" in line:
                    inside_provinces = False
                    output_lines.append(line)
                    continue

                if inside_provinces and current_state:
                    provs = province_pattern.findall(line)
                    valid = []
                    for p in provs:
                        pu = p.upper()
                        if pu not in province_to_state:
                            removed += 1
                            continue
                        if province_to_state[pu] != current_state:
                            removed += 1
                            continue
                        valid.append(p)
                    if valid:
                        output_lines.append("\t\t\t\t" + " ".join(valid) + "\n")
                    continue

                output_lines.append(line)

        with open(output_file, "w", encoding="utf-8") as fh:
            fh.writelines(output_lines)

        self._log_write(self._corr_log, f"{removed} province(s) supprimee(s)")
        self._log_write(self._corr_log, f"Fichier corrige: {os.path.basename(output_file)}")
        messagebox.showinfo("Termine", f"Correction terminee - {removed} provinces supprimees")

    # ----------------------------------------------------------
    # TAB 3 : RECHERCHE DE PROVINCES
    # ----------------------------------------------------------

    def _tab_search(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Recherche  ")

        info = ttk.Label(f, text=(
            "Compare les provinces entre deux fichiers Vic3.\n"
            "Trouve les provinces presentes dans l'un mais pas dans l'autre."
        ), justify="center")
        info.pack(pady=10)

        row = ttk.Frame(f)
        row.pack(fill="x", padx=15, pady=5)
        ttk.Label(row, text="Fichier reference:", width=20).pack(side="left")
        self._search_ref = tk.StringVar()
        ttk.Entry(row, textvariable=self._search_ref, width=42).pack(side="left")
        ttk.Button(row, text="...", width=3,
                   command=lambda: self._browse_file(self._search_ref)).pack(side="left", padx=3)

        row2 = ttk.Frame(f)
        row2.pack(fill="x", padx=15, pady=5)
        ttk.Label(row2, text="Fichier cible:", width=20).pack(side="left")
        self._search_target = tk.StringVar()
        ttk.Entry(row2, textvariable=self._search_target, width=42).pack(side="left")
        ttk.Button(row2, text="...", width=3,
                   command=lambda: self._browse_file(self._search_target)).pack(side="left", padx=3)

        ttk.Button(f, text="Comparer", command=self._run_search).pack(pady=8)
        self._search_log = self._make_log(f)

    def _run_search(self):
        ref_path = self._search_ref.get()
        target_path = self._search_target.get()

        if not ref_path or not target_path:
            messagebox.showerror("Erreur", "Selectionne les deux fichiers")
            return
        if not os.path.isfile(ref_path) or not os.path.isfile(target_path):
            messagebox.showerror("Erreur", "Fichiers invalides")
            return

        self._log_clear(self._search_log)

        prov_pattern = re.compile(r'x[0-9A-Fa-f]{6}')

        with open(ref_path, "r", encoding="utf-8") as fh:
            ref_provs = set(p.upper() for p in prov_pattern.findall(fh.read()))
        with open(target_path, "r", encoding="utf-8") as fh:
            target_provs = set(p.upper() for p in prov_pattern.findall(fh.read()))

        only_in_ref = ref_provs - target_provs
        only_in_target = target_provs - ref_provs
        common = ref_provs & target_provs

        self._log_write(self._search_log, f"Provinces en commun: {len(common)}")
        self._log_write(self._search_log, f"Uniquement dans reference ({len(only_in_ref)}):")
        for p in sorted(only_in_ref)[:50]:
            self._log_write(self._search_log, f"  {p}")
        if len(only_in_ref) > 50:
            self._log_write(self._search_log, f"  ... et {len(only_in_ref) - 50} de plus")
        self._log_write(self._search_log, f"\nUniquement dans cible ({len(only_in_target)}):")
        for p in sorted(only_in_target)[:50]:
            self._log_write(self._search_log, f"  {p}")
        if len(only_in_target) > 50:
            self._log_write(self._search_log, f"  ... et {len(only_in_target) - 50} de plus")

    # ----------------------------------------------------------
    # HELPERS NAVIGATION FICHIERS
    # ----------------------------------------------------------

    def _browse_dir(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def _browse_file(self, var):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            var.set(path)

    def _browse_save(self, var):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if path:
            var.set(path)
