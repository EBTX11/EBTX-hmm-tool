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


def _parse_buildings(state_inner):
    """Somme les niveaux de bâtiments depuis tous les region_state d'un état.
    Retourne [(name, {level, reserves, has_reserves, extras}), ...] en ordre d'apparition."""
    result = {}
    order = []
    for rs in re.finditer(r'region_state:\w+\s*=\s*\{', state_inner):
        rs_end = _block_end(state_inner, rs.end())
        rs_content = state_inner[rs.end():rs_end - 1]
        for bm in re.finditer(r'create_building\s*=\s*\{', rs_content):
            be = _block_end(rs_content, bm.end())
            b = rs_content[bm.end():be - 1]
            nm = re.search(r'\bbuilding\s*=\s*(\w+)', b)
            lm = re.search(r'\blevel\s*=\s*(\d+)', b)
            if not nm or not lm:
                continue
            name = nm.group(1)
            level = int(lm.group(1))
            rm = re.search(r'\breserves\s*=\s*(\d+)', b)
            reserves = int(rm.group(1)) if rm else 0
            if name not in result:
                order.append(name)
                result[name] = {'level': 0, 'reserves': 0, 'has_reserves': False, 'extras': []}
            result[name]['level'] += level
            result[name]['reserves'] += reserves
            if rm:
                result[name]['has_reserves'] = True
            # Capturer activate_production_methods et autres blocs supplémentaires
            for apm in re.finditer(r'activate_production_methods\s*=\s*\{', b):
                ae = _block_end(b, apm.end())
                apm_str = b[apm.start():ae].strip()
                if apm_str not in result[name]['extras']:
                    result[name]['extras'].append(apm_str)
    return [(n, result[n]) for n in order]


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


def _write_buildings_block(state_name, buildings, proportions, ind):
    """Construit le bloc s:STATE = { region_state:TAG = { create_building... } } pour les bâtiments."""
    T = '\t'
    lines = [f"s:{state_name} = {{"]
    for tag in sorted(proportions):
        lines.append(f"{ind}{T}region_state:{tag} = {{")
        for name, data in buildings:
            lvl_dist = _distribute(data['level'], proportions)
            res_dist = _distribute(data['reserves'], proportions)
            lvl = lvl_dist.get(tag, 0)
            if lvl <= 0:
                continue
            lines.append(f"{ind}{T}{T}create_building = {{")
            lines.append(f"{ind}{T}{T}{T}building = {name}")
            lines.append(f"{ind}{T}{T}{T}level = {lvl}")
            if data['has_reserves']:
                lines.append(f"{ind}{T}{T}{T}reserves = {res_dist.get(tag, 0)}")
            for extra in data['extras']:
                lines.append(f"{ind}{T}{T}{T}{extra}")
            lines.append(f"{ind}{T}{T}}}")
        lines.append(f"{ind}{T}}}")
    lines.append(f"{ind}}}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# MISE À JOUR D'UN FICHIER
# ─────────────────────────────────────────────────────────────

def _update_file(path, modified_states, proportions_map, file_type):
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
        if state in modified_states and state in proportions_map:
            inner = content[block_start:j - 1]
            # Détecter l'indentation du s:STATE dans ce fichier
            before = content[i:start]
            last_nl = before.rfind('\n')
            ind = before[last_nl + 1:] if last_nl >= 0 else ''
            props = proportions_map[state]
            if file_type == 'pops':
                data = _parse_pops(inner)
                new_block = _write_pops_block(state, data, props, ind)
            else:
                data = _parse_buildings(inner)
                new_block = _write_buildings_block(state, data, props, ind)
            parts.append(content[i:start])
            parts.append(new_block)
            changed = True
        else:
            parts.append(content[i:j])
        i = j
    if changed:
        shutil.copy(path, path + '.backup')
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

    # Calculer les proportions provinces-par-tag pour chaque état modifié
    proportions_map = {}
    for state in modified_states:
        tag_counts = {}
        for (s, tag), provs in substates.items():
            if s == state and provs:
                tag_counts[tag] = len(provs)
        total = sum(tag_counts.values())
        if total > 0:
            proportions_map[state] = {t: c / total for t, c in tag_counts.items()}

    if not proportions_map:
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
            if _update_file(os.path.join(folder, fname), modified_states, proportions_map, ftype):
                updated += 1

    return updated
