with open('modules/pays_frame.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Nombre total de lignes: {len(lines)}")

# Afficher les lignes autour de 3775
for i in range(3770, 3790):
    if i < len(lines):
        print(f'Ligne {i+1}: {lines[i]}', end='')