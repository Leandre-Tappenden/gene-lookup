#!/usr/bin/env python3
"""Look up a human gene symbol using the mygene.info REST API."""

import argparse
import json
import os
import sys
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import anthropic


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


def summarize_with_claude(gene: Dict) -> str:
    """Ask Claude to turn the retrieved gene record into plain English."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    gene_details = {
        "symbol": gene.get("symbol"),
        "name": gene.get("name"),
        "type_of_gene": gene.get("type_of_gene"),
        "summary": gene.get("summary"),
    }
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            system=(
                "You explain biological information accurately for a general audience. "
                "Do not provide medical advice."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Using only the following gene record, write one concise, "
                        "plain-English paragraph describing the gene's function. "
                        "Do not use headings or bullet points.\n\n"
                        + json.dumps(gene_details)
                    ),
                }
            ],
        )
    except anthropic.APIError as error:
        raise RuntimeError(f"Claude API request failed: {error}") from error

    text_parts = [block.text for block in response.content if block.type == "text"]
    if not text_parts:
        raise RuntimeError("Claude returned no text summary.")
    return " ".join(text_parts).strip()


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

    try:
        plain_english_summary = summarize_with_claude(gene)
    except RuntimeError as error:
        print(f"\nClaude summary unavailable: {error}", file=sys.stderr)
        return 1

    print(f"\nPlain-English summary:\n{plain_english_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
