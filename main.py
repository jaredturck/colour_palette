from PIL import Image
from sklearn.cluster import MiniBatchKMeans
from jinja2 import Template
from io import BytesIO
import numpy as np
import math, colour, os, base64, hashlib, webbrowser
from pathlib import Path
from tkinter import Tk, filedialog

class ColourPaletteReport:
    def __init__(self, template_file='template.html', output_file='report.html'):
        self.template_file = template_file
        self.output_file = output_file

    def render_report(self, filename):
        src_img = Image.open(filename).convert('RGB')
        dst_img = self.downsample_image(src_img)
        oklab = self.img_to_oklab(dst_img)

        palette, weights = self.quantize_img(oklab, k=32)
        family_palette, family_weights, family_groups = self.merge_colour_families(palette, weights)
        ranked_palette, ranked_weights, ranked_scores, ranked_order = self.rank_colour_families(family_palette, family_weights)
        final_palette, final_weights, final_scores = self.select_final_palette(ranked_palette, ranked_weights, ranked_scores)

        candidate_palette = self.oklab_to_hex(palette, sort=True)
        family_palette_hex = self.oklab_to_hex(family_palette, sort=True)
        ranked_palette_hex = self.oklab_to_hex(ranked_palette, sort=False)
        final_palette_hex = self.oklab_to_hex(final_palette, sort=False)

        colour_space_points = self.build_colour_space_points(final_palette, count=len(final_palette))
        image_metadata = self.build_image_metadata(filename, src_img, dst_img, palette, family_palette, final_palette)
        image_summary = self.build_image_summary(filename, src_img, family_palette, family_weights, final_palette)

        family_items = []

        for index, hex_colour in enumerate(family_palette_hex):
            family_items.append({
                'hex': hex_colour,
                'weight': round(family_weights[index] * 100, 1),
                'count': len(family_groups[index]),
            })

        ranked_items = []

        for hex_colour, weight, score in zip(ranked_palette_hex, ranked_weights, ranked_scores):
            ranked_items.append({
                'hex': hex_colour,
                'weight': round(weight * 100, 1),
                'score': round(score * 100, 1),
            })

        roles = ['Primary', 'Secondary', 'Contrast', 'Accent', 'Neutral', 'Support', 'Support', 'Support']
        recommended_palette = []

        for index, hex_colour in enumerate(final_palette_hex):
            recommended_palette.append({
                'hex': hex_colour,
                'role': roles[index] if index < len(roles) else 'Colour',
                'weight': round(final_weights[index] * 100, 1),
                'score': round(final_scores[index] * 100, 1),
            })

        context = {
            'report_title': 'Image Palette Report',
            'report_subtitle': 'Generated with precision. Designed for creators.',
            'filename': filename,
            'image_src': self.img_to_base64(src_img),
            'candidate_palette': candidate_palette,
            'candidate_count': len(candidate_palette),
            'family_palette': family_palette_hex,
            'family_items': family_items,
            'family_count': len(family_items),
            'ranked_palette': ranked_palette_hex,
            'ranked_items': ranked_items,
            'recommended_palette': recommended_palette,
            'recommended_count': len(recommended_palette),
            'colour_space_points': colour_space_points,
            'image_metadata': image_metadata,
            'image_summary': image_summary,
            'source_size': src_img.size,
            'downsampled_size': dst_img.size,
        }

        with open(self.template_file, 'r') as file:
            template_str = file.read()

        with open(self.output_file, 'w') as file:
            template = Template(template_str)
            html = template.render(**context)
            file.write(html)

        webbrowser.open(Path(self.output_file).resolve().as_uri())

    def downsample_image(self, img, target=50_000):
        total = img.size[0] * img.size[1]
        scale = min(math.sqrt(target / total), 1)
        w = round(img.size[0] * scale)
        h = round(img.size[1] * scale)

        new_img = img.resize((w, h), Image.Resampling.LANCZOS)
        return new_img

    def img_to_base64(self, img):
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{encoded}'

    def img_to_oklab(self, img):
        rgb = np.array(img) / 255
        xyz = colour.sRGB_to_XYZ(rgb)
        oklab = colour.XYZ_to_Oklab(xyz)
        return oklab

    def oklab_to_hex(self, oklab, sort=True):
        if sort:
            chroma = np.sqrt(oklab[:, 1] ** 2 + oklab[:, 2] ** 2)
            hue = np.arctan2(oklab[:, 2], oklab[:, 1])
            order = np.lexsort((chroma, hue))
            oklab = oklab[order]

        xyz = colour.Oklab_to_XYZ(oklab)
        rgb = colour.XYZ_to_sRGB(xyz)
        rgb = np.clip(rgb, 0, 1)
        rgb = (rgb * 255).round().astype('uint8')
        hex_colours = [f'#{r:02x}{g:02x}{b:02x}' for r,g,b in rgb]
        return hex_colours

    def oklab_swatch_to_hex(self, swatch):
        xyz = colour.Oklab_to_XYZ(swatch)
        rgb = colour.XYZ_to_sRGB(xyz)
        rgb = np.clip(rgb, 0, 1)
        r, g, b = (rgb * 255).round().astype('uint8')
        return f'#{r:02x}{g:02x}{b:02x}'

    def oklch_to_hex(self, l, c, h):
        h = math.radians(h)
        a = c * math.cos(h)
        b = c * math.sin(h)
        return self.oklab_swatch_to_hex(np.array([l, a, b]))

    def quantize_img(self, oklab, k=32):
        pixels = oklab.reshape(-1, 3)
        model = MiniBatchKMeans(n_clusters=k, random_state=1, n_init='auto', batch_size=4096)
        labels = model.fit_predict(pixels)
        counts = np.bincount(labels, minlength=k)
        weights = counts / counts.sum()
        order = weights.argsort()[::-1]

        return model.cluster_centers_[order], weights[order]

    def merge_colour_families(self, palette, weights, threshold=0.075):
        centres = np.array(palette, dtype='float32')
        weights = np.array(weights, dtype='float32')
        groups = [[i] for i in range(len(centres))]

        while len(centres) > 1:
            distances = np.linalg.norm(centres[:, None, :] - centres[None, :, :], axis=2)
            np.fill_diagonal(distances, np.inf)

            i, j = np.unravel_index(distances.argmin(), distances.shape)

            if distances[i, j] > threshold:
                break

            if j < i:
                i, j = j, i

            total = weights[i] + weights[j]
            merged = (centres[i] * weights[i] + centres[j] * weights[j]) / total

            centres[i] = merged
            weights[i] = total
            groups[i] = groups[i] + groups[j]

            centres = np.delete(centres, j, axis=0)
            weights = np.delete(weights, j)
            del groups[j]

        order = weights.argsort()[::-1]

        centres = centres[order]
        weights = weights[order]
        groups = [groups[i] for i in order]

        return centres, weights, groups

    def rank_colour_families(self, family_palette, family_weights):
        chroma = np.sqrt(family_palette[:, 1] ** 2 + family_palette[:, 2] ** 2)
        avg_colour = np.average(family_palette, axis=0, weights=family_weights)
        distance = np.linalg.norm(family_palette - avg_colour, axis=1)

        area_score = family_weights / family_weights.max()
        chroma_score = np.clip(chroma / 0.14, 0, 1)
        distance_score = np.clip(distance / 0.25, 0, 1)

        scores = (
            area_score * 0.60 +
            chroma_score * 0.25 +
            distance_score * 0.15
        )

        order = scores.argsort()[::-1]

        return family_palette[order], family_weights[order], scores[order], order

    def select_final_palette(self, ranked_palette, ranked_weights, ranked_scores, min_colours=3, max_colours=8):
        selected = []
        selected_weights = []
        selected_scores = []

        best_score = ranked_scores[0]
        min_score = best_score * 0.35
        min_distance = 0.10

        for colour, weight, score in zip(ranked_palette, ranked_weights, ranked_scores):
            if len(selected) >= max_colours:
                break

            if selected:
                distances = np.linalg.norm(np.array(selected) - colour, axis=1)
                too_similar = distances.min() < min_distance
            else:
                too_similar = False

            important_enough = score >= min_score or len(selected) < min_colours

            if not too_similar and important_enough:
                selected.append(colour)
                selected_weights.append(weight)
                selected_scores.append(score)

        return np.array(selected), np.array(selected_weights), np.array(selected_scores)

    def build_colour_space_points(self, palette, count=5):
        roles = ['Primary', 'Secondary', 'Contrast', 'Accent', 'Neutral']
        points = []

        for index, swatch in enumerate(palette[:count]):
            l, a, b = swatch

            chroma = math.sqrt(a ** 2 + b ** 2)
            hue = (math.degrees(math.atan2(b, a)) + 360) % 360

            if chroma < 0.015:
                x = 50
            else:
                x = hue / 360 * 100

            y = (1 - l) * 100
            size = 14 + min(chroma / 0.12, 1) * 10

            alternatives = []

            for offset in [-0.16, -0.08, 0, 0.08, 0.16]:
                alt_l = np.clip(l + offset, 0.05, 0.97)
                alt_hex = self.oklch_to_hex(alt_l, chroma, hue)
                alternatives.append(alt_hex)

            points.append({
                'role': roles[index] if index < len(roles) else 'Colour',
                'hex': self.oklab_swatch_to_hex(swatch),
                'x': round(x, 2),
                'y': round(y, 2),
                'size': round(size, 2),
                'alternatives': alternatives,
            })

        return points

    def build_image_metadata(self, filename, src_img, dst_img, palette, family_palette, final_palette):
        src_w, src_h = src_img.size
        dst_w, dst_h = dst_img.size

        file_size = os.path.getsize(filename)

        if file_size >= 1024 * 1024:
            file_size = f'{file_size / 1024 / 1024:.2f} MB'
        elif file_size >= 1024:
            file_size = f'{file_size / 1024:.2f} KB'
        else:
            file_size = f'{file_size} bytes'

        file_ext = os.path.splitext(filename)[1].replace('.', '').upper()

        divisor = math.gcd(src_w, src_h)
        aspect_ratio = f'{src_w // divisor}:{src_h // divisor}'

        dpi = src_img.info.get('dpi')

        if dpi:
            dpi = f'{round(dpi[0])}×{round(dpi[1])}'
        else:
            dpi = 'Not embedded'

        return [
            {'label': 'Filename', 'value': filename},
            {'label': 'File type', 'value': file_ext},
            {'label': 'File size', 'value': file_size},
            {'label': 'Source size', 'value': f'{src_w}×{src_h}'},
            {'label': 'Working size', 'value': f'{dst_w}×{dst_h}'},
            {'label': 'Aspect ratio', 'value': aspect_ratio},
            {'label': 'Megapixels', 'value': f'{src_w * src_h / 1_000_000:.2f} MP'},
            {'label': 'DPI', 'value': dpi},
            {'label': 'Image mode', 'value': src_img.mode},
            {'label': 'Working colour space', 'value': 'OKLab'},
            {'label': 'Candidate colours', 'value': len(palette)},
            {'label': 'Colour families', 'value': len(family_palette)},
            {'label': 'Final colours', 'value': len(final_palette)},
        ]

    def build_image_summary(self, filename, src_img, family_palette, family_weights, final_palette):
        src_w, src_h = src_img.size
        ratio = src_w / src_h

        if abs(src_w - src_h) / max(src_w, src_h) < 0.05:
            orientation = 'Square'
        elif src_w > src_h:
            orientation = 'Landscape'
        else:
            orientation = 'Portrait'

        if 0.95 <= ratio <= 1.05:
            aspect_category = 'Square'
        elif ratio >= 1.6:
            aspect_category = 'Wide landscape'
        elif ratio > 1:
            aspect_category = 'Standard landscape'
        elif ratio <= 0.63:
            aspect_category = 'Tall portrait'
        else:
            aspect_category = 'Standard portrait'

        family_count = len(family_palette)

        if family_count <= 5:
            palette_complexity = 'Low'
        elif family_count <= 10:
            palette_complexity = 'Medium'
        else:
            palette_complexity = 'High'

        chroma = np.sqrt(family_palette[:, 1] ** 2 + family_palette[:, 2] ** 2)
        avg_chroma = np.average(chroma, weights=family_weights)

        if avg_chroma < 0.035:
            colour_character = 'Muted'
        elif avg_chroma < 0.07:
            colour_character = 'Soft'
        elif avg_chroma < 0.11:
            colour_character = 'Balanced'
        else:
            colour_character = 'Vibrant'

        avg_lightness = np.average(family_palette[:, 0], weights=family_weights)

        if avg_lightness < 0.35:
            lightness_profile = 'Dark'
        elif avg_lightness < 0.58:
            lightness_profile = 'Balanced'
        elif avg_lightness < 0.78:
            lightness_profile = 'Bright'
        else:
            lightness_profile = 'High-key'

        with open(filename, 'rb') as file:
            fingerprint = hashlib.sha1(file.read()).hexdigest()[:8].upper()

        return [
            {'label': 'Orientation', 'value': orientation},
            {'label': 'Aspect category', 'value': aspect_category},
            {'label': 'Palette complexity', 'value': palette_complexity},
            {'label': 'Colour character', 'value': colour_character},
            {'label': 'Lightness profile', 'value': lightness_profile},
            {'label': 'Image fingerprint', 'value': fingerprint},
        ]

if __name__ == '__main__':
    root = Tk()
    root.withdraw()

    filename = filedialog.askopenfilename(
        title='Select image',
        initialdir=os.path.expanduser('~/Pictures'),
        filetypes=[
            ('Image files', '*.png *.jpg *.jpeg *.webp *.bmp'),
            ('All files', '*.*'),
        ]
    )

    root.destroy()

    report = ColourPaletteReport()
    report.render_report(filename or 'Whomping_Willow_POAF.png')
