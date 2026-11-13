#!/usr/bin/env python3
"""Genera canciones de demostración de Gramola (melodía y letra originales, sin derechos de terceros).

Cada canción queda en web/songs/<carpeta>/ con:
  - demo.txt   (formato UltraStar, con el estribillo marcado para el Megamix)
  - demo.wav   (audio sintetizado: melodía guía + acordes + bajo + percusión); demo.mp3 si hay ffmpeg
  - cover.png  (portada generada en Python, sin dependencias)
  - megamix.*  (tramo del estribillo) + megamix.json, para que la canción valga en el Megamix
  - video.mp4  (solo con ffmpeg: degradado de prueba para comprobar el vídeo y su sincronía)

Uso:
  python3 tools/demo-song.py                 # crea las demos que falten (no pisa las existentes)
  python3 tools/demo-song.py --forzar        # vuelve a generarlas todas
  python3 tools/demo-song.py demo-cocina     # solo la carpeta indicada
Sin ffmpeg funciona igual: escribe WAV en vez de MP3 y se salta el vídeo.
"""
import json
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import wave
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONGS_DIR = os.path.join(ROOT, 'web', 'songs')
SR = 44100
BPM = 240               # BPM en el sentido UltraStar: un "pulso" = 60000/(240*4) = 62,5 ms
BEAT = 60.0 / (BPM * 4)
GAP_MS = 4000           # intro antes de la primera frase
Q = 8                   # negra (= 0,5 s)
E = 4                   # corchea
MEDLEY_ANTES = 5000     # ms de entrada antes del estribillo (igual que tools/megamix.py)
MEDLEY_DESPUES = 3000   # ms de cola después del estribillo
FFMPEG = shutil.which('ffmpeg')


def L(*parts):
    """Frase compacta: ('sí', tono, duración, 'la', tono, duración, ...)."""
    return [(parts[i], parts[i + 1], parts[i + 2]) for i in range(0, len(parts), 3)]

PROG = [  # un acorde por compás (16 pulsos = 1 compás de 4 negras); cada demo lo transporta
    [0, 4, 7], [-3, 0, 4], [-7, -3, 0], [-5, -1, 2],
]

# Letra y melodía originales. Cada frase: lista de (sílaba, tono, duración en pulsos).
# Tono 0 = Do4. "*" al principio de la sílaba = nota dorada. 'coro' = frases del estribillo.
SONGS = [
    dict(
        folder='demo-gramola', title='Luces en el salón', artist='Gramola (demo)', genre='Pop', seed=7, key=0,
        colors=((42, 20, 96), (255, 79, 163), (11, 58, 92), (236, 48, 19)), coro=(4, 6),
        lines=[
            L('Lu', 4, E, 'ces ', 4, E, 'en ', 5, E, 'el ', 7, E, 'sa', 7, Q, 'lón', 5, Q),
            L('sue', 4, E, 'na ', 2, E, 'la ', 0, E, 'can', 0, E, 'ción', 2, Q * 2),
            L('co', 4, E, 'ge el ', 4, E, 'mó', 5, E, 'vil ', 7, E, 'y ', 9, Q, 'ven', 7, Q),
            L('can', 5, E, 'ta ', 4, E, 'con ', 2, E, 'el ', 4, E, 'co', 2, E, 'ra', 2, E, 'zón', 0, Q),
            L('Gra', 9, E, 'mo', 9, E, 'la, ', 7, Q, '*no ', 9, Q, '*pa', 11, Q, '*res', 12, Q),
            L('cada ', 12, E, 'no', 11, E, 'ta ', 9, E, 'vale ', 7, E, 'un ', 9, Q, 'sol', 7, Q),
            L('Gra', 9, E, 'mo', 9, E, 'la, ', 7, Q, '*su', 9, Q, '*be el ', 11, Q, '*son', 12, Q),
            L('que ', 7, E, 'es', 5, E, 'ta ', 4, E, 'no', 2, E, 'che ', 4, Q, 'es ', 2, Q, 'hoy', 0, Q * 2),
        ],
    ),
    dict(
        folder='demo-vuelta', title='Vuelta a casa', artist='Las Teclas', genre='Pop', seed=11, key=-3,
        colors=((16, 40, 74), (242, 194, 48), (32, 30, 29), (47, 169, 214)), coro=(4, 6),
        lines=[
            L('La ', 4, E, 'no', 4, E, 'che ', 5, E, 'me ', 7, E, 'lla', 7, Q, 'ma', 5, Q),
            L('y la ', 4, E, 'ca', 5, E, 'lle ', 7, E, 'me ', 9, Q, 'es', 7, Q, 'pe', 5, Q, 'ra', 4, Q),
            L('su', 4, E, 'e', 4, E, 'na ', 5, E, 'la ', 7, E, 'ra', 7, Q, 'dio ', 5, E, 'en ', 5, E, 'ca', 7, Q, 'sa', 5, Q),
            L('y se ', 2, E, 'me ', 0, E, 'pa', 2, E, 'sa ', 4, E, 'el ', 4, E, 'mie', 5, Q, 'do', 7, Q),
            L('Vuel', 9, E, 'vo ', 9, E, 'a ', 11, Q, 'ca', 11, Q, 'sa', 12, Q),
            L('o', 9, E, 'tra ', 9, E, 'vez', 11, Q * 2),
            L('y me ', 9, E, 'que', 12, E, 'do ', 12, E, 'a ', 11, Q, 'vi', 9, Q, 'vir', 7, Q * 2),
        ],
    ),
    dict(
        folder='demo-cocina', title='Luz de cocina', artist='Modo Suave', genre='Pop', seed=23, key=2,
        colors=((15, 51, 44), (255, 150, 79), (242, 194, 48), (32, 30, 29)), coro=(4, 6),
        lines=[
            L('La ', 4, E, 'luz ', 4, E, 'de ', 5, E, 'la ', 5, E, 'co', 7, Q, 'ci', 7, Q, 'na', 5, Q),
            L('si', 4, E, 'gue ', 4, E, 'en', 5, E, 'cen', 7, E, 'di', 9, Q, 'da ', 7, Q, 'hoy', 5, Q * 2),
            L('pon', 4, E, 'go ', 4, E, 'la ', 5, E, 'te', 7, E, 'te', 9, E, 'ra ', 9, E, 'al ', 7, Q, 'fue', 5, Q, 'go', 4, Q),
            L('y ', 4, E, 'bai', 4, E, 'lo ', 5, E, 'sin ', 7, E, 'pen', 7, Q, 'sar', 5, Q * 2),
            L('Luz', 9, E, 'de ', 9, E, 'co', 11, Q, 'ci', 11, Q, 'na', 12, Q * 2),
            L('qué', 9, E, 'da', 9, E, 'te ', 11, Q, 'a', 11, E, 'quí', 12, Q * 2),
            L('has', 9, E, 'ta ', 11, E, 'que ', 11, E, 'sal', 12, E, 'ga ', 12, Q, 'el ', 9, Q, 'sol', 7, Q * 2),
        ],
    ),
    dict(
        folder='demo-baila', title='Baila despacio', artist='Cinta Azul', genre='Pop', seed=31, key=-5,
        colors=((26, 16, 68), (47, 169, 214), (255, 79, 163), (32, 30, 29)), coro=(4, 6),
        lines=[
            L('Bai', 4, E, 'la ', 4, E, 'des', 5, E, 'pa', 7, E, 'cio', 7, Q * 2),
            L('que ', 4, E, 'la ', 2, E, 'no', 0, E, 'che ', 0, E, 'es ', 2, Q, 'lar', 4, Q, 'ga', 4, Q),
            L('y ', 4, E, 'el ', 4, E, 're', 5, E, 'loj ', 7, E, 'no ', 9, Q, 'mi', 7, Q, 'ra', 5, Q),
            L('cuan', 4, E, 'do ', 4, E, 'bai', 5, E, 'las ', 7, E, 'tú', 9, Q * 2),
            L('Bai', 9, E, 'la ', 9, E, 'des', 11, Q, 'pa', 11, Q, 'cio', 12, Q * 2),
            L('no ', 9, E, 'te ', 11, E, 'va', 11, Q, 'yas', 12, Q * 2),
            L('qué', 9, E, 'da', 11, E, 'te ', 11, E, 'con', 12, Q, 'mi', 9, Q, 'go', 7, Q * 2),
        ],
    ),
    dict(
        folder='demo-kilometros', title='Mil kilómetros', artist='Corredor 9', genre='Pop', seed=41, key=-7,
        colors=((11, 58, 92), (242, 194, 48), (236, 48, 19), (32, 30, 29)), coro=(4, 6),
        lines=[
            L('Mil', 4, E, 'ki', 4, E, 'ló', 5, E, 'me', 7, E, 'tros', 7, Q * 2),
            L('y ', 4, E, 'to', 4, E, 'da', 5, E, 'ví', 7, E, 'a ', 9, E, 'te ', 9, E, 'es', 7, Q, 'cu', 5, Q, 'cho', 4, Q),
            L('por ', 4, E, 'la ', 4, E, 'ra', 5, E, 'dio ', 7, E, 'del ', 7, Q, 'co', 5, Q, 'che', 4, Q),
            L('aun', 4, E, 'que ', 2, E, 'es', 0, E, 'tés ', 2, E, 'tan ', 4, Q, 'le', 2, Q, 'jos', 0, Q * 2),
            L('Mil', 9, E, 'ki', 9, E, 'ló', 11, Q, 'me', 11, Q, 'tros', 12, Q * 2),
            L('pe', 9, E, 'ro ', 9, E, 'si', 11, Q, 'go ', 11, Q, 'a', 12, Q, 'quí', 12, Q * 2),
            L('con ', 9, E, 'tu ', 11, E, 'voz ', 11, E, 'en ', 12, E, 'el ', 12, Q, 'co', 9, Q, 'che', 7, Q * 2),
        ],
    ),
]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def layout(lines):
    """Coloca las frases en el tiempo, cada una al empezar un compás."""
    notes, txt_lines, spans = [], [], []
    beat = 0
    for line in lines:
        cur = beat
        out = []
        for syl, pitch, dur in line:
            golden = syl.startswith('*')
            syl = syl.lstrip('*')
            out.append(('*' if golden else ':', cur, dur - 1 if dur > 2 else dur, pitch, syl))
            notes.append((cur, dur, pitch))
            cur += dur
        txt_lines.append(out)
        spans.append((beat, cur))
        beat = ((cur + 8 + 15) // 16) * 16  # siguiente frase en el próximo compás, con un respiro
    return notes, txt_lines, spans, beat


def synth(notes, total_beats, chords, gap_ms):
    gap = gap_ms / 1000
    total_s = gap + total_beats * BEAT + 3
    n = int(total_s * SR)
    buf = [0.0] * n

    def add_tone(t0, dur, hz, amp, harmonics, attack=0.01, release=0.08):
        i0 = int(t0 * SR)
        length = int((dur + release) * SR)
        w = 2 * math.pi * hz / SR
        for k in range(length):
            i = i0 + k
            if i >= n:
                break
            t = k / SR
            env = min(1.0, t / attack) * (1.0 if t < dur else max(0.0, 1 - (t - dur) / release))
            s = 0.0
            for h, a in harmonics:
                s += a * math.sin(w * h * k)
            buf[i] += amp * env * s

    # Melodía guía (tipo flauta suave), una octava por encima
    for beat, dur, pitch in notes:
        add_tone(gap + beat * BEAT, dur * BEAT * 0.92, midi_hz(72 + pitch), 0.16, [(1, 1), (2, 0.25), (3, 0.08)], 0.02, 0.06)
    # Acordes y bajo desde la intro hasta el final
    bar = 16 * BEAT
    for b, chord in enumerate(chords):
        t0 = b * bar
        if t0 > total_s - 3:
            break
        for c in chord:
            add_tone(t0, bar * 0.95, midi_hz(60 + c), 0.045, [(1, 1), (2, 0.4), (4, 0.1)], 0.05, 0.2)
        add_tone(t0, bar * 0.45, midi_hz(36 + chord[0] % 12), 0.12, [(1, 1), (2, 0.3)], 0.01, 0.1)
        add_tone(t0 + bar / 2, bar * 0.45, midi_hz(43 + chord[0] % 12), 0.1, [(1, 1), (2, 0.3)], 0.01, 0.1)
        # Percusión: bombo en 1 y 3, "hi-hat" en corcheas
        for q in range(4):
            tq = t0 + q * bar / 4
            if q % 2 == 0:
                i0 = int(tq * SR)
                for k in range(int(0.15 * SR)):
                    if i0 + k < n:
                        t = k / SR
                        buf[i0 + k] += 0.35 * math.exp(-t * 30) * math.sin(2 * math.pi * (50 + 80 * math.exp(-t * 40)) * t)
            for e in (0, 0.5):
                i0 = int((tq + e * bar / 4) * SR)
                for k in range(int(0.04 * SR)):
                    if i0 + k < n:
                        buf[i0 + k] += 0.04 * math.exp(-k / SR * 90) * (random.random() * 2 - 1)

    peak = max(abs(x) for x in buf) or 1
    return [x / peak * 0.85 for x in buf]


def write_wav(path, samples):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, s)) * 32767)) for s in samples))


def write_txt(path, song, txt_lines, spans, audio, video):
    med_a, med_b = spans[song['coro'][0]][0], spans[song['coro'][1]][1]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"#TITLE:{song['title']}\n#ARTIST:{song['artist']}\n#LANGUAGE:Español\n")
        f.write(f"#GENRE:{song['genre']}\n#YEAR:2026\n")
        f.write(f'#AUDIO:{audio}\n')
        if audio.endswith('.mp3'):
            f.write(f'#MP3:{audio}\n')
        f.write('#COVER:cover.png\n')
        if video:
            f.write(f'#VIDEO:{video}\n#VIDEOGAP:0\n')
        f.write(f'#BPM:{BPM}\n#GAP:{GAP_MS}\n')
        f.write(f'#MEDLEYSTARTBEAT:{med_a}\n#MEDLEYENDBEAT:{med_b}\n')
        for li, line in enumerate(txt_lines):
            for kind, beat, dur, pitch, syl in line:
                f.write(f'{kind} {beat} {dur} {pitch} {syl}\n')
            if li < len(txt_lines) - 1:
                last = line[-1]
                f.write(f'- {last[1] + last[2] + 1}\n')  # salto de frase justo después de la última nota
        f.write('E\n')


def write_png(path, w, h, pixel):
    rows = bytearray()
    for y in range(h):
        rows.append(0)  # filtro "None" de cada fila
        for x in range(w):
            rows += bytes(pixel(x / w, y / h))

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)  # 8 bits, RGB
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(bytes(rows), 6)) + chunk(b'IEND', b''))


def write_cover(path, colors, size=800):
    """Portada sin ffmpeg: degradado radial con un halo de luz."""
    c1, c2 = colors

    def pixel(u, v):
        d = math.hypot(u - 0.5, v - 0.42)
        k = min(1.0, d / 0.78)
        glow = max(0.0, 1 - d * 3.0) * 60
        return tuple(min(255, int(c1[i] * (1 - k) + c2[i] * k + glow)) for i in range(3))

    write_png(path, size, size, pixel)


def write_megamix(folder, samples, start, end):
    """Recorte del estribillo (entrada de 5 s y cola de 3 s), con el mismo formato que tools/megamix.py."""
    off = max(0.0, start - MEDLEY_ANTES)
    clip = samples[int(off / 1000 * SR):int((end + MEDLEY_DESPUES) / 1000 * SR)]
    wav = os.path.join(folder, 'megamix.wav')
    write_wav(wav, clip)
    name = 'megamix.wav'
    if FFMPEG:
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libmp3lame', '-b:a', '128k',
                        os.path.join(folder, 'megamix.mp3')], check=True)
        os.remove(wav)
        name = 'megamix.mp3'
    with open(os.path.join(folder, 'megamix.json'), 'w', encoding='utf-8') as f:
        json.dump({'file': name, 'offset': round(off), 'start': round(start), 'end': round(end),
                   'origen': 'generado'}, f)


def write_video(path, dur, colors):
    """Vídeo de prueba (original): degradado de colores en movimiento, para comprobar el vídeo y su sincronía."""
    c = [f'0x{r:02x}{g:02x}{b:02x}' for r, g, b in colors]
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    f'gradients=s=854x480:c0={c[0]}:c1={c[1]}:c2={c[2]}:c3={c[3]}:n=4:speed=0.02:duration={dur:.1f}:rate=25',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an',
                    path], check=True)


def generate(song, forzar=False):
    folder = os.path.join(SONGS_DIR, song['folder'])
    txt = os.path.join(folder, 'demo.txt')
    if os.path.exists(txt) and not forzar:
        return 'ya está (usa --forzar para rehacerla)'
    os.makedirs(folder, exist_ok=True)
    random.seed(song['seed'])
    notes, txt_lines, spans, total = layout(song['lines'])
    beat_ms = 60.0 / (BPM * 4) * 1000
    start = GAP_MS + spans[song['coro'][0]][0] * beat_ms
    end = GAP_MS + spans[song['coro'][1]][1] * beat_ms
    dur = GAP_MS / 1000 + total * BEAT + 3
    chords = [[x + song['key'] for x in PROG[i % len(PROG)]] for i in range(int(dur / (16 * BEAT)) + 2)]
    samples = synth(notes, total, chords, GAP_MS)
    wav = os.path.join(folder, 'demo.wav')
    write_wav(wav, samples)
    audio = 'demo.wav'
    if FFMPEG:
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-i', wav, '-c:a', 'libmp3lame', '-b:a', '128k',
                        os.path.join(folder, 'demo.mp3')], check=True)
        os.remove(wav)
        audio = 'demo.mp3'
    write_cover(os.path.join(folder, 'cover.png'), song['colors'][:2])
    video = ''
    if FFMPEG:
        write_video(os.path.join(folder, 'video.mp4'), dur, song['colors'])
        video = 'video.mp4'
    write_txt(txt, song, txt_lines, spans, audio, video)
    if end - start < MEDLEY_ANTES:
        return f'ok · audio {audio} · sin estribillo válido para el Megamix'
    write_megamix(folder, samples, start, end)
    return f'ok · audio {audio} · estribillo de {(end - start) / 1000:.1f} s'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    forzar = '--forzar' in sys.argv
    songs = SONGS
    if args:
        songs = [s for s in SONGS if s['folder'] in args]
        if not songs:
            sys.exit('No hay demos con esas carpetas. Disponibles: ' + ', '.join(s['folder'] for s in SONGS))
    if not FFMPEG:
        print('Aviso: no hay ffmpeg en el PATH; se genera WAV en vez de MP3 y sin vídeo de prueba.', flush=True)
    for s in songs:
        print(f"{s['folder']}: {generate(s, forzar)}", flush=True)
    print(f'Canciones de demostración en {SONGS_DIR}', flush=True)


if __name__ == '__main__':
    main()
