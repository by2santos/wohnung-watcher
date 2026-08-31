#!/usr/bin/env python3
"""
Vigilante de pisos en inberlinwohnen.de

Revisa el buscador de pisos (filtrado por Kaltmiete máxima) y avisa
por Telegram, ntfy.sh y/o Email cuando aparece un piso nuevo que no
se había visto antes.

Estado: guarda los pisos ya vistos en seen.json (en el propio repo).
"""

import json
import os
import re
import smtplib
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------

# URL de búsqueda. Puedes cambiar el filtro (p.ej. rent_net][max]=600)
SEARCH_URL = os.environ.get(
    "SEARCH_URL",
    "https://www.inberlinwohnen.de/wohnungsfinder?q[rent_net][max]=600&q[save_search_profile]=0",
)

MAX_PAGES = int(os.environ.get("MAX_PAGES", "10"))
SEEN_FILE = Path(__file__).parent / "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# ------------------------------------------------------------------
# Scraping
# ------------------------------------------------------------------


def fetch_page(page: int) -> str:
    sep = "&" if "?" in SEARCH_URL else "?"
    url = SEARCH_URL if page == 1 else f"{SEARCH_URL}{sep}page={page}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_listings(html: str) -> dict:
    """Devuelve {url_detalle: info_dict} para todos los pisos de una página."""
    soup = BeautifulSoup(html, "html.parser")
    listings = {}

    # Cada piso tiene un enlace "Alle Details" -> es nuestro identificador único
    for link in soup.find_all("a", string=re.compile(r"Alle Details", re.I)):
        href = link.get("href")
        if not href:
            continue

        # Subimos en el árbol hasta encontrar un contenedor con el resumen
        # (Zimmer / m² / €) y la dirección.
        container = link
        text = ""
        for _ in range(6):
            container = container.parent
            if container is None:
                break
            text = container.get_text(" ", strip=True)
            if "Zimmer" in text and "€" in text:
                break

        summary_match = re.search(
            r"([\d,]+)\s*Zimmer.*?([\d,]+)\s*m²\s*,?\s*([\d.,]+)\s*€\s*\|\s*([^|]+?)(?:\s{2,}|$)",
            text,
        )

        if summary_match:
            rooms, size, price, address = summary_match.groups()
            address = address.strip()
        else:
            rooms = size = price = None
            address = None

        listings[href] = {
            "url": href,
            "rooms": rooms,
            "size_m2": size,
            "kaltmiete": price,
            "address": address,
        }

    return listings


def get_all_current_listings() -> dict:
    all_listings = {}
    previous_keys = set()

    for page in range(1, MAX_PAGES + 1):
        try:
            html = fetch_page(page)
        except requests.RequestException as exc:
            print(f"[WARN] No se pudo cargar la página {page}: {exc}", file=sys.stderr)
            break

        page_listings = parse_listings(html)
        if not page_listings:
            break

        new_keys = set(page_listings) - previous_keys
        if page > 1 and not new_keys:
            # La página no aportó nada nuevo -> probablemente ya no hay más páginas
            break

        all_listings.update(page_listings)
        previous_keys |= set(page_listings)
        time.sleep(1)  # ser educados con el servidor

    return all_listings


# ------------------------------------------------------------------
# Estado (pisos ya vistos)
# ------------------------------------------------------------------


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2))


# ------------------------------------------------------------------
# Notificaciones
# ------------------------------------------------------------------


def format_message(listing: dict) -> str:
    rooms = listing.get("rooms") or "?"
    size = listing.get("size_m2") or "?"
    price = listing.get("kaltmiete") or "?"
    address = listing.get("address") or "Dirección no disponible"
    url = listing["url"]
    return (
        f"🏠 Piso nuevo en inberlinwohnen.de\n"
        f"{address}\n"
        f"{rooms} Zimmer · {size} m² · {price} € Kaltmiete\n"
        f"{url}"
    )


def notify_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[WARN] Telegram falló: {exc}", file=sys.stderr)


def notify_ntfy(message: str) -> None:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": "Piso nuevo en Berlin"},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[WARN] ntfy falló: {exc}", file=sys.stderr)


def notify_email(message: str) -> None:
    user = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASS")
    to_addr = os.environ.get("EMAIL_TO", user)
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))

    if not user or not password:
        return

    msg = MIMEText(message)
    msg["Subject"] = "Piso nuevo en inberlinwohnen.de"
    msg["From"] = user
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Email falló: {exc}", file=sys.stderr)


def notify_all(listing: dict) -> None:
    message = format_message(listing)
    notify_telegram(message)
    notify_ntfy(message)
    notify_email(message)
    print(message)
    print("-" * 40)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> None:
    seen = load_seen()
    current = get_all_current_listings()

    if not current:
        print("[WARN] No se ha podido extraer ningún piso. ¿Cambió la web?", file=sys.stderr)
        return

    new_keys = set(current) - seen

    if not seen:
        # Primera ejecución: no avisamos de todo lo existente, solo lo guardamos.
        print(f"Primera ejecución: guardando {len(current)} pisos existentes como vistos.")
    else:
        for key in new_keys:
            notify_all(current[key])
        print(f"{len(new_keys)} piso(s) nuevo(s) encontrados de {len(current)} totales.")

    save_seen(set(current))


if __name__ == "__main__":
    main()
