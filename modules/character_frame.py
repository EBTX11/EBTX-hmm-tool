import tkinter as tk
from tkinter import ttk, messagebox
import os
import re


class CharacterFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._build()

    def _build(self):
        ttk.Label(self, text="Outils Personnages", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        self._tab_creer(nb)
        self._tab_nettoyer(nb)

    # ----------------------------------------------------------
    # TAB 1 : CREER UN PERSONNAGE
    # ----------------------------------------------------------

    def _tab_creer(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Creer personnage  ")

        form = ttk.LabelFrame(f, text="Nouveau personnage")
        form.pack(fill="x", padx=20, pady=15)

        fields = [
            ("Prenom (ex: Friedrich Wilhelm)", "first"),
            ("Nom de famille (ex: von Hohenzollern)", "last"),
            ("Date de naissance (YYYY.MM.DD)", "birth"),
        ]
        self._char = {}
        for label, key in fields:
            row = ttk.Frame(form)
            row.pack(fill="x", padx=10, pady=4)
            ttk.Label(row, text=label, width=34, anchor="w").pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var, width=30).pack(side="left")
            self._char[key] = var

        row = ttk.Frame(form)
        row.pack(fill="x", padx=10, pady=4)
        ttk.Label(row, text="Historique", width=34, anchor="w").pack(side="left")
        self._char["historical"] = tk.StringVar(value="yes")
        ttk.OptionMenu(row, self._char["historical"], "yes", "yes", "no").pack(side="left")

        row2 = ttk.Frame(form)
        row2.pack(fill="x", padx=10, pady=4)
        ttk.Label(row2, text="Genre", width=34, anchor="w").pack(side="left")
        self._char["gender"] = tk.StringVar(value="male")
        ttk.OptionMenu(row2, self._char["gender"], "male", "male", "female").pack(side="left")

        ttk.Button(f, text="Creer le personnage", command=self._generate_character).pack(pady=12)

    def _format_name(self, name):
        parts = name.strip().split()
        return "_".join(p.lower() for p in parts), " ".join(parts)

    def _generate_character(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        first = self._char["first"].get().strip()
        last = self._char["last"].get().strip()
        birth = self._char["birth"].get().strip()
        historical = self._char["historical"].get()
        gender = self._char["gender"].get()

        if not all([first, last, birth]):
            messagebox.showerror("Erreur", "Remplis tous les champs")
            return

        first_key, first_loc = self._format_name(first)
        last_key, last_loc = self._format_name(last)
        female_flag = "yes" if gender == "female" else "no"
        template_name = last_key.split("_")[-1] + "_character_template"

        char_file = os.path.join(mod, "common/character_templates/00_hmm_character_templates.txt")
        loc_file = os.path.join(mod, "localization/english/00_mm_character_template_l_english.yml")
        os.makedirs(os.path.dirname(char_file), exist_ok=True)
        os.makedirs(os.path.dirname(loc_file), exist_ok=True)

        char_block = f"""
{template_name} = {{
\tfirst_name = {first_key}
\tlast_name = {last_key}
\thistorical = {historical}
\tculture = primary_culture
\tfemale = {female_flag}
\tbirth_date = {birth}
}}
"""
        loc_block = f"\n {first_key}: \"{first_loc}\"\n {last_key}: \"{last_loc}\"\n"

        with open(char_file, "a", encoding="utf-8") as fh:
            fh.write(char_block)
        with open(loc_file, "a", encoding="utf-8") as fh:
            fh.write(loc_block)

        messagebox.showinfo("Succes", f"Personnage {first_loc} {last_loc} ajoute !")
        self._char["first"].set("")
        self._char["last"].set("")
        self._char["birth"].set("")

    # ----------------------------------------------------------
    # TAB 2 : NETTOYER LES PERSONNAGES
    # ----------------------------------------------------------

    def _tab_nettoyer(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Nettoyer personnages  ")

        info = ttk.Label(f, text=(
            "Vide les blocs de personnages (c:XXX) dans common/history/characters/\n"
            "en les remplacant par des blocs vides propres."
        ), justify="center")
        info.pack(pady=20)

        ttk.Button(f, text="Nettoyer les personnages", command=self._clean_characters).pack(pady=10)

        self._clean_log = tk.Text(f, height=10, state="disabled", font=("Consolas", 9))
        self._clean_log.pack(fill="both", expand=True, padx=15, pady=10)

    def _log(self, msg):
        self._clean_log.configure(state="normal")
        self._clean_log.insert("end", msg + "\n")
        self._clean_log.see("end")
        self._clean_log.configure(state="disabled")

    def _clean_block(self, content):
        i = 0
        result = ""
        while i < len(content):
            if content.startswith("c:", i):
                start = i
                while i < len(content) and content[i] != "{":
                    i += 1
                if i >= len(content):
                    break
                brace_count = 1
                i += 1
                while i < len(content) and brace_count > 0:
                    if content[i] == "{":
                        brace_count += 1
                    elif content[i] == "}":
                        brace_count -= 1
                    i += 1
                block = content[start:i]
                tag_match = re.match(r'c:(\w+)', block)
                tag_str = f"c:{tag_match.group(1)}" if tag_match else "c:???"
                result += f"{tag_str} ?= {{\n\t}}\n"
            else:
                result += content[i]
                i += 1
        return result

    def _clean_characters(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        characters_path = os.path.join(mod, "common", "history", "characters")
        if not os.path.exists(characters_path):
            messagebox.showerror("Erreur", f"Dossier introuvable:\n{characters_path}")
            return

        self._clean_log.configure(state="normal")
        self._clean_log.delete("1.0", "end")
        self._clean_log.configure(state="disabled")

        count = 0
        for fname in os.listdir(characters_path):
            if fname.endswith(".txt"):
                fpath = os.path.join(characters_path, fname)
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read()
                new_content = self._clean_block(content)
                with open(fpath, "w", encoding="utf-8") as fh:
                    fh.write(new_content)
                self._log(f"Nettoye: {fname}")
                count += 1

        self._log(f"\n{count} fichier(s) traite(s).")
        messagebox.showinfo("Termine", f"{count} fichier(s) nettoye(s) !")
