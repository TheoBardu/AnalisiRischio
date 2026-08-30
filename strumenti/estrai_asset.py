#! /usr/bin/env python3
"""
Estrae da 'MockUp/App VRR standalone.html' i fogli di stile e i font che
compongono l'interfaccia, e li scrive in web/.

Il mockup e' un bundle: il markup vive in uno <script type="__bundler/template">
e le risorse (font, immagini) in uno <script type="__bundler/manifest">, dove
ogni asset e' identificato da un uuid ed e' codificato in base64, eventualmente
compresso con gzip. Nel CSS i font sono referenziati con url("<uuid>"): qui gli
uuid vengono sostituiti con i nomi dei file scritti su disco.

USO:
    python strumenti/estrai_asset.py [percorso_mockup]
"""

import base64
import gzip
import json
import os
import re
import sys

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCKUP_DEFAULT = os.path.join(
    os.path.dirname(CARTELLA_PROGETTO), 'MockUp', 'App VRR standalone.html')

ESTENSIONI = {
    'font/woff2': '.woff2',
    'font/woff': '.woff',
    'font/ttf': '.ttf',
    'image/svg+xml': '.svg',
}


def leggi_bundle(percorso):
    """
    INPUT:  percorso del file html del mockup
    OUTPUT: (manifest, template) - dizionario degli asset e markup completo
    """
    with open(percorso, encoding='utf-8') as f:
        sorgente = f.read()

    m = re.search(r'<script type="__bundler/manifest">(.*?)</script>', sorgente, re.S)
    t = re.search(r'<script type="__bundler/template">(.*?)</script>', sorgente, re.S)
    if not m or not t:
        raise ValueError(f'{percorso} non sembra un bundle: manifest o template assenti')
    return json.loads(m.group(1)), json.loads(t.group(1))


def dati_asset(voce):
    """Decodifica un asset del manifest (base64, eventualmente gzip)."""
    grezzo = base64.b64decode(voce['data'])
    if voce.get('compressed'):
        grezzo = gzip.decompress(grezzo)
    return grezzo


def scrivi_font(manifest, cartella_font):
    """
    Scrive su disco i soli asset di tipo font.

    OUTPUT: dizionario uuid -> nome del file scritto
    """
    os.makedirs(cartella_font, exist_ok=True)
    nomi = {}
    contatore = {}
    for uuid, voce in manifest.items():
        mime = voce.get('mime', '')
        if not mime.startswith('font/'):
            continue
        estensione = ESTENSIONI.get(mime, '.bin')
        # nome stabile e leggibile: font1.woff2, font2.woff2, ...
        indice = contatore.get(estensione, 0) + 1
        contatore[estensione] = indice
        nome = f'font{indice}{estensione}'
        with open(os.path.join(cartella_font, nome), 'wb') as f:
            f.write(dati_asset(voce))
        nomi[uuid] = nome
    return nomi


def estrai_stili(template, nomi_font):
    """
    Concatena i blocchi <style> del template e sostituisce gli uuid dei font
    con i percorsi relativi dei file scritti da scrivi_font().
    """
    blocchi = re.findall(r'<style>(.*?)</style>', template, re.S)
    css = '\n\n'.join(blocchi)
    for uuid, nome in nomi_font.items():
        css = css.replace(uuid, f'assets/fonts/{nome}')
    # gli asset non estratti (svg decorativi mai usati dall'interfaccia)
    # resterebbero come url("<uuid>"): li si neutralizza per non generare
    # richieste fallite a runtime.
    css = re.sub(r'url\("[0-9a-f-]{36}"\)', 'none', css)
    return css


def estrai_markup(template):
    """Restituisce il contenuto di <x-dc>, cioe' il markup dell'interfaccia."""
    apertura = re.search(r'<x-dc(?:\s[^>]*)?>', template)
    chiusura = template.rfind('</x-dc>')
    if not apertura or chiusura == -1:
        raise ValueError('elemento <x-dc> non trovato nel template')
    markup = template[apertura.end():chiusura]
    # l'<helmet> contiene gli <style>, gia' estratti a parte
    return re.sub(r'<helmet.*?</helmet>', '', markup, flags=re.S).strip()


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else MOCKUP_DEFAULT
    if not os.path.exists(percorso):
        print(f'Mockup non trovato: {percorso}')
        return 1

    manifest, template = leggi_bundle(percorso)
    cartella_web = os.path.join(CARTELLA_PROGETTO, 'web')

    nomi_font = scrivi_font(manifest, os.path.join(cartella_web, 'assets', 'fonts'))
    print(f'font estratti: {len(nomi_font)}')

    css = estrai_stili(template, nomi_font)
    with open(os.path.join(cartella_web, 'mockup.css'), 'w', encoding='utf-8') as f:
        f.write(css)
    print(f'web/mockup.css: {len(css)} byte')

    markup = estrai_markup(template)
    with open(os.path.join(cartella_web, 'mockup.html'), 'w', encoding='utf-8') as f:
        f.write(markup)
    print(f'web/mockup.html: {len(markup)} byte  (riferimento per index.html)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
