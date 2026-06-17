from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
from rembg import remove
import io
import os

app = Flask(__name__)
CORS(app)

MAX_SIZE = 20 * 1024 * 1024  # 20MB

def get_image():
    if 'image' not in request.files:
        return None, jsonify({'error': 'No se recibió imagen'}), 400
    f = request.files['image']
    if f.content_length and f.content_length > MAX_SIZE:
        return None, jsonify({'error': 'Imagen demasiado grande'}), 400
    img = Image.open(f.stream).convert('RGBA')
    return img, None, None

def send_image(img, fmt='PNG', filename='resultado'):
    buf = io.BytesIO()
    save_fmt = fmt.upper()
    if save_fmt == 'JPG':
        save_fmt = 'JPEG'
        img = img.convert('RGB')
    img.save(buf, format=save_fmt, quality=92)
    buf.seek(0)
    mime = 'image/jpeg' if save_fmt == 'JPEG' else f'image/{fmt.lower()}'
    return send_file(buf, mimetype=mime, download_name=f'{filename}.{fmt.lower()}')

# ─── 1. FONDO BLANCO ─────────────────────────────────────────────────────────
@app.route('/api/fondo-blanco', methods=['POST'])
def fondo_blanco():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No se recibió imagen'}), 400
        f = request.files['image']
        input_bytes = f.read()
        # rembg quita el fondo → PNG con transparencia
        output_bytes = remove(input_bytes)
        img = Image.open(io.BytesIO(output_bytes)).convert('RGBA')
        # fondo blanco
        fondo = Image.new('RGBA', img.size, (255, 255, 255, 255))
        fondo.paste(img, mask=img.split()[3])
        resultado = fondo.convert('RGB')
        buf = io.BytesIO()
        resultado.save(buf, format='JPEG', quality=95)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name='fondo-blanco.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── 2. COMPRIMIR ─────────────────────────────────────────────────────────────
@app.route('/api/comprimir', methods=['POST'])
def comprimir():
    try:
        img, err, code = get_image()
        if err: return err, code
        quality = int(request.form.get('quality', 80))
        quality = max(10, min(95, quality))
        img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name='comprimida.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── 3. CONVERTIR ─────────────────────────────────────────────────────────────
@app.route('/api/convertir', methods=['POST'])
def convertir():
    try:
        img, err, code = get_image()
        if err: return err, code
        fmt = request.form.get('formato', 'jpg').lower()
        allowed = ['jpg', 'jpeg', 'png', 'webp', 'gif']
        if fmt not in allowed:
            return jsonify({'error': 'Formato no permitido'}), 400
        if fmt in ['jpg', 'jpeg']:
            img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=92)
            buf.seek(0)
            return send_file(buf, mimetype='image/jpeg', download_name=f'convertida.jpg')
        else:
            buf = io.BytesIO()
            img.save(buf, format=fmt.upper())
            buf.seek(0)
            return send_file(buf, mimetype=f'image/{fmt}', download_name=f'convertida.{fmt}')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── 4. RECORTAR ──────────────────────────────────────────────────────────────
@app.route('/api/recortar', methods=['POST'])
def recortar():
    try:
        img, err, code = get_image()
        if err: return err, code
        w = int(request.form.get('width', 1080))
        h = int(request.form.get('height', 1080))
        img = img.convert('RGB')
        # crop centrado manteniendo proporción
        orig_w, orig_h = img.size
        target_ratio = w / h
        orig_ratio = orig_w / orig_h
        if orig_ratio > target_ratio:
            # más ancho → recortar lados
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, orig_h))
        else:
            # más alto → recortar arriba/abajo
            new_h = int(orig_w / target_ratio)
            top = (orig_h - new_h) // 2
            img = img.crop((0, top, orig_w, top + new_h))
        img = img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name=f'recortada-{w}x{h}.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── 5. PORTADA ───────────────────────────────────────────────────────────────
@app.route('/api/portada', methods=['POST'])
def portada():
    try:
        img, err, code = get_image()
        if err: return err, code
        w = int(request.form.get('width', 1280))
        h = int(request.form.get('height', 720))
        texto = request.form.get('texto', '').strip()
        img = img.convert('RGB')
        # resize con crop centrado
        orig_w, orig_h = img.size
        target_ratio = w / h
        orig_ratio = orig_w / orig_h
        if orig_ratio > target_ratio:
            new_w = int(orig_h * target_ratio)
            left = (orig_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, orig_h))
        else:
            new_h = int(orig_w / target_ratio)
            top = (orig_h - new_h) // 2
            img = img.crop((0, top, orig_w, top + new_h))
        img = img.resize((w, h), Image.LANCZOS)
        # agregar texto si viene
        if texto:
            draw = ImageDraw.Draw(img)
            font_size = max(24, h // 18)
            try:
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
            except:
                font = ImageFont.load_default()
            # sombra
            margin = 20
            draw.text((margin+2, h - font_size - margin + 2), texto, font=font, fill=(0,0,0,180))
            draw.text((margin, h - font_size - margin), texto, font=font, fill=(255,255,255,230))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name=f'portada-{w}x{h}.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── 6. MARCA DE AGUA ─────────────────────────────────────────────────────────
@app.route('/api/marca-de-agua', methods=['POST'])
def marca_de_agua():
    try:
        img, err, code = get_image()
        if err: return err, code
        tipo = request.form.get('tipo', 'texto')
        posicion = request.form.get('posicion', 'bottom-right')
        opacidad = int(request.form.get('opacidad', 50)) / 100
        img = img.convert('RGBA')
        w, h = img.size
        overlay = Image.new('RGBA', img.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)

        if tipo == 'texto':
            texto = request.form.get('texto', '').strip()
            if not texto:
                return jsonify({'error': 'Falta el texto'}), 400
            font_size = max(20, min(w, h) // 20)
            try:
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
            except:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0,0), texto, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            margin = 20
            x, y = _calcular_pos(posicion, w, h, tw, th, margin)
            alpha = int(255 * opacidad)
            # sombra
            draw.text((x+2, y+2), texto, font=font, fill=(0,0,0,alpha//2))
            draw.text((x, y), texto, font=font, fill=(255,255,255,alpha))

        elif tipo == 'logo':
            if 'logo' not in request.files:
                return jsonify({'error': 'Falta el logo'}), 400
            logo = Image.open(request.files['logo'].stream).convert('RGBA')
            max_logo = min(w, h) // 4
            logo.thumbnail((max_logo, max_logo), Image.LANCZOS)
            lw, lh = logo.size
            margin = 20
            x, y = _calcular_pos(posicion, w, h, lw, lh, margin)
            # aplicar opacidad al logo
            r, g, b, a = logo.split()
            a = a.point(lambda p: int(p * opacidad))
            logo = Image.merge('RGBA', (r, g, b, a))
            overlay.paste(logo, (x, y), logo)

        resultado = Image.alpha_composite(img, overlay).convert('RGB')
        buf = io.BytesIO()
        resultado.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name='marca-de-agua.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _calcular_pos(posicion, w, h, ew, eh, margin):
    mapa = {
        'top-left':      (margin, margin),
        'top-center':    ((w - ew) // 2, margin),
        'top-right':     (w - ew - margin, margin),
        'center-left':   (margin, (h - eh) // 2),
        'center':        ((w - ew) // 2, (h - eh) // 2),
        'center-right':  (w - ew - margin, (h - eh) // 2),
        'bottom-left':   (margin, h - eh - margin),
        'bottom-center': ((w - ew) // 2, h - eh - margin),
        'bottom-right':  (w - ew - margin, h - eh - margin),
    }
    return mapa.get(posicion, (margin, h - eh - margin))

@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'PixelTools API corriendo ✓'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
