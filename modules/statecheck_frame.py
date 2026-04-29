"""
State Check Frame - Outil de vérification des provinces dans state_regions
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import shutil


class StateCheckFrame(ttk.Frame):
    """Frame pour l'outil State Check - Vérification des provinces."""

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _get_mod_map_data_dir(self):
        """Retourne le chemin du dossier map_data du mod."""
        mod = self.config.mod_path
        if not mod:
            return None
        return os.path.join(mod, "map_data")

    def _get_state_regions_dir(self):
        """Retourne le chemin du dossier state_regions dans le mod."""
        map_data_dir = self._get_mod_map_data_dir()
        if not map_data_dir:
            return None
        return os.path.join(map_data_dir, "state_regions")

    def _build(self):
        """Construit l'interface du State Check."""
        # Titre
        ttk.Label(self, text="State Check", font=("Segoe UI", 15, "bold")).pack(pady=(20, 10))
        ttk.Label(self, text="Vérifie que les provinces de 00_states.txt\nsont présentes dans state_regions",
                  justify="center", font=("Segoe UI", 9)).pack(pady=(0, 15))

        # Container principal
        main_container = ttk.Frame(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        # Bouton pour lancer le screening
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill="x", pady=(0, 10))
        
        self._sc_button = ttk.Button(btn_frame, text="Lancer le screening", 
                                      command=self._run_state_screening, style="Accent.TButton")
        self._sc_button.pack(side="left", padx=5)

        # Statut
        self._sc_status = ttk.Label(btn_frame, text="Cliquez sur 'Lancer le screening' pour analyser",
                                     font=("Segoe UI", 9), foreground="#89b4fa")
        self._sc_status.pack(side="left", padx=15)

        # Zone de résultats avec notebook
        self._results_notebook = ttk.Notebook(main_container)
        self._results_notebook.pack(fill="both", expand=True, pady=10)

        # Onglet 1 : Résumé
        self._summary_tab = ttk.Frame(self._results_notebook)
        self._results_notebook.add(self._summary_tab, text="Résumé")
        
        summary_scroll = ttk.Scrollbar(self._summary_tab)
        summary_scroll.pack(side="right", fill="y")
        self._summary_listbox = tk.Listbox(self._summary_tab, font=("Consolas", 9), 
                                            yscrollcommand=summary_scroll.set)
        self._summary_listbox.pack(fill="both", expand=True)
        summary_scroll.config(command=self._summary_listbox.yview)

        # Onglet 2 : Détaillé
        self._detail_tab = ttk.Frame(self._results_notebook)
        self._results_notebook.add(self._detail_tab, text="Détaillé")
        
        detail_scroll = ttk.Scrollbar(self._detail_tab)
        detail_scroll.pack(side="right", fill="y")
        self._detail_listbox = tk.Listbox(self._detail_tab, font=("Consolas", 8), 
                                           yscrollcommand=detail_scroll.set)
        self._detail_listbox.pack(fill="both", expand=True)
        detail_scroll.config(command=self._detail_listbox.yview)

        # Panneau du bas - Options et Actions
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill="x", pady=(10, 0))

        # Options
        opt_frame = ttk.LabelFrame(bottom_frame, text="Options")
        opt_frame.pack(side="left", fill="y", padx=(0, 20))
        
        self._sc_backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Sauvegarde automatique", 
                        variable=self._sc_backup_var).pack(anchor="w", padx=10, pady=5)

        # Statistiques
        stats_frame = ttk.LabelFrame(bottom_frame, text="Statistiques")
        stats_frame.pack(side="left", fill="y", padx=(0, 20))
        
        self._sc_stats_label = ttk.Label(stats_frame, text="Déplacer: 0 | Ajouter: 0 | Manquants: 0",
                                          font=("Segoe UI", 9))
        self._sc_stats_label.pack(padx=10, pady=5)

        # Chemins (affichés après le screening)
        self._sc_paths_label = ttk.Label(stats_frame, text="Chemins non analysés",
                                          font=("Segoe UI", 8), foreground="#6c7086", wraplength=200)
        self._sc_paths_label.pack(padx=10, pady=(5, 0))

        # Boutons appliquer - Deux boutons séparés
        # Style pour bouton déplacer (orange)
        style = ttk.Style()
        style.configure("Move.TButton", background="#f9e2af", foreground="#1e1e2e", 
                        font=("Segoe UI", 9, "bold"))
        style.map("Move.TButton", background=[("active", "#f5d76e")])
        
        # Style pour bouton ajouter (vert)
        style.configure("Add.TButton", background="#a6e3a1", foreground="#1e1e2e", 
                        font=("Segoe UI", 9, "bold"))
        style.map("Add.TButton", background=[("active", "#94e3a1")])
        
        # Bouton Déplacer (gauche) - modifie 00_states.txt
        self._sc_move_button = ttk.Button(bottom_frame, text="Déplacer dans 00_states.txt",
                                            command=self._move_provinces,
                                            state="disabled", style="Move.TButton")
        self._sc_move_button.pack(side="right", padx=5)
        
        # Bouton Ajouter (droite) - modifie state_regions
        self._sc_add_button = ttk.Button(bottom_frame, text="Ajouter à state_regions",
                                           command=self._add_provinces,
                                           state="disabled", style="Add.TButton")
        self._sc_add_button.pack(side="right", padx=5)

        # Variables pour stocker les résultats
        self._sc_missing_provinces = {}
        self._sc_orphelines = {}
        self._sc_missing_states = set()

    def _run_state_screening(self):
        """Lance le screening des provinces avec analyse détaillée."""
        mod = self.config.mod_path
        if not mod:
            self._sc_status.config(text="Erreur: Configure le dossier mod dans Config", foreground="#f38ba8")
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
        self._sc_status.config(text="Analyse en cours...", foreground="#89b4fa")
        
        # Nettoyer les listbox
        self._summary_listbox.delete(0, "end")
        self._detail_listbox.delete(0, "end")

        # Parser 00_states.txt
        states_provinces = self._parse_states_provinces(states_path)
        
        # Parser state_regions - créer une map province -> état
        sr_provinces = self._parse_state_regions_provinces(sr_dir)

        # Debug: afficher quelques provinces de chaque fichier
        self._detail_listbox.insert("end", "=== DEBUG ===")
        self._detail_listbox.insert("end", f"mod: {mod}")
        self._detail_listbox.insert("end", f"00_states.txt: {states_path}")
        self._detail_listbox.insert("end", f"state_regions: {sr_dir}")
        
        # Afficher quelques provinces de 00_states.txt
        first_state = list(states_provinces.keys())[0] if states_provinces else None
        if first_state:
            sample_provs = list(states_provinces[first_state])[:3]
            self._detail_listbox.insert("end", f"Exemples de {first_state}: {sample_provs}")
        
        # Afficher quelques provinces de state_regions
        first_sr_state = list(sr_provinces.keys())[0] if sr_provinces else None
        if first_sr_state:
            sr_sample_provs = list(sr_provinces[first_sr_state])[:3]
            self._detail_listbox.insert("end", f"Exemples de {first_sr_state}: {sr_sample_provs}")
        
        # Créer une map {province: état} pour toutes les provinces dans state_regions
        prov_to_state_map = {}
        for state_name, provs in sr_provinces.items():
            for p in provs:
                prov_to_state_map[p] = state_name
        
        # Afficher le nombre de provinces dans la map
        self._detail_listbox.insert("end", f"Nombre de provinces dans map: {len(prov_to_state_map)}")
        
        # Test: vérifier si une province de 00_states existe dans la map
        if first_state and states_provinces.get(first_state):
            test_prov = list(states_provinces[first_state])[0]
            self._detail_listbox.insert("end", f"Test: {test_prov}")
            self._detail_listbox.insert("end", f"  existe dans map: {test_prov in prov_to_state_map}")
            
            # Test avec differentes variations
            test_prov_upper = test_prov.upper()
            test_prov_lower = test_prov.lower()
            self._detail_listbox.insert("end", f"  (upper) {test_prov_upper} existe: {test_prov_upper in prov_to_state_map}")
            self._detail_listbox.insert("end", f"  (lower) {test_prov_lower} existe: {test_prov_lower in prov_to_state_map}")
            
            if test_prov in prov_to_state_map:
                self._detail_listbox.insert("end", f"  -> état: {prov_to_state_map[test_prov]}")

        self._detail_listbox.insert("end", "")
        self._detail_listbox.insert("end", "=== ANALYSE ===")

        # Analyser chaque province dans 00_states.txt
        provinces_to_move = {}  # {state_name: {correct_state: [provinces]}}
        provinces_to_add = {}   # {state_name: [provinces]}
        missing_states = set()  # États dans 00_states.txt qui n'existent pas dans state_regions

        total_checked = 0
        total_provinces = 0

        for state_name, provs in states_provinces.items():
            total_checked += 1
            total_provinces += len(provs)

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

        # États présents dans state_regions mais absents de 00_states.txt
        states_only_in_sr = set(sr_provinces.keys()) - set(states_provinces.keys())

        # Afficher les résultats
        total_to_move = sum(len(provs) for states in provinces_to_move.values() for provs in states.values())
        total_to_add = sum(len(provs) for provs in provinces_to_add.values())
        total_missing = len(missing_states) + len(states_only_in_sr)

        # Summary
        self._summary_listbox.insert("end", f"=== RÉSUMÉ ===")
        self._summary_listbox.insert("end", f"États dans 00_states.txt: {total_checked}")
        self._summary_listbox.insert("end", f"Provinces dans 00_states.txt: {total_provinces}")
        self._summary_listbox.insert("end", f"États dans state_regions: {len(sr_provinces)}")
        total_sr_provs = sum(len(p) for p in sr_provinces.values())
        self._summary_listbox.insert("end", f"Provinces dans state_regions: {total_sr_provs}")
        self._summary_listbox.insert("end", "")
        self._summary_listbox.insert("end", f"Provinces à déplacer: {total_to_move}")
        self._summary_listbox.insert("end", f"Provinces à ajouter: {total_to_add}")
        self._summary_listbox.insert("end", f"États seulement dans 00_states.txt: {len(missing_states)}")
        self._summary_listbox.insert("end", f"États seulement dans state_regions: {len(states_only_in_sr)}")

        # Détail
        self._detail_listbox.insert("end", "=== PROVINCES À DÉPLACER ===")
        if provinces_to_move:
            for wrong_state in sorted(provinces_to_move.keys()):
                for correct_state in sorted(provinces_to_move[wrong_state].keys()):
                    provs = provinces_to_move[wrong_state][correct_state]
                    self._detail_listbox.insert("end", f"  {wrong_state} -> {correct_state}: {len(provs)} provinces")
                    for p in sorted(provs):
                        self._detail_listbox.insert("end", f"    - {p}")
        else:
            self._detail_listbox.insert("end", "  (Aucune)")

        self._detail_listbox.insert("end", "")
        self._detail_listbox.insert("end", "=== PROVINCES À AJOUTER ===")
        if provinces_to_add:
            for state_name in sorted(provinces_to_add.keys()):
                provs = provinces_to_add[state_name]
                self._detail_listbox.insert("end", f"  {state_name}: {len(provs)} provinces")
                for p in sorted(provs):
                    self._detail_listbox.insert("end", f"    + {p}")
        else:
            self._detail_listbox.insert("end", "  (Aucune)")

        self._detail_listbox.insert("end", "")
        self._detail_listbox.insert("end", "=== ÉTATS MANQUANTS ===")
        if missing_states or states_only_in_sr:
            for s in sorted(missing_states):
                self._detail_listbox.insert("end", f"  ! {s} (dans 00_states.txt)")
            for s in sorted(states_only_in_sr):
                self._detail_listbox.insert("end", f"  + {s} (dans state_regions)")
        else:
            self._detail_listbox.insert("end", "  (Aucun)")

        self._sc_missing_provinces = provinces_to_move

        # Construire une map {province_upper: tag} en parsant chaque create_state individuellement
        # Nécessaire car un état peut avoir plusieurs create_state avec des tags différents
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            states_content = fh.read()

        prov_to_tag = {}  # {province_upper: tag}
        _prov_pat = re.compile(r'\b[xX][0-9A-Fa-f]{6}\b')
        _cs_pat = re.compile(r'create_state\s*=\s*\{')

        for sm in re.finditer(r's:(STATE_\w+)\s*=\s*\{', states_content):
            start = sm.end()
            depth, i = 1, start
            while i < len(states_content) and depth > 0:
                if states_content[i] == "{": depth += 1
                elif states_content[i] == "}": depth -= 1
                i += 1
            state_block = states_content[start:i - 1]

            # Parcourir chaque create_state du bloc
            for cs_m in _cs_pat.finditer(state_block):
                cs_start = cs_m.end()
                depth2, j = 1, cs_start
                while j < len(state_block) and depth2 > 0:
                    if state_block[j] == "{": depth2 += 1
                    elif state_block[j] == "}": depth2 -= 1
                    j += 1
                cs_block = state_block[cs_start:j - 1]

                country_match = re.search(r'country\s*=\s*(c:\w+)', cs_block)
                if not country_match:
                    continue
                tag = country_match.group(1)

                for pm in _prov_pat.finditer(cs_block):
                    prov_to_tag[pm.group(0).upper()] = tag

        # Construire provinces_to_move_with_tags en groupant par tag d'origine réel
        # Structure: {source_state: {target_state: {tag: [provinces]}}}
        provinces_to_move_with_tags = {}
        for source_state, data in provinces_to_move.items():
            for target_state, provs in data.items():
                for prov in provs:
                    tag = prov_to_tag.get(prov.upper(), "UNKNOWN")
                    provinces_to_move_with_tags \
                        .setdefault(source_state, {}) \
                        .setdefault(target_state, {}) \
                        .setdefault(tag, []) \
                        .append(prov)
        
        self._sc_missing_provinces_with_tags = provinces_to_move_with_tags
        self._sc_orphelines = provinces_to_add
        self._sc_missing_states = missing_states

        # Mettre à jour le statut et les boutons
        if total_to_move > 0:
            self._sc_move_button.config(state="normal")
            self._sc_status.config(text=f"Prêt: {total_to_move} provinces à déplacer", 
                                    foreground="#f9e2af")
        else:
            self._sc_move_button.config(state="disabled")
        
        if total_to_add > 0:
            self._sc_add_button.config(state="normal")
            if total_to_move == 0:
                self._sc_status.config(text=f"Prêt: {total_to_add} provinces à ajouter", 
                                        foreground="#a6e3a1")
        else:
            self._sc_add_button.config(state="disabled")
        
        if total_to_move == 0 and total_to_add == 0:
            if total_missing > 0:
                self._sc_status.config(text=f"Terminé - {total_missing} état(s) manquants",
                                        foreground="#f9e2af")
            else:
                self._sc_status.config(text="Analyse terminée - Tout est OK !",
                                        foreground="#a6e3a1")

        self._sc_stats_label.config(
            text=f"Déplacer: {total_to_move} | Ajouter: {total_to_add} | "
                 f"00_states seul: {len(missing_states)} | SR seul: {len(states_only_in_sr)}"
        )
        
        # Mettre à jour le label des chemins
        backup_path = sr_dir + "_backup" if self._sc_backup_var.get() else "Désactivée"
        self._sc_paths_label.config(
            text=f"00_states: ...states/00_states.txt\nstate_regions: ...map_data/state_regions\nSauvegarde: {backup_path}",
            foreground="#89b4fa"
        )
        
        self._sc_button.config(state="normal")

    def _parse_states_provinces(self, states_path):
        """Parse 00_states.txt et retourne un dict {state_name: set_of_provinces}."""
        result = {}
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()

        # Regex pour provinces sans guillemets (détecte x et X)
        prov_pat = re.compile(r'\b[xX][0-9A-Fa-f]{6}\b', re.IGNORECASE)
        
        debug_provs = []
        
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
                # Simpler: just take the whole match and uppercase it
                p = pm.group(0).upper()
                provs.add(p)
                
                # Debug: collect first few provinces from first state
                if len(debug_provs) < 10 and not result:
                    debug_provs.append(p)

            if provs:
                result[state] = provs

        # Debug output
        if debug_provs:
            print(f"[DEBUG] First provinces from 00_states.txt: {debug_provs}")
        
        return result

    def _parse_state_regions_provinces(self, sr_dir):
        """Parse les fichiers state_regions et retourne un dict {state_name: set_of_provinces}."""
        result = {}
        # Regex pour provinces avec ou sans guillemets (détecte x et X)
        prov_pat = re.compile(r'"?[xX]([0-9A-Fa-f]{6})"?', re.IGNORECASE)
        state_pat = re.compile(r'^(STATE_\w+)\s*=\s*\{', re.MULTILINE)
        
        debug_provs = []

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
                    # Take group(1) to get just the hex part, then add x and uppercase
                    hex_part = pm.group(1)
                    p = "X" + hex_part.upper()  # Force uppercase X prefix
                    provs.add(p)
                    
                    # Debug: collect first few provinces from first state
                    if len(debug_provs) < 10 and not result:
                        debug_provs.append(p)

                result[state] = provs

        # Debug output
        if debug_provs:
            print(f"[DEBUG] First provinces from state_regions: {debug_provs}")
            
        return result

    def _apply_state_corrections(self):
        """Applique les corrections en ajoutant les provinces manquantes aux fichiers state_regions."""
        if not self._sc_missing_provinces and not self._sc_orphelines:
            return

        mod = self.config.mod_path
        sr_dir = self._get_state_regions_dir()

        if not mod or not sr_dir or not os.path.exists(sr_dir):
            self._sc_status.config(text="Erreur: Dossiers non configurés", foreground="#f38ba8")
            return

        # Compter les fichiers qui seront modifiés
        files_to_modify = set()
        for state_name, data in self._sc_missing_provinces.items():
            for correct_state in data.keys():
                fpath = self._find_state_regions_file(sr_dir, correct_state)
                if fpath:
                    files_to_modify.add(os.path.basename(fpath))
        
        for state_name in self._sc_orphelines.keys():
            fpath = self._find_state_regions_file(sr_dir, state_name)
            if fpath:
                files_to_modify.add(os.path.basename(fpath))
        
        total_provs = sum(len(provs) for states in self._sc_missing_provinces.values() for provs in states.values())
        total_provs += sum(len(provs) for provs in self._sc_orphelines.values())
        
        # Confirmation détaillée
        confirm = messagebox.askyesno("Confirmer", 
            f"Fichiers state_regions qui seront modifiés ({len(files_to_modify)} fichiers):\n"
            + ", ".join(sorted(files_to_modify)[:5]) + ("..." if len(files_to_modify) > 5 else "") + f"\n\n"
            f"Nombre de provinces à ajouter: {total_provs}\n"
            f"Fichiers modifiés: {sr_dir}")
        if not confirm:
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
            self._summary_listbox.insert("end", "")
            self._summary_listbox.insert("end", f"Sauvegarde créée: {backup_dir}")

        # Appliquer les corrections pour provinces_to_move
        corrections_made = 0

        for state_name, data in self._sc_missing_provinces.items():
            for correct_state, provs in data.items():
                file_path = self._find_state_regions_file(sr_dir, correct_state)
                if not file_path:
                    self._detail_listbox.insert("end", f"ATTENTION: {correct_state} non trouvé")
                    continue
                self._add_provinces_to_state(file_path, correct_state, provs)
                corrections_made += len(provs)

        # Appliquer les corrections pour provinces_orphelines
        for state_name, provs in self._sc_orphelines.items():
            file_path = self._find_state_regions_file(sr_dir, state_name)
            if not file_path:
                self._detail_listbox.insert("end", f"ATTENTION: {state_name} non trouvé")
                continue
            self._add_provinces_to_state(file_path, state_name, provs)
            corrections_made += len(provs)

        self._sc_status.config(text=f"Corrections appliquées: {corrections_made} provinces", 
                                foreground="#a6e3a1")
        self._sc_apply_button.config(state="disabled")

        messagebox.showinfo("State Check", 
            f"{corrections_made} province(s) ajoutée(s) aux fichiers state_regions.\n"
            f"Sauvegardes créées si cochée.")

    @staticmethod
    def _fmt_prov(p):
        """Normalise une province au format du fichier : x minuscule + hex majuscule (ex: x26DB64)."""
        return 'x' + p[1:].upper()

    def _add_provinces_with_tag(self, content, state_name, provinces, tag):
        """Ajoute les provinces à un état dans 00_states.txt avec le bon tag country.

        Si l'état a déjà un create_state avec ce tag, ajoute les provinces à owned_provinces.
        Sinon, crée un nouveau create_state avec le tag et les provinces.
        """
        prov_pat = re.compile(r'\b[xX][0-9A-Fa-f]{6}\b')

        # Trouver le bloc de l'état
        state_match = re.search(rf's:{state_name}\s*=\s*\{{', content)
        if not state_match:
            return content

        block_start = state_match.end()
        depth, i = 1, block_start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1

        state_block = content[block_start:i-1]

        # Chercher s'il y a déjà un create_state avec ce tag
        # Pattern: create_state = { country = c:XXX
        create_state_pattern = re.compile(r'create_state\s*=\s*\{[^}]*country\s*=\s*' + re.escape(tag), re.DOTALL)
        existing_create = create_state_pattern.search(state_block)
        
        if existing_create:
            # Ajouter les provinces au create_state existant
            # Trouver le bloc du create_state
            cs_start = block_start + existing_create.start()
            cs_block_start = block_start + existing_create.end()
            
            # Trouver la fin du create_state
            depth_cs, k = 1, cs_block_start
            while k < i and depth_cs > 0:
                if content[k] == "{": depth_cs += 1
                elif content[k] == "}": depth_cs -= 1
                k += 1
            
            # Chercher owned_provinces dans ce create_state
            create_subblock = content[cs_block_start:k-1]
            owned_match = re.search(r'owned_provinces\s*=\s*\{', create_subblock)
            
            if owned_match:
                # Ajouter les provinces à owned_provinces existant
                prov_start = cs_block_start + owned_match.end()
                
                # Trouver la fin de la liste de provinces
                depth2, j = 1, prov_start
                while j < k and depth2 > 0:
                    if content[j] == "{": depth2 += 1
                    elif content[j] == "}": depth2 -= 1
                    j += 1
                
                # Extraire les provinces existantes
                existing_provs_block = content[prov_start:j-1]
                
                # Parser les provinces existantes
                existing_set = set()
                for pm in prov_pat.finditer(existing_provs_block):
                    existing_set.add(pm.group(0).upper())
                
                # Ajouter les provinces manquantes
                provs_to_add = []
                for p in provinces:
                    if p.upper() not in existing_set:
                        provs_to_add.append(self._fmt_prov(p))

                if not provs_to_add:
                    return content

                # Ajouter les nouvelles provinces
                new_provs_str = " " + " ".join(provs_to_add) + " "
                new_content = content[:prov_start] + new_provs_str + existing_provs_block + content[j-1:]

                return new_content
            else:
                # owned_provinces n'existe pas, le créer
                new_provs = " " + " ".join(self._fmt_prov(p) for p in provinces) + " "
                new_content = content[:k-1] + "\n\t\towned_provinces = {" + new_provs + "}\n" + content[k-1:]
                return new_content
        else:
            # Créer un nouveau create_state juste après s:STATE_XXX = {
            # Détecter l'indentation depuis les blocs create_state existants dans le fichier
            indent_match = re.search(r'\n([ \t]*)create_state', content[block_start:i])
            indent = indent_match.group(1) if indent_match else '\t\t\t'
            inner = indent + '\t'

            new_create = (
                f'\n{indent}create_state = {{\n'
                f'{inner}country = {tag}\n'
                f'{inner}owned_provinces = {{ {" ".join(self._fmt_prov(p) for p in provinces)} }}\n'
                f'{indent}}}'
            )

            new_content = content[:block_start] + new_create + content[block_start:]
            return new_content

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

            self._detail_listbox.insert("end", f"+ {state_name}: {len(new_provs)} provinces ajoutées")

    def _move_provinces(self):
        """Déplace les provinces dans 00_states.txt (état source -> état cible)."""
        if not self._sc_missing_provinces_with_tags:
            return

        mod = self.config.mod_path
        if not mod:
            self._sc_status.config(text="Erreur: Dossier mod non configuré", foreground="#f38ba8")
            return

        states_path = os.path.join(mod, "common/history/states/00_states.txt")
        
        if not os.path.exists(states_path):
            self._sc_status.config(text="Erreur: 00_states.txt introuvable", foreground="#f38ba8")
            return

        # Compter les provinces à déplacer (avec la structure enrichie)
        total_to_move = sum(len(provs) for data in self._sc_missing_provinces_with_tags.values() 
                          for tags_data in data.values() 
                          for provs in tags_data.values())
        
        # Confirmation détaillée
        states_list = []
        for wrong_state, data in self._sc_missing_provinces_with_tags.items():
            for correct_state, tags_data in data.items():
                for tag, provs in tags_data.items():
                    states_list.append(f"{wrong_state} -> {correct_state} [{tag}]: {len(provs)} provinces")
        
        confirm = messagebox.askyesno("Confirmer", 
            f"Provinces à déplacer dans 00_states.txt:\n"
            + "\n".join(states_list[:10]) + ("..." if len(states_list) > 10 else "") + f"\n\n"
            f"Nombre total de provinces: {total_to_move}\n"
            f"Fichier modifié: {states_path}")
        if not confirm:
            return

        # Sauvegarde de 00_states.txt
        if self._sc_backup_var.get():
            backup_path = states_path + "_backup"
            shutil.copy2(states_path, backup_path)
            self._summary_listbox.insert("end", "")
            self._summary_listbox.insert("end", f"Sauvegarde 00_states.txt: {backup_path}")

        # Lire le fichier
        with open(states_path, "r", encoding="utf-8-sig") as fh:
            content = fh.read()

        # Pour chaque déplacement avec les tags
        corrections_made = 0
        for wrong_state, data in self._sc_missing_provinces_with_tags.items():
            for correct_state, tags_data in data.items():
                for tag, provs in tags_data.items():
                    # Supprimer les provinces de l'état source
                    content = self._remove_provinces_from_state(content, wrong_state, provs)
                    # Ajouter les provinces à l'état cible avec le bon tag
                    content = self._add_provinces_with_tag(content, correct_state, provs, tag)
                    corrections_made += len(provs)
                    
                    self._detail_listbox.insert("end", f"-> {wrong_state} -> {correct_state} [{tag}]: {len(provs)} provinces déplacées")

        # Écrire le fichier modifié
        with open(states_path, "w", encoding="utf-8-sig") as fh:
            fh.write(content)

        self._sc_status.config(text=f"Déplacement terminé: {corrections_made} provinces", 
                                foreground="#f9e2af")
        self._sc_move_button.config(state="disabled")

        messagebox.showinfo("State Check", 
            f"{corrections_made} province(s) déplacée(s) dans 00_states.txt.\n"
            f"Sauvegarde créée si cochée.")

    def _remove_provinces_from_state(self, content, state_name, provinces):
        """Supprime les provinces spécifiées d'un état dans 00_states.txt.

        Opère sur l'ensemble du bloc d'état pour gérer les états avec
        plusieurs blocs create_state (chacun ayant son propre owned_provinces).
        """
        state_match = re.search(rf's:{state_name}\s*=\s*\{{', content)
        if not state_match:
            return content

        block_start = state_match.end()
        depth, i = 1, block_start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1
        block_end = i - 1

        state_block = content[block_start:block_end]
        result_block = state_block

        for prov in provinces:
            prov_upper = prov.upper()
            # Supprime la province partout dans le bloc (word boundary, insensible à la casse)
            result_block = re.sub(r'\b' + re.escape(prov_upper) + r'\b', '', result_block, flags=re.IGNORECASE)

        # Nettoyer les espaces doubles (sans toucher aux tabs d'indentation en début de ligne)
        result_block = re.sub(r'[ ]{2,}', ' ', result_block)
        result_block = re.sub(r' $', '', result_block, flags=re.MULTILINE)

        return content[:block_start] + result_block + content[block_end:]

    def _add_provinces_to_state_in_states(self, content, state_name, provinces):
        """Ajoute les provinces à un état dans 00_states.txt."""
        prov_pat = re.compile(r'\bx[0-9A-Fa-f]{6}\b')
        
        # Trouver le bloc de l'état
        state_match = re.search(rf's:{state_name}\s*=\s*\{{', content)
        if not state_match:
            return content
            
        block_start = state_match.end()
        depth, i = 1, block_start
        while i < len(content) and depth > 0:
            if content[i] == "{": depth += 1
            elif content[i] == "}": depth -= 1
            i += 1
        
        state_block = content[block_start:i-1]
        
        # Trouver la ligne "owned_provinces = {"
        owned_match = re.search(r'owned_provinces\s*=\s*\{', state_block)
        if not owned_match:
            # Créer la section si elle n'existe pas
            create_match = re.search(r'create_state\s*=\s*\{', state_block)
            if create_match:
                # Trouver la fin du create_state
                create_start = block_start + create_match.end()
                depth3, k = 1, create_start
                while k < i and depth3 > 0:
                    if content[k] == "{": depth3 += 1
                    elif content[k] == "}": depth3 -= 1
                    k += 1
                
                # Insérer owned_provinces avant la fermeture
                new_provs = " " + " ".join(provinces) + " "
                new_content = content[:k-1] + "\n\t\towned_provinces = {" + new_provs + "}\n" + content[k-1:]
                return new_content
            return content
            
        prov_start = block_start + owned_match.end()
        
        # Trouver la fin de la liste de provinces
        depth2, j = 1, prov_start
        while j < i and depth2 > 0:
            if content[j] == "{": depth2 += 1
            elif content[j] == "}": depth2 -= 1
            j += 1
        
        # Extraire les provinces existantes
        existing_provs_block = content[prov_start:j-1]
        
        # Parser les provinces existantes
        existing_set = set()
        for pm in prov_pat.finditer(existing_provs_block):
            existing_set.add(pm.group(0).upper())
        
        # Ajouter les provinces manquantes
        provs_to_add = []
        for p in provinces:
            if p.upper() not in existing_set:
                provs_to_add.append(p)
        
        if not provs_to_add:
            return content
        
        # Ajouter les nouvelles provinces
        new_provs_str = " " + " ".join(provs_to_add) + " "
        new_content = content[:prov_start] + new_provs_str + existing_provs_block + content[j-1:]
        
        return new_content

    def _add_provinces(self):
        """Ajoute les provinces aux fichiers state_regions."""
        if not self._sc_orphelines:
            return

        mod = self.config.mod_path
        sr_dir = self._get_state_regions_dir()

        if not mod or not sr_dir or not os.path.exists(sr_dir):
            self._sc_status.config(text="Erreur: Dossiers non configurés", foreground="#f38ba8")
            return

        # Compter les fichiers qui seront modifiés
        files_to_modify = set()
        for state_name in self._sc_orphelines.keys():
            fpath = self._find_state_regions_file(sr_dir, state_name)
            if fpath:
                files_to_modify.add(os.path.basename(fpath))
        
        total_provs = sum(len(provs) for provs in self._sc_orphelines.values())
        
        # Confirmation détaillée
        confirm = messagebox.askyesno("Confirmer", 
            f"Fichiers state_regions qui seront modifiés ({len(files_to_modify)} fichiers):\n"
            + ", ".join(sorted(files_to_modify)[:5]) + ("..." if len(files_to_modify) > 5 else "") + f"\n\n"
            f"Nombre de provinces à ajouter: {total_provs}\n"
            f"Fichiers modifiés: {sr_dir}")
        if not confirm:
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
            self._summary_listbox.insert("end", "")
            self._summary_listbox.insert("end", f"Sauvegarde state_regions: {backup_dir}")

        # Appliquer les corrections pour provinces_orphelines
        corrections_made = 0

        for state_name, provs in self._sc_orphelines.items():
            file_path = self._find_state_regions_file(sr_dir, state_name)
            if not file_path:
                self._detail_listbox.insert("end", f"ATTENTION: {state_name} non trouvé")
                continue
            self._add_provinces_to_state(file_path, state_name, provs)
            corrections_made += len(provs)

        self._sc_status.config(text=f"Ajout terminé: {corrections_made} provinces", 
                                foreground="#a6e3a1")
        self._sc_add_button.config(state="disabled")

        messagebox.showinfo("State Check", 
            f"{corrections_made} province(s) ajoutée(s) aux fichiers state_regions.\n"
            f"Sauvegardes créées si cochée.")
