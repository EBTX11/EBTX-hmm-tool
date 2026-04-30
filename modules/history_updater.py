"""
Redistribution des pops et batiments lors d'un changement de possession d'état.

Logique :
- Chaque état modifié a un ou plusieurs nouveaux propriétaires (tags)
- La proportion attribuée à chaque tag = nb provinces tag / nb provinces totales de l'état
- Les pops (par culture) et les niveaux de bâtiments sont redistribués proportionnellement
- Les arrondis sont gérés en distribuant le reste aux tags ayant la plus grande partie fractionnaire
- Le total de pops/levels reste identique au total original
"""

import os
import re
import shutil


# ─────────────────────────────────────────────────────────────
# UTILITAIRES
# ─────────────────────────────────────────────────────────────

def _block_end(content, start):
    """Retourne l'index juste après le } fermant.
    'start' doit être la position juste après le { ouvrant."""
    depth, i = 1, start
    while i < len(content) and depth > 0:
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
        i += 1
    return i


def _distribute(total, proportions):
    """Distribue un entier 'total' entre les tags selon leurs proportions.
    Retourne {tag: amount} avec sum(values) == total.
    Le reste est réparti aux tags avec la plus grande partie fractionnaire."""
    if not proportions or total <= 0:
        return {t: 0 for t in proportions}
    tags = list(proportions.keys())
    floats = {t: total * proportions[t] for t in tags}
    floors = {t: int(floats[t]) for t in tags}
    remainder = total - sum(floors.values())
    order = sorted(tags, key=lambda t: -(floats[t] - floors[t]))
    for i in range(remainder):
        floors[order[i % len(order)]] += 1
    return floors


# ─────────────────────────────────────────────────────────────
# PARSEURS
# ─────────────────────────────────────────────────────────────

def _parse_pops(state_inner):
    """Somme les populations par culture depuis tous les region_state d'un état.
    Retourne [(culture, total_size), ...] en préservant l'ordre de première apparition."""
    totals = {}   # culture -> size (ordered dict Python 3.7+)
    order = []
    for rs in re.finditer(r'region_state:\w+\s*=\s*\{', state_inner):
        rs_end = _block_end(state_inner, rs.end())
        rs_content = state_inner[rs.end():rs_end - 1]
        for pm in re.finditer(r'create_pop\s*=\s*\{', rs_content):
            pe = _block_end(rs_content, pm.end())
            pop = rs_content[pm.end():pe - 1]
            cm = re.search(r'culture\s*=\s*(\w+)', pop)
            sz = re.search(r'size\s*=\s*(\d+)', pop)
            if cm and sz:
                c = cm.group(1)
                if c not in totals:
                    order.append(c)
                    totals[c] = 0
                totals[c] += int(sz.group(1))
    return [(c, totals[c]) for c in order]


def _get_first_region_state(state_inner):
    """Extrait le TAG et le contenu brut du premier region_state trouvé dans un bloc d'état.
    Retourne (first_tag, raw_content_between_braces) ou (None, None) si absent."""
    sm = re.search(r'region_state:(\w+)\s*=\s*\{', state_inner)
    if not sm:
        return None, None
    first_tag = sm.group(1)
    end_pos = _block_end(state_inner, sm.end())
    # Contenu brut entre { et } (avec indentation originale)
    first_content = state_inner[sm.end():end_pos - 1]
    return first_tag, first_content


# ─────────────────────────────────────────────────────────────
# CONSTRUCTEURS DE BLOCS
# ─────────────────────────────────────────────────────────────

def _write_pops_block(state_name, pops, proportions, ind):
    """Construit le bloc s:STATE = { region_state:TAG = { create_pop... } } pour les pops."""
    T = '\t'
    lines = [f"s:{state_name} = {{"]
    # Pré-calculer la distribution pour chaque culture
    dist = {culture: _distribute(size, proportions) for culture, size in pops}
    for tag in sorted(proportions):
        lines.append(f"{ind}{T}region_state:{tag} = {{")
        for culture, _ in pops:
            amt = dist[culture].get(tag, 0)
            if amt > 0:
                lines.append(f"{ind}{T}{T}create_pop = {{")
                lines.append(f"{ind}{T}{T}{T}culture = {culture}")
                lines.append(f"{ind}{T}{T}{T}size = {amt}")
                lines.append(f"{ind}{T}{T}}}")
        lines.append(f"{ind}{T}}}")
    lines.append(f"{ind}}}")
    return "\n".join(lines)


def _write_buildings_copy(state_name, first_tag, first_content, new_owners, ind):
    """Construit le bloc buildings par copie du premier region_state vers les nouveaux owners.

    Règles :
    - 1 owner  : copie le bloc en remplaçant c:first_tag → c:new_tag partout
    - N owners : copie le bloc verbatim pour chaque owner (sans toucher add_ownership)
    - 0 owner  : retourne le bloc vide (ne devrait pas arriver)
    """
    T = '\t'
    if not new_owners:
        return f"s:{state_name}={{\n{ind}}}"

    out = f"s:{state_name}={{\n"
    for new_tag in sorted(new_owners):
        content = first_content.replace(f"c:{first_tag}", f"c:{new_tag}")
        out += f"{ind}{T}region_state:{new_tag}={{{content}}}\n"
    out += f"{ind}}}"
    return out


# ─────────────────────────────────────────────────────────────
# MISE À JOUR D'UN FICHIER
# ─────────────────────────────────────────────────────────────

def _update_file(path, modified_states, proportions_map, new_owners_map, file_type):
    """Réécrit les blocs d'états modifiés dans un fichier pops ou buildings.
    Retourne True si le fichier a été modifié."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    parts = []
    i = 0
    changed = False
    while i < len(content):
        sm = re.search(r's:(STATE_\w+)\s*=\s*\{', content[i:])
        if not sm:
            parts.append(content[i:])
            break
        state = sm.group(1)
        start = i + sm.start()
        block_start = i + sm.end()
        j = _block_end(content, block_start)
        if state in modified_states:
            inner = content[block_start:j - 1]
            before = content[i:start]
            last_nl = before.rfind('\n')
            ind = before[last_nl + 1:] if last_nl >= 0 else ''
            if file_type == 'pops' and state in proportions_map:
                data = _parse_pops(inner)
                new_block = _write_pops_block(state, data, proportions_map[state], ind)
                parts.append(content[i:start])
                parts.append(new_block)
                changed = True
            elif file_type == 'buildings' and state in new_owners_map:
                first_tag, first_content = _get_first_region_state(inner)
                if first_tag is not None:
                    new_block = _write_buildings_copy(
                        state, first_tag, first_content, new_owners_map[state], ind)
                    parts.append(content[i:start])
                    parts.append(new_block)
                    changed = True
                else:
                    parts.append(content[i:j])
            else:
                parts.append(content[i:j])
        else:
            parts.append(content[i:j])
        i = j
    if changed:
        _bkdir = os.path.join(os.path.dirname(path), "_backup")
        os.makedirs(_bkdir, exist_ok=True)
        shutil.copy(path, os.path.join(_bkdir, os.path.basename(path)))
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(''.join(parts))
    return changed


# ─────────────────────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────

def update_history_files(mod_path, modified_states, substates):
    """
    Met à jour les fichiers pops et buildings pour tous les états modifiés.

    Args:
        mod_path      : chemin vers le dossier racine du mod
        modified_states : set de noms d'états (ex: {"STATE_TEXAS"})
        substates     : dict {(state, tag): set_of_prov_hex} courant de map_frame

    Retourne le nombre de fichiers effectivement modifiés.
    """
    if not modified_states:
        return 0

    proportions_map = {}   # pour pops  : {state: {tag: ratio}}
    new_owners_map  = {}   # pour buildings : {state: [tag, ...]}

    for state in modified_states:
        tag_counts = {}
        for (s, tag), provs in substates.items():
            if s == state and provs:
                tag_counts[tag] = len(provs)
        total = sum(tag_counts.values())
        if total > 0:
            proportions_map[state] = {t: c / total for t, c in tag_counts.items()}
            new_owners_map[state]  = sorted(tag_counts.keys())

    if not proportions_map and not new_owners_map:
        return 0

    updated = 0
    for folder, ftype in [
        (os.path.join(mod_path, 'common', 'history', 'pops'), 'pops'),
        (os.path.join(mod_path, 'common', 'history', 'buildings'), 'buildings'),
    ]:
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith('.txt'):
                continue
            if _update_file(os.path.join(folder, fname), modified_states,
                            proportions_map, new_owners_map, ftype):
                updated += 1

    return updated
