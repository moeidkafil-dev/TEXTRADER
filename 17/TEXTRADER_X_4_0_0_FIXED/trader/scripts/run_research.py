from __future__ import annotations
import argparse, json
from trader.research import ResearchEngine

def main():
    p=argparse.ArgumentParser(); p.add_argument('query', nargs='?', default='trading risk management')
    a=p.parse_args(); r=ResearchEngine(); print(json.dumps(r.search(a.query), indent=2, ensure_ascii=False))
if __name__=='__main__': main()
