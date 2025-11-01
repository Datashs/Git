from PIL import Image
import os

# === PARAMÈTRES ===
input_folder = "."                  # dossier courant (pas de sous-dossier)
output_file = "bandeau_institutions.jpg"
page_width_cm = 21                  # largeur A4
dpi = 300
target_height_cm = 2.5              # hauteur cible des logos
max_row_width_ratio = 0.9           # occupe 90 % de la largeur
background_color = (255, 255, 255)  # fond blanc

# === CALCULS ===
page_width_px = int(page_width_cm / 2.54 * dpi)
target_height_px = int(target_height_cm / 2.54 * dpi)
max_row_width_px = int(page_width_px * max_row_width_ratio)

# === CHARGEMENT ET REDIMENSIONNEMENT ===
images = []
for f in sorted(os.listdir(input_folder)):
    if f.lower().endswith((".jpg", ".jpeg", ".png")) and f != output_file:
        img = Image.open(os.path.join(input_folder, f)).convert("RGBA")
        ratio = target_height_px / img.height
        new_width = int(img.width * ratio)
        img = img.resize((new_width, target_height_px), Image.LANCZOS)

        # Convertir transparence → fond blanc
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, (0, 0), img)
        img = bg.convert("RGB")

        images.append(img)

if not images:
    raise ValueError("Aucune image trouvée dans le dossier courant.")

# === MISE EN PAGE ===
current_width = 0
rows = [[]]
for img in images:
    if current_width + img.width > max_row_width_px and rows[-1]:
        rows.append([])
        current_width = 0
    rows[-1].append(img)
    current_width += img.width

# === ASSEMBLAGE ===
margin_px = int(0.2 * dpi)
total_height_px = len(rows) * target_height_px + (len(rows) - 1) * margin_px
bandeau = Image.new("RGB", (page_width_px, total_height_px), background_color)

y = 0
for row in rows:
    row_width = sum(img.width for img in row) + (len(row) - 1) * margin_px
    x = (page_width_px - row_width) // 2
    for img in row:
        bandeau.paste(img, (x, y))
        x += img.width + margin_px
    y += target_height_px + margin_px

bandeau.save(output_file, dpi=(dpi, dpi))
print(f"✅ Bandeau enregistré : {output_file} ({len(images)} logos, {len(rows)} ligne(s))")
