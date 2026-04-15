#!/usr/bin/env python3
"""Dump Allfred Workspace GraphQL schema snippets (invoice / quick setup) via introspection.

Requires ALLFRED_API_KEY and optional ALLFRED_WORKSPACE (default redbuttonedu).
Run from repo root:  python3 scripts/allfred_introspect.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types { ...FullType }
  }
}
fragment FullType on __Type {
  kind name
  fields(includeDeprecated: true) {
    name args { name type { kind name ofType { kind name ofType { kind name } } } }
    type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
  }
  inputFields {
    name
    type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
  }
  enumValues(includeDeprecated: true) { name }
}
"""


def main() -> int:
    key = (os.environ.get("ALLFRED_API_KEY") or "").strip()
    if not key:
        print("Set ALLFRED_API_KEY", file=sys.stderr)
        return 1
    ws = (os.environ.get("ALLFRED_WORKSPACE") or "redbuttonedu").strip()
    url = f"https://{ws}-api.allfred.io/workspace-api"
    body = json.dumps({"query": INTROSPECTION_QUERY}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.read().decode()[:2000], file=sys.stderr)
        return e.code

    if data.get("errors"):
        print(json.dumps(data["errors"], indent=2))
        return 2

    types = {t["name"]: t for t in data["data"]["__schema"]["types"] if t.get("name")}

    def dump_type(name: str) -> None:
        t = types.get(name)
        print(f"\n=== {name} ===")
        if not t:
            print("(missing)")
            return
        if t.get("inputFields"):
            for inf in sorted(t["inputFields"], key=lambda x: x["name"]):
                print(f"  {inf['name']}: {json.dumps(inf['type'])}")
        elif t.get("enumValues"):
            for ev in t["enumValues"]:
                print(f"  {ev['name']}")
        else:
            print(json.dumps(t, indent=2)[:4000])

    for n in (
        "QuickSetupInput",
        "QuickSetupClientDataInput",
        "QuickSetupProjectInput",
        "QuickSetupInvoiceInput",
        "QuickSetupInvoiceItemInput",
        "QuickSetupInvoiceTypeEnum",
        "QuickSetupResult",
    ):
        dump_type(n)

    mt = types.get("Mutation")
    if mt and mt.get("fields"):
        print("\n=== Mutation fields ===")
        for f in sorted(mt["fields"], key=lambda x: x["name"]):
            print(f"  {f['name']}")

    qt = types.get("Query")
    if qt and qt.get("fields"):
        print("\n=== Query fields (invoice / proforma / client) ===")
        for f in sorted(qt["fields"], key=lambda x: x["name"]):
            n = f["name"]
            if any(x in n.lower() for x in ("invoice", "proforma", "client")):
                print(f"  {n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
