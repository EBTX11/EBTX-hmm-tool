import tkinter as tk
from tkinter import ttk, messagebox
import os
import re


class TechFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        ttk.Label(self, text="Mise a jour des Technologies", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        info = ttk.Label(self, text=(
            "Lit 00_major_tags.txt dans le dossier history/countries du mod\n"
            "et applique le bon effet de technologie de depart pour chaque pays."
        ), justify="center", font=("Segoe UI", 9))
        info.pack(pady=5)

        ttk.Button(self, text="Lancer la mise a jour des techs", command=self._run_tech).pack(pady=12)

        self._log = tk.Text(self, height=20, state="disabled", font=("Consolas", 9))
        self._log.pack(fill="both", expand=True, padx=15, pady=8)

    def _log_write(self, msg):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _run_tech(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        countries_folder = os.path.join(mod, "common/history/countries")
        tier_tags_file = os.path.join(countries_folder, "00_major_tags.txt")

        if not os.path.exists(countries_folder):
            messagebox.showerror("Erreur", f"Dossier countries introuvable:\n{countries_folder}")
            return
        if not os.path.exists(tier_tags_file):
            messagebox.showerror("Erreur", f"Fichier 00_major_tags.txt introuvable:\n{tier_tags_file}")
            return

        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

        tier_tags, default_effect = self._load_tiers(tier_tags_file)
        total = sum(len(v) for cat in tier_tags.values() for v in cat.values())
        self._log_write(f"{total} tags charges depuis 00_major_tags.txt")
        if default_effect:
            self._log_write(f"Default: {default_effect}")

        files = 0
        modified = 0
        for fname in os.listdir(countries_folder):
            if fname.endswith(".txt") and fname != "00_major_tags.txt":
                fpath = os.path.join(countries_folder, fname)
                result = self._process_file(fpath, tier_tags, default_effect)
                files += 1
                if result:
                    modified += 1

        self._log_write("---")
        self._log_write(f"Fichiers lus: {files} | Modifies: {modified}")
        messagebox.showinfo("Termine", f"{modified}/{files} fichiers mis a jour")

    def _load_tiers(self, filepath):
        tiers = {
            "hmm": {i: set() for i in range(1, 7)},
            "vanilla": {i: set() for i in range(1, 7)},
        }
        default_effect = None
        current_type = None
        current_tier = None

        with open(filepath, "r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                upper = raw.upper()
                if not raw:
                    continue
                if upper.startswith("BASE:"):
                    default_effect = raw.split("BASE:", 1)[1].strip()
                    continue
                if upper.startswith("#"):
                    if "_TECH_HMM" in upper:
                        current_type = "hmm"
                    elif "_TECH" in upper:
                        current_type = "vanilla"
                    else:
                        current_type = None
                    tier_match = re.search(r'TIER_(\d)', upper)
                    current_tier = int(tier_match.group(1)) if tier_match else None
                    continue
                if current_type and current_tier:
                    tag = upper.strip()
                    if re.match(r'^[A-Z]{3}$', tag) or re.match(r'^Y\d{2}$', tag):
                        tiers[current_type][current_tier].add(tag)

        return tiers, default_effect

    def _process_file(self, filepath, tier_tags, default_effect):
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        original = content

        match = re.search(r'c:\s*([A-Z]{3}|Y\d{2})\s*\??\s*=\s*{', content)
        if not match:
            return 0

        tag = match.group(1)

        # Supprimer les anciennes techs
        content = re.sub(r'effect_starting_technology_[^\n]+', '', content)
        content = re.sub(r'\n\s*\n+', '\n', content)

        # Determiner le tier
        tier = None
        mode = None
        for t, tags in tier_tags["hmm"].items():
            if tag in tags:
                tier = t
                mode = "hmm"
                break
        if tier is None:
            for t, tags in tier_tags["vanilla"].items():
                if tag in tags:
                    tier = t
                    mode = "vanilla"
                    break

        if tier and mode == "hmm":
            new_line = f"effect_starting_technology_tier_{tier}_tech_hmm = yes"
            status = f"HMM TIER {tier}"
        elif tier and mode == "vanilla":
            new_line = f"effect_starting_technology_tier_{tier}_tech = yes"
            status = f"VANILLA TIER {tier}"
        else:
            new_line = default_effect if default_effect else "effect_starting_technology_tier_5_tech = yes"
            status = "DEFAULT"

        content = re.sub(
            r'(c:\s*(?:[A-Z]{3}|Y\d{2})\s*\??\s*=\s*{)',
            r'\1\n        ' + new_line,
            content,
            count=1
        )

        self._log_write(f"{tag} -> {status}")

        if content != original:
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
            return 1
        return 0
