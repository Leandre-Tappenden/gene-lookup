#!/usr/bin/env python3
"""Look up a human gene symbol using the mygene.info REST API."""

import argparse
import json
import sys
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


API_URL = "https://mygene.info/v3/query"
FIELDS = "symbol,name,summary,entrezgene,ensembl,type_of_gene,alias"


def fetch_gene(symbol: str) -> Optional[Dict]:
    """Return the best human-gene match for *symbol*, if one exists."""
    params = urlencode(
        {
            "q": "symbol:" + symbol,
            "species": "human",
            "fields": FIELDS,
            "size": 1,
        }
    )

    try:
        with urlopen(f"{API_URL}?{params}", timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"mygene.info returned HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach mygene.info: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("mygene.info returned invalid JSON.") from error

    hits = payload.get("hits", [])
    return hits[0] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a human gene's basic information and summary from mygene.info."
    )
    parser.add_argument("gene_symbol", help="Gene symbol to look up (for example, BRCA1)")
    args = parser.parse_args()

    try:
        gene = fetch_gene(args.gene_symbol)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if gene is None:
        print(f"No human gene found for symbol: {args.gene_symbol}", file=sys.stderr)
        return 2

    print(f"Symbol: {gene.get('symbol', 'Unknown')}")
    print(f"Name: {gene.get('name', 'Unknown')}")
    print(f"Entrez ID: {gene.get('entrezgene', 'Unknown')}")
    print(f"Gene type: {gene.get('type_of_gene', 'Unknown')}")

    ensembl = gene.get("ensembl")
    if isinstance(ensembl, list):
        ensembl = ", ".join(item.get("gene", "") for item in ensembl if item.get("gene"))
    elif isinstance(ensembl, dict):
        ensembl = ensembl.get("gene")
    print(f"Ensembl ID: {ensembl or 'Unknown'}")

    aliases = gene.get("alias", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    print(f"Aliases: {', '.join(aliases) if aliases else 'None'}")
    print(f"\nSummary:\n{gene.get('summary', 'No summary available.')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
