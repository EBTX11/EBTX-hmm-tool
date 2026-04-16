with open('modules/pays_frame.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Afficher les lignes 37770-37800
for i in range(37769, 37800):
    if i < len(lines):
        print(f'Ligne {i+1}: {lines[i]}', end='')