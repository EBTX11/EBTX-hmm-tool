import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import shutil

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TARGET_HISTORY = os.path.join("common", "history", "global", "99_ef_history_global_variable.txt")
TARGET_TRIGGER = os.path.join("common", "scripted_triggers", "00_ef_custom_trigger.txt")

YEARS = ["1804", "1837", "1861", "1871", "1890", "1919"]
LAWS = [
    "law_fiat_standard",
    "law_silver_standard",
    "law_bimetallism_standard",
    "law_gold_standard",
    "law_gold_exchange_standard",
    "law_external_exchange_standard",
]


def load_currency_map():
    mapping = {}
    path = os.path.join(DATA_DIR, "currency_map.txt")
    if not os.path.exists(path):
        return mapping
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                tag, cur = line.split("=", 1)
                mapping[tag.strip().upper()] = cur.strip()
    return mapping


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


class CurrencyFrame(ttk.Frame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self._currency_map = load_currency_map()
        self._build()

    def _build(self):
        ttk.Label(self, text="Editeur de Devises", font=("Segoe UI", 15, "bold")).pack(pady=(18, 5))

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=20, pady=5)

        left = ttk.LabelFrame(main, text="Pays et annee")
        left.pack(side="left", fill="y", padx=(0, 10), pady=5)

        fields_left = [
            ("TAG du pays", "tag"),
            ("Devise detectee", "currency"),
        ]
        self._v = {}
        for label, key in fields_left:
            row = ttk.Frame(left)
            row.pack(fill="x", padx=8, pady=4)
            ttk.Label(row, text=label, width=18, anchor="w").pack(side="left")
            var = tk.StringVar()
            e = ttk.Entry(row, textvariable=var, width=22)
            if key == "currency":
                e.config(state="readonly")
            else:
                var.trace_add("write", self._update_currency)
            e.pack(side="left")
            self._v[key] = var

        row = ttk.Frame(left)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="Annee", width=18, anchor="w").pack(side="left")
        self._v["year"] = tk.StringVar(value="1871")
        ttk.OptionMenu(row, self._v["year"], "1871", *YEARS).pack(side="left")

        row = ttk.Frame(left)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="Loi monetaire", width=18, anchor="w").pack(side="left")
        self._v["law"] = tk.StringVar(value=LAWS[1])
        ttk.OptionMenu(row, self._v["law"], LAWS[1], *LAWS).pack(side="left")

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=5, pady=6)

        row = ttk.Frame(left)
        row.pack(fill="x", padx=8, pady=2)
        ttk.Label(row, text="Trigger present", width=18, anchor="w").pack(side="left")
        self._v["trigger_status"] = tk.StringVar(value="---")
        ttk.Label(row, textvariable=self._v["trigger_status"], foreground="#888").pack(side="left")

        self._add_trigger_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Ajouter au trigger banque centrale",
                        variable=self._add_trigger_var).pack(padx=8, pady=4, anchor="w")

        right = ttk.LabelFrame(main, text="Parametres economiques")
        right.pack(side="left", fill="both", expand=True, pady=5)

        num_fields = [
            ("Money min", "money_min", "15"),
            ("Money max", "money_max", "30"),
            ("Circulating min", "circ_min", "50000000"),
            ("Circulating max", "circ_max", "100000000"),
            ("Base index min", "base_min", "100"),
            ("Base index max", "base_max", "300"),
            ("Ratio stockpile", "stockpile", "0.1"),
        ]
        for label, key, default in num_fields:
            row = ttk.Frame(right)
            row.pack(fill="x", padx=8, pady=3)
            ttk.Label(row, text=label, width=20, anchor="w").pack(side="left")
            var = tk.StringVar(value=default)
            ttk.Entry(row, textvariable=var, width=18).pack(side="left")
            self._v[key] = var

        ttk.Button(self, text="VALIDER les modifications", command=self._apply,
                   style="Accent.TButton").pack(pady=12)
        self._status = ttk.Label(self, text="")
        self._status.pack()

    def _update_currency(self, *_):
        tag = self._v["tag"].get().upper()
        currency = self._currency_map.get(tag, "UNKNOWN")
        self._v["currency"].set(currency)
        self._check_trigger()

    def _check_trigger(self):
        mod = self.config.mod_path
        if not mod:
            return
        path = os.path.join(mod, TARGET_TRIGGER)
        if not os.path.exists(path):
            self._v["trigger_status"].set("NO FILE")
            return
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        tag = self._v["tag"].get().upper()
        year = self._v["year"].get()
        pattern = rf"#\s*{year}.*?OR\s*=\s*{{.*?c:{tag}\s*\?=\s*this"
        found = bool(re.search(pattern, content, re.DOTALL))
        self._v["trigger_status"].set("OUI" if found else "NON")

    def _apply(self):
        mod = self.config.mod_path
        if not mod:
            messagebox.showerror("Erreur", "Configure le dossier mod d'abord (Config)")
            return

        file_path = os.path.join(mod, TARGET_HISTORY)
        if not os.path.exists(file_path):
            messagebox.showerror("Erreur", f"Fichier introuvable:\n{file_path}")
            return

        _bkdir = os.path.join(os.path.dirname(file_path), "_backup")
        os.makedirs(_bkdir, exist_ok=True)
        shutil.copy(file_path, os.path.join(_bkdir, os.path.basename(file_path)))

        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        tag = self._v["tag"].get().upper()
        currency = self._v["currency"].get()
        year = self._v["year"].get()
        law = self._v["law"].get()

        match = re.search(rf"(#\s*{year}.*?if\s*=\s*{{)(.*?)(\n\s*\}})", content, re.DOTALL)
        if not match:
            messagebox.showerror("Erreur", f"Bloc annee {year} introuvable")
            return

        prefix, inner, suffix = match.groups()

        limit_match = re.search(r"limit\s*=\s*{", inner)
        if not limit_match:
            messagebox.showerror("Erreur", "Bloc limit introuvable")
            return

        insert_pos = find_block_end(inner, limit_match.start()) + 1
        currency_law = f"law_{currency}_currency"
        stockpile = self._v["stockpile"].get()
        is_gold = (law == "law_gold_standard")

        metal_var = "gold" if is_gold else "silver"
        other_var = "silver" if is_gold else "gold"
        other_calc = (
            f"add = var:gold_state_1\n" if is_gold else
            f"add = {{\n                                value = var:silver_state_1\n"
            f"                                multiply = silver_to_gold_rate\n                            }}\n"
        )

        stockpile_var = (
            f"""
                    var:central_bank_location = {{
                        change_variable = {{
                            name = stockpiling_{currency}_state_1
                            add = {{
                                value = owner.var:circulating_{currency}_c_var_1
                                multiply = {stockpile}
                            }}
                        }}
                        change_variable = {{
                            name = {metal_var}_state_1
                            add = {{
                                value = owner.var:circulating_{currency}_c_var_1
                                add = var:stockpiling_{currency}_state_1
                                add = owner.building_saving
                                multiply = owner.var:money_value_target_1
                            }}
                        }}
                        change_variable = {{
                            name = {other_var}_state_1
                            add = {{
                                value = var:{metal_var}_state_1
                                multiply = silver_to_gold_rate
                            }}
                        }}
                    }}
"""
        )

        new_block = f"""
                # {currency}
                if = {{
                    limit = {{
                        c:{tag}?= this
                    }}

                    activate_law = law_type:{currency_law}
                    activate_law = law_type:{law}

                    set_variable = {{
                        name = money_value_target_1
                        value = {{ {self._v["money_min"].get()} {self._v["money_max"].get()} }}
                    }}

                    change_variable = {{
                        name = circulating_{currency}_c_var_1
                        add = {{ {self._v["circ_min"].get()} {self._v["circ_max"].get()} }}
                    }}
{stockpile_var}
                    set_variable = {{
                        name = base_index_value
                        value = {{ {self._v["base_min"].get()} {self._v["base_max"].get()} }}
                    }}
                }}
"""
        inner = inner[:insert_pos] + new_block + inner[insert_pos:]
        new_year = prefix + inner + suffix
        content = content.replace(match.group(0), new_year)

        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)

        if self._add_trigger_var.get():
            self._update_trigger(mod, tag, year)

        self._status.config(text=f"Modifie avec succes - backup cree")
        messagebox.showinfo("OK", "Modifications appliquees !")

    def _update_trigger(self, mod, tag, year):
        path = os.path.join(mod, TARGET_TRIGGER)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        hmm_start = re.search(r"is_valid_country_hmm\s*=\s*{", content)
        if not hmm_start:
            return

        hmm_end = find_block_end(content, hmm_start.start())
        hmm_block = content[hmm_start.start():hmm_end + 1]

        year_match = re.search(rf"#\s*{year}", hmm_block)
        if not year_match:
            return

        year_start = year_match.start()
        next_year = re.search(r"\n\s*#", hmm_block[year_start + 1:])
        year_end = year_start + 1 + next_year.start() if next_year else len(hmm_block)
        year_block = hmm_block[year_start:year_end]

        and_match = re.search(r"\bAND\s*=\s*{", year_block)
        if not and_match:
            return
        end_and = find_block_end(year_block, and_match.start())
        and_block = year_block[and_match.start():end_and + 1]

        or_match = re.search(r"\bOR\s*=\s*{", and_block)
        if not or_match:
            return

        if f"c:{tag}" in and_block:
            return

        insert = f"\n                c:{tag} ?= this"
        new_and_block = and_block[:or_match.end()] + insert + and_block[or_match.end():]
        new_year_block = year_block.replace(and_block, new_and_block)
        new_hmm_block = hmm_block.replace(year_block, new_year_block)
        content = content.replace(hmm_block, new_hmm_block)

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
