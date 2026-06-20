# v5 — imagen + PDF + GIF
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
from rembg import remove
import io, os, zipfile
import pikepdf

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=False)

MAX_SIZE = 20 * 1024 * 1024   # 20MB imágenes
MAX_PDF  = 50 * 1024 * 1024   # 50MB PDFs

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

def get_pdf(field='pdf'):
    if field not in request.files:
        return None, jsonify({'error': f'No se recibió el PDF ({field})'}), 400
    f = request.files[field]
    data = f.read()
    if len(data) > MAX_PDF:
        return None, jsonify({'error': 'PDF demasiado grande (máx 50MB)'}), 400
    return data, None, None

# ═══════════════════════════════════════════════════════════════
# IMAGEN ENDPOINTS (sin cambios)
# ═══════════════════════════════════════════════════════════════

@app.route('/api/fondo-blanco', methods=['POST'])
def fondo_blanco():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No se recibió imagen'}), 400
        f = request.files['image']
        input_bytes = f.read()
        output_bytes = remove(input_bytes)
        img = Image.open(io.BytesIO(output_bytes)).convert('RGBA')
        fondo = Image.new('RGBA', img.size, (255, 255, 255, 255))
        fondo.paste(img, mask=img.split()[3])
        resultado = fondo.convert('RGB')
        buf = io.BytesIO()
        resultado.save(buf, format='JPEG', quality=95)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name='fondo-blanco.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            return send_file(buf, mimetype='image/jpeg', download_name='convertida.jpg')
        else:
            buf = io.BytesIO()
            img.save(buf, format=fmt.upper())
            buf.seek(0)
            return send_file(buf, mimetype=f'image/{fmt}', download_name=f'convertida.{fmt}')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recortar', methods=['POST'])
def recortar():
    try:
        img, err, code = get_image()
        if err: return err, code
        w = int(request.form.get('width', 1080))
        h = int(request.form.get('height', 1080))
        img = img.convert('RGB')
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
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name=f'recortada-{w}x{h}.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portada', methods=['POST'])
def portada():
    try:
        img, err, code = get_image()
        if err: return err, code
        w = int(request.form.get('width', 1280))
        h = int(request.form.get('height', 720))
        texto = request.form.get('texto', '').strip()
        img = img.convert('RGB')
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
        if texto:
            draw = ImageDraw.Draw(img)
            font_size = max(24, h // 18)
            try:
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
            except:
                font = ImageFont.load_default()
            margin = 20
            draw.text((margin+2, h - font_size - margin + 2), texto, font=font, fill=(0,0,0,180))
            draw.text((margin, h - font_size - margin), texto, font=font, fill=(255,255,255,230))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', download_name=f'portada-{w}x{h}.jpg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

# ═══════════════════════════════════════════════════════════════
# PDF ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# ─── PDF 1. COMPRIMIR ─────────────────────────────────────────
@app.route('/api/comprimir-pdf', methods=['POST'])
def comprimir_pdf():
    try:
        data, err, code = get_pdf('pdf')
        if err: return err, code
        inp = pikepdf.open(io.BytesIO(data))
        buf = io.BytesIO()
        inp.save(buf, compress_streams=True, recompress_flate=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='comprimido.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 2. UNIR ──────────────────────────────────────────────
@app.route('/api/unir-pdf', methods=['POST'])
def unir_pdf():
    try:
        files = request.files.getlist('pdfs')
        if len(files) < 2:
            return jsonify({'error': 'Se necesitan al menos 2 PDFs'}), 400
        resultado = pikepdf.Pdf.new()
        for f in files:
            data = f.read()
            if len(data) > MAX_PDF:
                return jsonify({'error': f'Archivo {f.filename} supera 50MB'}), 400
            pdf = pikepdf.open(io.BytesIO(data))
            resultado.pages.extend(pdf.pages)
        buf = io.BytesIO()
        resultado.save(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='unidos.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 3. DIVIDIR ───────────────────────────────────────────
@app.route('/api/dividir-pdf', methods=['POST'])
def dividir_pdf():
    try:
        data, err, code = get_pdf('pdf')
        if err: return err, code
        modo = request.form.get('modo', 'todas')
        pdf = pikepdf.open(io.BytesIO(data))
        total = len(pdf.pages)

        if modo == 'rango':
            paginas_str = request.form.get('paginas', '').strip()
            indices = _parsear_paginas(paginas_str, total)
            if not indices:
                return jsonify({'error': 'Páginas inválidas'}), 400
            nuevo = pikepdf.Pdf.new()
            for i in indices:
                nuevo.pages.append(pdf.pages[i])
            buf = io.BytesIO()
            nuevo.save(buf)
            buf.seek(0)
            return send_file(buf, mimetype='application/pdf', download_name='paginas.pdf')
        else:
            # Una página por archivo → ZIP
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(pdf.pages):
                    nuevo = pikepdf.Pdf.new()
                    nuevo.pages.append(page)
                    pb = io.BytesIO()
                    nuevo.save(pb)
                    zf.writestr(f'pagina-{i+1:03d}.pdf', pb.getvalue())
            zip_buf.seek(0)
            return send_file(zip_buf, mimetype='application/zip', download_name='paginas.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _parsear_paginas(s, total):
    indices = set()
    for parte in s.split(','):
        parte = parte.strip()
        if '-' in parte:
            a, b = parte.split('-', 1)
            try:
                a, b = int(a.strip()), int(b.strip())
                for n in range(a, b+1):
                    if 1 <= n <= total:
                        indices.add(n-1)
            except: pass
        else:
            try:
                n = int(parte)
                if 1 <= n <= total:
                    indices.add(n-1)
            except: pass
    return sorted(indices)

# ─── PDF 4. PDF A JPG ─────────────────────────────────────────
@app.route('/api/pdf-a-jpg', methods=['POST'])
def pdf_a_jpg():
    try:
        from pdf2image import convert_from_bytes
        data, err, code = get_pdf('pdf')
        if err: return err, code
        imagenes = convert_from_bytes(data, dpi=150)
        if len(imagenes) == 1:
            buf = io.BytesIO()
            imagenes[0].save(buf, format='JPEG', quality=90)
            buf.seek(0)
            return send_file(buf, mimetype='image/jpeg', download_name='pagina-1.jpg')
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(imagenes):
                pb = io.BytesIO()
                img.save(pb, format='JPEG', quality=90)
                zf.writestr(f'pagina-{i+1:03d}.jpg', pb.getvalue())
        zip_buf.seek(0)
        return send_file(zip_buf, mimetype='application/zip', download_name='paginas.zip')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 5. JPG A PDF ─────────────────────────────────────────
@app.route('/api/jpg-a-pdf', methods=['POST'])
def jpg_a_pdf():
    try:
        files = request.files.getlist('imagenes')
        if not files:
            return jsonify({'error': 'No se recibieron imágenes'}), 400
        imagenes = []
        for f in files:
            img = Image.open(f.stream).convert('RGB')
            imagenes.append(img)
        buf = io.BytesIO()
        if len(imagenes) == 1:
            imagenes[0].save(buf, format='PDF')
        else:
            imagenes[0].save(buf, format='PDF', save_all=True, append_images=imagenes[1:])
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='imagenes.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 6. ROTAR ─────────────────────────────────────────────
@app.route('/api/rotar-pdf', methods=['POST'])
def rotar_pdf():
    try:
        data, err, code = get_pdf('pdf')
        if err: return err, code
        grado = int(request.form.get('grado', 90))
        if grado not in [90, 180, 270]:
            return jsonify({'error': 'Grado inválido'}), 400
        pdf = pikepdf.open(io.BytesIO(data))
        for page in pdf.pages:
            page.rotate(grado, relative=True)
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name=f'rotado-{grado}.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 7. PROTEGER ──────────────────────────────────────────
@app.route('/api/proteger-pdf', methods=['POST'])
def proteger_pdf():
    try:
        data, err, code = get_pdf('pdf')
        if err: return err, code
        password = request.form.get('password', '').strip()
        if not password:
            return jsonify({'error': 'Falta la contraseña'}), 400
        pdf = pikepdf.open(io.BytesIO(data))
        perms = pikepdf.Permissions(
            print_lowres=False, print_highres=False,
            modify_annotation=False, modify_assembly=False,
            modify_form=False, modify_other=False,
            extract=False
        )
        enc = pikepdf.Encryption(user=password, owner=password, allow=perms)
        buf = io.BytesIO()
        pdf.save(buf, encryption=enc)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='protegido.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PDF 8. DESBLOQUEAR ───────────────────────────────────────
@app.route('/api/desbloquear-pdf', methods=['POST'])
def desbloquear_pdf():
    try:
        data, err, code = get_pdf('pdf')
        if err: return err, code
        password = request.form.get('password', '')
        try:
            pdf = pikepdf.open(io.BytesIO(data), password=password)
        except pikepdf.PasswordError:
            return jsonify({'error': 'Contraseña incorrecta'}), 403
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', download_name='desbloqueado.pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════
# GIF ENDPOINT
# ═══════════════════════════════════════════════════════════════

@app.route('/api/optimizar-gif', methods=['POST'])
def optimizar_gif():
    try:
        if 'gif' not in request.files:
            return jsonify({'error': 'No se recibió ningún GIF'}), 400
        f = request.files['gif']
        data = f.read()
        if len(data) > MAX_SIZE:
            return jsonify({'error': 'GIF demasiado grande (máx 20MB)'}), 400

        nivel = request.form.get('nivel', 'medio')
        colors_map = {'bajo': 256, 'medio': 128, 'alto': 64}
        colors = int(request.form.get('colores', colors_map.get(nivel, 128)))
        colors = max(8, min(256, colors))

        src = Image.open(io.BytesIO(data))
        frames = []
        durations = []
        loop = src.info.get('loop', 0)

        try:
            while True:
                frame = src.copy().convert('RGBA')
                frame = frame.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
                frames.append(frame)
                durations.append(src.info.get('duration', 100))
                src.seek(src.tell() + 1)
        except EOFError:
            pass

        buf = io.BytesIO()
        frames[0].save(
            buf,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            loop=loop,
            duration=durations,
            optimize=True
        )
        buf.seek(0)
        return send_file(buf, mimetype='image/gif', download_name='optimizado.gif')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════
@app.route('/', methods=['GET'])
def index():
    return jsonify({'status': 'PixelTools API v5 corriendo ✓'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
