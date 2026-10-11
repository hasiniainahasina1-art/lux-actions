#!/usr/bin/env python3
"""
dump_button.py — Capture le HTML exact du formulaire login + bouton
sur tronlux.io, APRES resolution du Turnstile, pour voir l'etat reel
du DOM (disabled, caches, classes) au moment du clic.

Sauvegarde dans un fichier texte complet (pas tronque comme les logs
console GitHub Actions).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from camoufox import Camoufox
import ananana

BASE_URL = os.environ.get("LUX_BASE_URL", "https://tronlux.io")
OUTPUT_FILE = "/app/dump_button_report.txt"


def log_section(f, title):
    f.write(f"\n{'='*70}\n{title}\n{'='*70}\n")


def main():
    print(f"Ouverture de {BASE_URL}/login.php")

    with Camoufox(headless=False, humanize=True, geoip=True) as browser:
        page = browser.new_page()
        page.context.clear_cookies()
        page.goto(f"{BASE_URL}/login.php", wait_until="networkidle", timeout=60000)
        time.sleep(3)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

            # ── AVANT remplissage / Turnstile ────────────────────────────────
            log_section(f, "ETAT 1 — Page chargee, AVANT remplissage")
            html1 = page.evaluate("""() => {
                const form = document.querySelector('form');
                return form ? form.outerHTML : 'AUCUN FORM TROUVE';
            }""")
            f.write(html1[:8000])

            # ── Remplir email + password ─────────────────────────────────────
            print("Remplissage email/password...")
            try:
                page.fill("#user_email", "test@example.com")
                page.fill("#password", "testpassword123")
            except Exception as e:
                f.write(f"\nErreur remplissage : {e}\n")

            time.sleep(1)

            # ── Chercher et resoudre Turnstile ───────────────────────────────
            print("Resolution Turnstile...")
            try:
                box = ananana.find_turnstile_iframe_box(page, wait_seconds=10)
                if box:
                    cx = box['x'] + 24
                    cy = box['y'] + box['height'] / 2
                    ananana.human_click(page, cx, cy, color="red")
                    time.sleep(2)
                    for _ in range(20):
                        if ananana.check_turnstile_token(page):
                            print("Turnstile resolu")
                            break
                        time.sleep(1)
            except Exception as e:
                f.write(f"\nErreur Turnstile : {e}\n")

            time.sleep(2)

            # ── ETAT 2 — Apres remplissage + Turnstile ────────────────────────
            log_section(f, "ETAT 2 — APRES remplissage + Turnstile resolu")
            html2 = page.evaluate("""() => {
                const form = document.querySelector('form');
                return form ? form.outerHTML : 'AUCUN FORM TROUVE';
            }""")
            f.write(html2[:10000])

            # ── Tous les elements avec texte LOGIN (tout casse confondue) ─────
            log_section(f, "TOUS LES ELEMENTS CONTENANT 'LOGIN' (insensible casse)")
            elements_info = page.evaluate("""() => {
                const all = [...document.querySelectorAll('a, button, div, span, input')];
                const results = [];
                for (const el of all) {
                    const txt = (el.textContent || el.value || '').trim();
                    if (txt.toUpperCase() === 'LOGIN' || txt.toUpperCase().includes('LOGIN')) {
                        const rect = el.getBoundingClientRect();
                        results.push({
                            tag: el.tagName,
                            id: el.id || null,
                            className: (el.className || '').toString().slice(0, 150),
                            text: txt.slice(0, 50),
                            disabled: el.disabled || el.hasAttribute('disabled'),
                            href: el.href || null,
                            onclick: el.getAttribute('onclick') || null,
                            type: el.type || null,
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            x: Math.round(rect.left),
                            y: Math.round(rect.top),
                            visible: rect.width > 0 && rect.height > 0,
                            outerHTML: el.outerHTML.slice(0, 500)
                        });
                    }
                }
                return results;
            }""")

            for i, el in enumerate(elements_info):
                f.write(f"\n--- Element {i} ---\n")
                for k, v in el.items():
                    f.write(f"  {k}: {v}\n")

            # ── Chercher specifiquement #process_login ────────────────────────
            log_section(f, "DETAIL #process_login")
            process_login_info = page.evaluate("""() => {
                const el = document.querySelector('#process_login');
                if (!el) return 'ELEMENT #process_login INTROUVABLE';
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return JSON.stringify({
                    tag: el.tagName,
                    outerHTML: el.outerHTML.slice(0, 1000),
                    disabled: el.disabled,
                    display: style.display,
                    visibility: style.visibility,
                    opacity: style.opacity,
                    pointerEvents: style.pointerEvents,
                    width: rect.width,
                    height: rect.height,
                    onclick: el.getAttribute('onclick'),
                    type: el.type
                }, null, 2);
            }""")
            f.write(str(process_login_info))

            # ── Chercher tous les boutons/submit du formulaire ─────────────────
            log_section(f, "TOUS LES BOUTONS/SUBMIT DANS LE FORM")
            buttons_info = page.evaluate("""() => {
                const form = document.querySelector('form');
                if (!form) return 'AUCUN FORM';
                const btns = form.querySelectorAll('button, input[type="submit"], input[type="button"], [onclick]');
                const results = [];
                btns.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    results.push({
                        tag: el.tagName,
                        id: el.id,
                        className: (el.className || '').toString().slice(0,100),
                        text: (el.textContent || el.value || '').trim().slice(0,50),
                        disabled: el.disabled,
                        onclick: el.getAttribute('onclick'),
                        width: rect.width,
                        height: rect.height
                    });
                });
                return JSON.stringify(results, null, 2);
            }""")
            f.write(str(buttons_info))

            # ── Screenshot final ────────────────────────────────────────────
            os.makedirs("/app/screenshots", exist_ok=True)
            page.screenshot(path="/app/screenshots/dump_button_final.png", full_page=True)

        # Afficher aussi dans la console (tronque mais utile en apercu)
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            content = f.read()
        print(f"\nRapport sauvegarde : {OUTPUT_FILE} ({len(content)} caracteres)")
        print("Apercu (premiers 3000 car.) :")
        print(content[:3000])


if __name__ == "__main__":
    main()
