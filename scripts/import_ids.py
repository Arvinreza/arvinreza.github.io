#!/usr/bin/env python3
"""Inspect and import the IDS Mannheim author bibliography."""
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
import re

URL = "https://pub.ids-mannheim.de/autoren/ids/koplenig.html"
r = Request(URL, headers={"User-Agent":"Mozilla/5.0 (Academic bibliography importer; contact via https://github.com/Koplenig/koplenig.github.io)"})
with urlopen(r, timeout=25) as f:
    html = f.read().decode("utf-8",errors="replace")
print("Fetched HTML bytes:", len(html))
soup = BeautifulSoup(html, "html.parser")
for s in soup.find_all(string=re.compile(r"Koplenig, Alexander \(2016\)|Coding choices and short-sequence"))[:8]:
    print("MATCH TEXT",repr(str(s)[:350]))
    p=s.parent
    for i in range(5):
        print(f"Ancestor {i}: tag={p.name} class={p.get('class')} id={p.get('id')} TEXT={p.get_text(' ',strip=True)[:500]!r}")
        if i==2: print("HTML SAMPLE",str(p)[:4000])
        p=p.parent
