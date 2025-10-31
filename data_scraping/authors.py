# filepath: /Users/jonathanj/Work/school/DB_Proj/authors.py

"""Generate a deduplicated authors TSV from a books TSV.

Reads a books TSV (default: top1k_gbooks.tsv), finds the author(s) column, extracts
and normalizes author names, merges with an existing authors file if requested,
assigns author_id values, and writes a `unique_authors.tsv` with columns:
author_id\tname\tbirthday\tnationality

Usage examples:
    python3 authors.py
    python3 authors.py --input top1k_gbooks.tsv --output unique_authors.tsv --merge

"""

import argparse
import csv
import os
import re
import sys
import time
import json
import urllib.parse
import urllib.request
from collections import OrderedDict

NAME_SPLIT_RE = re.compile(r"\s*(?:;|\|\,|\s+and\s+|\s*&\s+|/|\\\\)\s*", flags=re.IGNORECASE)

# Try to robustly split author lists into individual names
def split_authors(field: str):
    if not field:
        return []
    # Some entries use ' and ' with commas, ensure we first replace ' and ' that is not inside a comma list
    parts = NAME_SPLIT_RE.split(field)
    names = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Convert 'Last, First' -> 'First Last'
        if ',' in p:
            # Avoid converting things like 'Smith, Jr.' badly; if there are multiple commas try to join appropriately
            comps = [c.strip() for c in p.split(',') if c.strip()]
            if len(comps) >= 2 and len(comps[0].split()) <= 3:
                # assume 'Last, First [Middle]' -> join First + Last
                p = ' '.join(comps[1:] + [comps[0]])
            else:
                p = ' '.join(comps)
        # Normalize whitespace
        p = re.sub(r"\s+", ' ', p)
        names.append(p)
    return names


def normalize_name(name: str) -> str:
    n = name.strip()
    # Collapse whitespace and remove double quotes
    n = re.sub(r"\s+", ' ', n).strip(' "\'')
    return n


def find_author_column(header):
    # Look for columns containing 'author' or common synonyms
    low = [h.lower() for h in header]
    for candidate in ('author', 'authors', 'creator', 'contributor', 'by'):
        for i, h in enumerate(low):
            if candidate in h:
                return i
    # fallback: try columns named 'author_name' or endswith 'author'
    for i, h in enumerate(low):
        if h.endswith('author') or 'author_' in h:
            return i
    return None


def read_existing_authors(path):
    authors = OrderedDict()
    max_id = 0
    if not os.path.exists(path):
        return authors, max_id
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        reader = csv.DictReader(fh, delimiter='\t')
        for row in reader:
            aid = row.get('author_id') or row.get('id')
            try:
                aid_int = int(aid) if aid else None
            except (ValueError, TypeError):
                aid_int = None
            name = row.get('name') or row.get('author') or ''
            norm = normalize_name(name).lower()
            if norm in authors:
                continue
            authors[norm] = {
                'author_id': aid_int,
                'name': name.strip(),
                'birthday': row.get('birthday', '').strip() if row else '',
                'nationality': row.get('nationality', '').strip() if row else ''
            }
            if aid_int and aid_int > max_id:
                max_id = aid_int
    return authors, max_id


def write_authors_tsv(path, authors_map):
    # authors_map is OrderedDict mapping norm->dict(author_id,name,birthday,nationality)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.writer(fh, delimiter='\t')
        writer.writerow(['author_id', 'name', 'birthday', 'nationality'])
        for norm, info in authors_map.items():
            writer.writerow([info['author_id'] or '', info['name'], info.get('birthday',''), info.get('nationality','')])
    os.replace(tmp, path)


def extract_authors_from_tsv(input_path, verbose=False):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    authors_found = []
    with open(input_path, 'r', encoding='utf-8', errors='replace') as fh:
        reader = csv.reader(fh, delimiter='\t')
        try:
            header = next(reader)
        except StopIteration:
            return []
        author_col = find_author_column(header)
        if author_col is None:
            # try to print header for debugging
            if verbose:
                print('Could not find author column in header:', header, file=sys.stderr)
            raise RuntimeError('Author column not found in TSV header')
        if verbose:
            print(f'Using author column index {author_col} (header: {header[author_col]})', file=sys.stderr)
        for row in reader:
            if author_col >= len(row):
                continue
            field = row[author_col]
            parts = split_authors(field)
            for p in parts:
                n = normalize_name(p)
                if n:
                    authors_found.append(n)
    return authors_found


WIKIDATA_SEARCH_URL = 'https://www.wikidata.org/w/api.php'
WIKIDATA_SPARQL_URL = 'https://query.wikidata.org/sparql'


def wikidata_search_entity(name: str):
    """Search Wikidata for an entity matching `name`. Returns the best match id (e.g. 'Q34660') or None.
    Uses wbsearchentities API.
    """
    params = {
        'action': 'wbsearchentities',
        'search': name,
        'language': 'en',
        'format': 'json',
        'type': 'item',
        'limit': '1'
    }
    url = WIKIDATA_SEARCH_URL + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'DB_Proj/1.0 (contact: you@example.com) Python/urllib'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    results = data.get('search') or []
    if not results:
        return None
    return results[0].get('id')


def wikidata_get_props(qid: str):
    """Given a Wikidata Q-id, query SPARQL to get dob and country/nationality labels.
    Returns dict with keys 'birthday' (ISO date) and 'nationality' (comma-separated labels) when available.
    """
    # Build SPARQL that fetches optional P569 (date of birth), P27 (country of citizenship), P172 (ethnic group/nationality)
    q = f"""
SELECT ?dob ?countryLabel ?nationalityLabel WHERE {{
  OPTIONAL {{ wd:{qid} wdt:P569 ?dob. }}
  OPTIONAL {{ wd:{qid} wdt:P27 ?country. }}
  OPTIONAL {{ wd:{qid} wdt:P172 ?nationality. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 10
"""
    params = {'query': q}
    url = WIKIDATA_SPARQL_URL + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'DB_Proj/1.0 (contact: you@example.com) Python/urllib', 'Accept': 'application/sparql-results+json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return {}
    bindings = data.get('results', {}).get('bindings', [])
    dob = None
    countries = []
    nationalities = []
    for b in bindings:
        if 'dob' in b and not dob:
            # dob value may be in xsd:dateTime format; keep date part
            v = b['dob']['value']
            dob = v.split('T')[0]
        if 'countryLabel' in b:
            countries.append(b['countryLabel']['value'])
        if 'nationalityLabel' in b:
            nationalities.append(b['nationalityLabel']['value'])
    # prefer nationalityLabel, else country
    nat = ', '.join(sorted(set(nationalities))) if nationalities else (', '.join(sorted(set(countries))) if countries else '')
    return {'birthday': dob or '', 'nationality': nat}


def enrich_authors_with_wikidata(authors_map, limit=None, force=False, verbose=False):
    """Enrich authors_map in-place. authors_map maps normalized name -> info dict.
    If force is False, only enrich entries where birthday and nationality are empty.
    limit: optional max number of authors to enrich (for safety).
    Returns number of authors enriched.
    """
    names = [n for n, info in authors_map.items()]
    enriched = 0
    for name in names:
        info = authors_map[name]
        needs = force or (not info.get('birthday') or not info.get('nationality'))
        if not needs:
            continue
        if limit is not None and enriched >= limit:
            break
        if verbose:
            print(f'Looking up "{info["name"]}" on Wikidata...', file=sys.stderr)
        qid = wikidata_search_entity(info['name'])
        time.sleep(0.6)  # be kind to the API
        if not qid:
            if verbose:
                print(f'  No Wikidata match for "{info["name"]}"', file=sys.stderr)
            continue
        props = wikidata_get_props(qid)
        time.sleep(0.6)
        if not props:
            if verbose:
                print(f'  No properties found for {qid}', file=sys.stderr)
            continue
        changed = False
        if props.get('birthday') and not info.get('birthday'):
            info['birthday'] = props['birthday']
            changed = True
        if props.get('nationality') and not info.get('nationality'):
            info['nationality'] = props['nationality']
            changed = True
        if changed:
            enriched += 1
            if verbose:
                print(f'  Enriched {info["name"]}: {props}', file=sys.stderr)
    return enriched


def main(argv=None):
    p = argparse.ArgumentParser(description='Create a deduplicated unique_authors.tsv from a books TSV')
    p.add_argument('--input', '-i', default='top1k_gbooks.tsv', help='input books TSV (default: top1k_gbooks.tsv)')
    p.add_argument('--output', '-o', default='unique_authors.tsv', help='output authors TSV (default: unique_authors.tsv)')
    p.add_argument('--merge', action='store_true', help='merge with existing output file and preserve IDs')
    p.add_argument('--dry-run', action='store_true', help="only show how many unique authors would be written")
    p.add_argument('--verbose', '-v', action='store_true', help='verbose logging')
    p.add_argument('--enrich', action='store_true', help='enrich author data with Wikidata')
    p.add_argument('--force-enrich', action='store_true', help='force re-enrichment of all authors')
    p.add_argument('--no-enrich', action='store_true', help='do not attempt Wikidata enrichment (enrichment is enabled by default)')
    p.add_argument('--enrich-limit', type=int, help='limit number of authors to enrich')
    args = p.parse_args(argv)

    try:
        found = extract_authors_from_tsv(args.input, verbose=args.verbose)
    except (FileNotFoundError, RuntimeError, OSError) as e:
        print('Error reading input TSV:', e, file=sys.stderr)
        sys.exit(2)

    # Build ordered unique map preserving first-seen canonical name
    authors_map = OrderedDict()

    start_id = 0
    if args.merge and os.path.exists(args.output):
        existing, max_id = read_existing_authors(args.output)
        authors_map.update(existing)
        start_id = max_id
        if args.verbose:
            print(f'Merged {len(existing)} existing authors, starting new ids at {start_id+1}', file=sys.stderr)

    # Add discovered authors
    for name in found:
        norm = name.lower()
        if norm in authors_map:
            continue
        authors_map[norm] = {'author_id': None, 'name': name, 'birthday': '', 'nationality': ''}

    # Assign ids to entries without one
    next_id = start_id + 1
    for _, info in authors_map.items():
        if not info.get('author_id'):
            info['author_id'] = next_id
            next_id += 1

    # Enrich with Wikidata: enabled by default unless --no-enrich. --enrich explicitly enables it; --force-enrich forces re-enrichment.
    do_enrich = (args.enrich or not args.no_enrich)
    if do_enrich:
        try:
            enriched_count = enrich_authors_with_wikidata(authors_map, limit=args.enrich_limit, force=args.force_enrich, verbose=args.verbose)
            if args.verbose:
                print(f'Enriched {enriched_count} authors with Wikidata', file=sys.stderr)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # Don't abort on enrichment errors; write whatever we have and warn.
            print('Warning: Wikidata enrichment failed:', e, file=sys.stderr)

    if args.dry_run:
        print(f'Unique authors discovered: {len(authors_map)}')
        return

    write_authors_tsv(args.output, authors_map)
    if args.verbose:
        print(f'Wrote {len(authors_map)} authors to {args.output}', file=sys.stderr)
    else:
        print(f'Wrote {len(authors_map)} authors to {args.output}')


if __name__ == '__main__':
    main()