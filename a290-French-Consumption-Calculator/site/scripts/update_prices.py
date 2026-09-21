#!/usr/bin/env python3
"""Met à jour data/prix.json avec les prix moyens nationaux quotidiens des carburants.

Source : flux open data officiel « Prix des carburants » (ministère de l'Économie)
https://www.prix-carburants.gouv.fr/rubrique/opendata/

Deux modes :
  python scripts/update_prices.py            -> ajoute (ou remplace) le point du jour
                                                 à partir du flux instantané.
  python scripts/update_prices.py --backfill -> recalcule les 100 derniers jours
                                                 à partir du stock annuel.

Méthode : moyenne arithmétique des prix déclarés par les stations, en ne gardant
qu'un prix par station et par carburant (le dernier connu) et seulement s'il a été
mis à jour dans les 7 derniers jours. Même principe que les moyennes publiées par
les sites de suivi des prix.
"""
import argparse, io, json, os, sys, urllib.request, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
BASE = "https://donnees.roulez-eco.fr/opendata"
FUELS = {"E10": "e10", "SP98": "sp98", "Gazole": "gazole", "E85": "e85"}
STALE_DAYS = 7          # un prix plus vieux que ça n'est pas compté
KEEP_DAYS = 400         # historique conservé dans le fichier
BACKFILL_DAYS = 100
MIN_P, MAX_P = 0.3, 5.0 # garde-fou contre les saisies aberrantes
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "prix.json")


def download_xml(url):
    req = urllib.request.Request(url, headers={"User-Agent": "a290-contre-la-pompe (GitHub Actions)"})
    with urllib.request.urlopen(req, timeout=300) as r:
        raw = r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        return z.read(name)


def parse_maj(s):
    s = (s or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            pass
    return None


def parse_price(v):
    try:
        p = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if p > 20:          # anciens fichiers : prix en millièmes d'euro
        p /= 1000
    return p if MIN_P <= p <= MAX_P else None


def iter_prices(xml_bytes):
    """Renvoie (station, carburant, horodatage, prix) pour chaque élément <prix>."""
    station = None
    for event, el in ET.iterparse(io.BytesIO(xml_bytes), events=("start", "end")):
        if event == "start" and el.tag == "pdv":
            station = el.get("id")
        elif event == "end" and el.tag == "prix":
            fuel = FUELS.get(el.get("nom"))
            if fuel and station:
                ts, p = parse_maj(el.get("maj")), parse_price(el.get("valeur"))
                if ts and p is not None:
                    yield station, fuel, ts, p
            el.clear()
        elif event == "end" and el.tag == "pdv":
            el.clear()


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"days": []}


def save(data, days_by_date):
    days = [days_by_date[k] for k in sorted(days_by_date)][-KEEP_DAYS:]
    data.update({
        "updated": datetime.now(PARIS).isoformat(timespec="minutes"),
        "source": "Flux open data Prix des carburants, ministère de l'Économie (donnees.roulez-eco.fr)",
        "method": f"Moyenne arithmétique des prix déclarés, prix de moins de {STALE_DAYS} jours",
        "days": days,
    })
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(days)} jours enregistrés, dernier : {days[-1]['date'] if days else '—'}")


def day_entry(d, sums, counts):
    e = {"date": d.isoformat()}
    for fuel in FUELS.values():
        if counts.get(fuel, 0) >= 100:  # au moins 100 stations, sinon le point est ignoré
            e[fuel] = round(sums[fuel] / counts[fuel], 4)
    e["n"] = {k: counts.get(k, 0) for k in FUELS.values()}
    return e if len(e) > 2 else None


def run_daily():
    now = datetime.now(PARIS).replace(tzinfo=None)
    xml = download_xml(f"{BASE}/instantane")
    latest = {}
    for st, fuel, ts, p in iter_prices(xml):
        k = (st, fuel)
        if k not in latest or ts > latest[k][0]:
            latest[k] = (ts, p)
    sums, counts = {}, {}
    limit = now - timedelta(days=STALE_DAYS)
    for (st, fuel), (ts, p) in latest.items():
        if ts >= limit:
            sums[fuel] = sums.get(fuel, 0) + p
            counts[fuel] = counts.get(fuel, 0) + 1
    entry = day_entry(now.date(), sums, counts)
    if not entry:
        sys.exit("Flux instantané vide ou illisible : rien n'est écrit.")
    data = load()
    by_date = {d["date"]: d for d in data.get("days", [])}
    by_date[entry["date"]] = entry
    save(data, by_date)


def run_backfill(n_days):
    today = datetime.now(PARIS).date()
    start = today - timedelta(days=n_days)
    first_needed = start - timedelta(days=STALE_DAYS + 1)
    # dernier prix de chaque jour, par station et carburant
    per_key = {}
    before = {}  # dernier prix connu avant la fenêtre
    for year in sorted({first_needed.year, today.year}):
        url = f"{BASE}/annee" if year == today.year else f"{BASE}/annee/{year}"
        print("Téléchargement", url)
        for st, fuel, ts, p in iter_prices(download_xml(url)):
            d = ts.date()
            k = (st, fuel)
            if d < first_needed:
                if k not in before or ts > before[k][0]:
                    before[k] = (ts, p)
                continue
            days = per_key.setdefault(k, {})
            if d not in days or ts > days[d][0]:
                days[d] = (ts, p)
    n = (today - start).days  # jusqu'à hier : le point du jour vient du flux instantané
    sums = [dict() for _ in range(n)]
    counts = [dict() for _ in range(n)]
    for k in set(per_key) | set(before):
        fuel = k[1]
        events = sorted((d, p) for d, (ts, p) in per_key.get(k, {}).items())
        last_d, last_p = (before[k][0].date(), before[k][1]) if k in before else (None, None)
        j = 0
        for i in range(n):
            day = start + timedelta(days=i)
            while j < len(events) and events[j][0] <= day:
                last_d, last_p = events[j]
                j += 1
            if last_d is not None and (day - last_d).days <= STALE_DAYS:
                sums[i][fuel] = sums[i].get(fuel, 0) + last_p
                counts[i][fuel] = counts[i].get(fuel, 0) + 1
    data = load()
    by_date = {d["date"]: d for d in data.get("days", [])}
    for i in range(n):
        e = day_entry(start + timedelta(days=i), sums[i], counts[i])
        if e:
            by_date[e["date"]] = e
    save(data, by_date)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true", help="recalcule l'historique récent depuis le stock annuel")
    ap.add_argument("--days", type=int, default=BACKFILL_DAYS)
    a = ap.parse_args()
    run_backfill(a.days) if a.backfill else run_daily()
