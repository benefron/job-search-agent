"""Fix the 9 undecided labs with Unicode name mismatches."""
import json

DATA = "data"
labs_data = json.loads(open(f"{DATA}/labs.json").read())
curation = json.loads(open(f"{DATA}/labs_curation.json").read())
discarded = json.loads(open(f"{DATA}/labs_discarded.json").read())

labs = labs_data["labs"]

HYPHEN = "\u2010"  # Unicode HYPHEN (U+2010) used in labs.json
RSQUO = "\u2019"   # RIGHT SINGLE QUOTATION MARK

DISCARD = {
    f"Eric{HYPHEN}Jan Wagenmakers": "Bayesian statistics methodology - not neuroscience",
    "Melly S. Oitzl": "neuroendocrinology (stress hormones) - retired 2017, not target domain",
    f"Charles{HYPHEN}Th\u00e9ophile Coen": "TU/e neuromorphic - very junior (4 papers only)",
    "Vit\u00f3ria Piai": "language neuroscience / word retrieval - primarily linguistic, not comp/neuromorphic",
}

KEEP = {
    f"Aida Todri{HYPHEN}Sanial": "neuromorphic circuit design (CNT transistor arrays), TU/e - top priority",
    f"Jan{HYPHEN}Mathijs Schoffelen": "MEG/EEG connectivity / network analysis, Donders",
    "Wery van den Wildenberg": "response inhibition / action selection neuroscience, VU Amsterdam",
    "Lorena Deuker": "spatial memory coding / hippocampal place cells, Radboud",
    f"Michele D{RSQUO}Asaro": "neurorobotics and sensory integration, Radboud",
}

new_discarded = []
new_keep = {}

for lab in labs:
    name = lab["name"]
    lab_id = lab["id"]
    if name in DISCARD:
        new_discarded.append({**lab, "discard_reason": DISCARD[name]})
    elif name in KEEP:
        new_keep[lab_id] = {
            "status": "keep",
            "name": name,
            "lab": lab["lab"],
            "notes": KEEP[name],
        }

curation.update(new_keep)
open(f"{DATA}/labs_curation.json", "w").write(json.dumps(curation, indent=2, ensure_ascii=False))

discarded.extend(new_discarded)
open(f"{DATA}/labs_discarded.json", "w").write(json.dumps(discarded, indent=2, ensure_ascii=False))

discard_ids = {l["id"] for l in new_discarded}
remaining = [l for l in labs if l["id"] not in discard_ids]
labs_data["labs"] = remaining
labs_data["count"] = len(remaining)
open(f"{DATA}/labs.json", "w").write(json.dumps(labs_data, indent=2, ensure_ascii=False))

print(f"Newly discarded: {[l['name'] for l in new_discarded]}")
print(f"Newly kept:      {[v['name'] for v in new_keep.values()]}")
print(f"Final labs.json count: {labs_data['count']}")
print(f"Total curation entries: {len(curation)}")
print(f"Total discarded entries: {len(discarded)}")
