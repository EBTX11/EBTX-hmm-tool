import tkinter as tk
from tkinter import ttk, messagebox
import os
import re


TAG_PATTERN = r'[A-Z][A-Z0-9]{2}'


def extract_blocks(text, keyword):
    blocks = []
    i = 0
    while True:
        start = text.find(keyword, i)
        if start == -1:
            break
        brace_start = text.find("{", start)
        if brace_start == -1:
            break
        depth = 1
        j = brace_start + 1
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        blocks.append(text[start:j])
        i = j
    return blocks


class PopulationFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        ttk.Label(self, text="Outils Population", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        self._tab_balance(nb)
        self._tab_update_buildings(nb)

    # ----------------------------------------------------------
    # TAB 1 : BALANCE POPULATION
    # ----------------------------------------------------------

    def _tab_balance(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Balance population  ")

        self._pop_files = []
        self._pop_state_data = []
        self._pop_current_total = 0

        top = ttk.Frame(f)
        top.pack(fill="x", padx=15, pady=10)

        ttk.Label(top, text="TAG :").pack(side="left")
        self._pop_tag = tk.StringVar()
        ttk.Entry(top, textvariable=self._pop_tag, width=10).pack(side="left", padx=5)
        ttk.Button(top, text="Analyser", command=self._analyze_pop).pack(side="left", padx=5)

        self._pop_result = ttk.Label(f, text="Population totale: -", font=("Segoe UI", 11))
        self._pop_result.pack(pady=5)

        target_row = ttk.Frame(f)
        target_row.pack(pady=5)
        ttk.Label(target_row, text="Population cible:").pack(side="left")
        self._pop_target = tk.StringVar()
        ttk.Entry(target_row, textvariable=self._pop_target, width=18).pack(side="left", padx=5)
        ttk.Button(target_row, text="Appliquer", command=self._apply_pop).pack(side="left", padx=5)

        self._pop_log = tk.Text(f, height=8, state="disabled", font=("Consolas", 9))
        self._pop_log.pack(fill="both", expand=True, padx=15, pady=8)

    def _pop_log_write(self, msg):
        self._pop_log.configure(state="normal")
        self._pop_log.insert("end", msg + "\n")
        self._pop_log.see("end")
        self._pop_log.configure(state="disabled")

    def _load_pop_files(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return False
        pops_path = os.path.join(mod, "common", "history", "pops")
        if not os.path.exists(pops_path):
            messagebox.showerror("Erreur", f"Dossier pops introuvable:\n{pops_path}")
            return False
        self._pop_files = []
        for root, _, files in os.walk(pops_path):
            for fname in files:
                if fname.endswith(".txt"):
                    self._pop_files.append(os.path.join(root, fname))
        return True

    def _get_total_for_tag(self, tag):
        total = 0
        state_data = []
        for fpath in self._pop_files:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read()
            regions = extract_blocks(content, f"region_state:{tag}")
            for region in regions:
                pops = extract_blocks(region, "create_pop")
                pop_blocks = []
                state_total = 0
                for p in pops:
                    size_match = re.search(r"size\s*=\s*(\d+)", p)
                    if size_match:
                        size = int(size_match.group(1))
                        state_total += size
                        pop_blocks.append((p, size))
                if state_total > 0:
                    total += state_total
                    state_data.append((fpath, pop_blocks, state_total))
        return total, state_data

    def _analyze_pop(self):
        if not self._load_pop_files():
            return
        tag = self._pop_tag.get().strip().upper()
        if not tag:
            return
        total, data = self._get_total_for_tag(tag)
        if total == 0:
            messagebox.showerror("Erreur", f"Aucune population trouvee pour {tag}")
            return
        self._pop_current_total = total
        self._pop_state_data = data
        self._pop_result.config(text=f"Population totale: {total:,}")
        self._pop_log.configure(state="normal")
        self._pop_log.delete("1.0", "end")
        self._pop_log.configure(state="disabled")
        self._pop_log_write(f"TAG: {tag} | Total: {total:,} | Fichiers: {len(data)}")

    def _apply_pop(self):
        if not self._pop_current_total:
            messagebox.showerror("Erreur", "Analyse d'abord une population")
            return
        try:
            target = int(self._pop_target.get())
        except ValueError:
            messagebox.showerror("Erreur", "Cible invalide (nombre entier requis)")
            return

        ratio = target / self._pop_current_total
        file_contents = {}
        for fpath in self._pop_files:
            with open(fpath, "r", encoding="utf-8") as fh:
                file_contents[fpath] = fh.read()

        for fpath, pops, _ in self._pop_state_data:
            content = file_contents[fpath]
            for block, size in pops:
                new_size = max(1, int(size * ratio))
                new_block = re.sub(r"size\s*=\s*\d+", f"size = {new_size}", block)
                content = content.replace(block, new_block, 1)
            file_contents[fpath] = content

        for fpath, content in file_contents.items():
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(content)

        self._pop_log_write(f"Population ajustee: {self._pop_current_total:,} -> {target:,} (ratio {ratio:.3f})")
        messagebox.showinfo("Succes", f"Population ajustee a {target:,}")

    # ----------------------------------------------------------
    # TAB 2 : MISE A JOUR BATIMENTS/POPS
    # ----------------------------------------------------------

    def _tab_update_buildings(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Sync batiments/pops  ")

        info = ttk.Label(f, text=(
            "Synchronise les blocs region_state dans buildings/ et pops/\n"
            "selon les proprietaires definis dans history/states/00_states.txt"
        ), justify="center")
        info.pack(pady=15)

        ttk.Button(f, text="Lancer la synchronisation", command=self._run_sync).pack(pady=8)

        self._sync_log = tk.Text(f, height=14, state="disabled", font=("Consolas", 9))
        self._sync_log.pack(fill="both", expand=True, padx=15, pady=8)

    def _sync_log_write(self, msg):
        self._sync_log.configure(state="normal")
        self._sync_log.insert("end", msg + "\n")
        self._sync_log.see("end")
        self._sync_log.configure(state="disabled")

    def _run_sync(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        states_file = os.path.join(mod, "common/history/states/00_states.txt")
        buildings_folder = os.path.join(mod, "common/history/buildings")
        pops_folder = os.path.join(mod, "common/history/pops")

        for path in [states_file, buildings_folder, pops_folder]:
            if not os.path.exists(path):
                messagebox.showerror("Erreur", f"Introuvable:\n{path}")
                return

        self._sync_log.configure(state="normal")
        self._sync_log.delete("1.0", "end")
        self._sync_log.configure(state="disabled")

        # Charger les proprietaires d'etats
        state_owners = self._load_state_owners(states_file)
        self._sync_log_write(f"{len(state_owners)} states charges")

        # Traiter buildings et pops
        for folder_name, folder_path in [("buildings", buildings_folder), ("pops", pops_folder)]:
            count = 0
            for fname in os.listdir(folder_path):
                if fname.endswith(".txt"):
                    fpath = os.path.join(folder_path, fname)
                    self._process_sync_file(fpath, state_owners)
                    count += 1
            self._sync_log_write(f"{folder_name}: {count} fichier(s) traite(s)")

        messagebox.showinfo("Termine", "Synchronisation terminee !")

    def _load_state_owners(self, states_file):
        state_owners = {}
        with open(states_file, "r", encoding="utf-8") as fh:
            content = fh.read()

        for m in re.finditer(r's:(STATE_[A-Z0-9_]+)\s*=\s*{', content):
            state = m.group(1)
            start = m.end()
            brace = 1
            i = start
            while i < len(content):
                if content[i] == "{":
                    brace += 1
                elif content[i] == "}":
                    brace -= 1
                    if brace == 0:
                        break
                i += 1
            block = content[start:i]
            tags = re.findall(rf'country\s*=\s*c:({TAG_PATTERN})', block)
            if tags:
                state_owners[state] = list(dict.fromkeys(tags))
        return state_owners

    def _extract_region_blocks(self, block):
        results = []
        i = 0
        n = len(block)
        while i < n:
            match = re.search(rf'region_state:({TAG_PATTERN})\s*=\s*{{', block[i:])
            if not match:
                break
            tag = match.group(1)
            start = i + match.start()
            j = start + len(match.group(0)) - 1
            brace = 0
            k = j
            while k < n:
                if block[k] == "{":
                    brace += 1
                elif block[k] == "}":
                    brace -= 1
                    if brace == 0:
                        k += 1
                        break
                k += 1
            results.append((block[start:k], tag))
            i = k
        return results

    def _process_sync_file(self, filepath, state_owners):
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()

        result = ""
        i = 0
        n = len(content)

        while i < n:
            match = re.search(r's:(STATE_[A-Z0-9_]+)\s*=\s*{', content[i:])
            if not match:
                result += content[i:]
                break

            start = i + match.start()
            state = match.group(1)
            result += content[i:start]

            j = start + len(match.group(0)) - 1
            brace = 0
            k = j
            while k < n:
                if content[k] == "{":
                    brace += 1
                elif content[k] == "}":
                    brace -= 1
                    if brace == 0:
                        k += 1
                        break
                k += 1

            block = content[start:k]

            if state in state_owners:
                owners = state_owners[state]
                region_blocks = self._extract_region_blocks(block)

                model_block = None
                model_tag = None
                for full, tag in region_blocks:
                    if "create_" in full:
                        model_block = full
                        model_tag = tag
                        break

                cleaned = block
                for full, tag in region_blocks:
                    if tag not in owners:
                        cleaned = cleaned.replace(full, "")
                block = cleaned

                region_blocks = self._extract_region_blocks(block)
                existing_tags = [tag for _, tag in region_blocks]
                missing = [tag for tag in owners if tag not in existing_tags]

                insert = ""
                for tag in missing:
                    if model_block:
                        new_b = re.sub(rf'region_state:{TAG_PATTERN}', f'region_state:{tag}', model_block)
                        if model_tag:
                            new_b = re.sub(rf'c:{model_tag}', f'c:{tag}', new_b)
                    else:
                        new_b = f"region_state:{tag} = {{ }}"
                    insert += f"\n\t\t{new_b}"

                if insert:
                    block = block.rstrip()
                    if block.endswith("}"):
                        block = block[:-1] + insert + "\n\t}"

            result += block
            i = k

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(result)
