"""Add web-searched researchers to labs.json."""
import json, hashlib
from datetime import datetime, timezone

with open('data/labs.json') as f:
    data = json.load(f)

existing_names = {l['name'].lower() for l in data['labs']}


def make_id(name):
    return hashlib.md5(name.encode()).hexdigest()[:16]


def make_entry(name, lab, location, topic, url, notes=""):
    return {
        "id": make_id(name),
        "name": name,
        "lab": lab,
        "location": location,
        "topic": topic,
        "url": url,
        "orcid_url": "",
        "google_url": f"https://www.google.com/search?q={name.replace(' ', '%20')}%20{location}%20neuroscience%20research",
        "scholar_url": f"https://scholar.google.com/scholar?q={name.replace(' ', '%20')}%20{lab.replace(' ','%20')}",
        "works_count": 0,
        "source": "web_search",
        "notes": notes,
    }


NEW_ENTRIES = [
    # ── ROTTERDAM ──────────────────────────────────────────────────────────────
    make_entry(
        "Mario Negrello",
        "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "computational neuroscience",
        "https://pure.eur.nl/en/persons/mario-negrello",
        "Co-lead NCL with Strydis; cerebellar oscillations, EDEN simulator, Purkinje cell dynamics",
    ),
    make_entry(
        "George Smaragdos",
        "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "FPGA/GPU brain simulation",
        "https://pure.eur.nl/en/persons/george-smaragdos",
        "PhD 2024; heterogeneous FPGA acceleration of brain simulations; flexHH FPGA library",
    ),
    make_entry(
        "Lennart Landsmeer",
        "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "neuromorphic computing",
        "https://pure.eur.nl/en/persons/lennart-landsmeer",
        "Memristor neuromorphic for Hodgkin-Huxley; AI-chip brain simulation; FPGA accelerators",
    ),
    make_entry(
        "Muhammad Ali Siddiqi",
        "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "brain-computer interface",
        "https://pure.eur.nl/en/persons/muhammad-ali-siddiqi",
        "Lightweight hardware for real-time neuronal spike classification; neuromodulation; BCI",
    ),
    make_entry(
        "Rene Miedema",
        "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "neural simulation",
        "https://pure.eur.nl/en/persons/rene-miedema",
        "EDEN modular neurosimulator; HPC/GPU for brain simulation; performance analysis of AI chips",
    ),
    make_entry(
        "Sadaf Soloukey Tbalvandany",
        "Erasmus MC – Dept. of Neurosurgery",
        "Rotterdam",
        "brain-computer interface",
        "https://pure.eur.nl/en/persons/sadaf-soloukey-tbalvandany",
        "Mobile functional ultrasound (fUS) brain imaging with skull implants; BCI-adjacent; Science Advances 2025",
    ),
    make_entry(
        "Aleksandra Badura",
        "Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "computational neuroscience",
        "https://pure.eur.nl/en/persons/aleksandra-badura",
        "Neural networks for behavioral flexibility; cerebello-cortical circuits; autism; Veni+Vidi grants",
    ),
    make_entry(
        "Vincenzo Romano",
        "Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "systems neuroscience",
        "https://pure.eur.nl/en/persons/vincenzo-romano",
        "Cerebellar-cortical circuits; co-author spike classification hardware paper (Siddiqi/Strydis); Veni 2023",
    ),
    make_entry(
        "Chris de Zeeuw",
        "De Zeeuw Lab, Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "systems neuroscience",
        "https://pure.eur.nl/en/persons/chris-de-zeeuw",
        "Dept. chair; cerebellar plasticity; motor learning; hosted NCN2025 neuromorphic event; 400+ pubs",
    ),
    make_entry(
        "Bas Koekkoek",
        "Erasmus MC – Dept. of Neurosciences",
        "Rotterdam",
        "brain-computer interface",
        "https://pure.eur.nl/en/persons/bas-koekkoek",
        "Functional ultrasound (fUS) brain imaging; neurobehavioral assessment; BCI-adjacent",
    ),
    make_entry(
        "Devika Narain",
        "Circuit Dynamics Lab, Erasmus MC – Dept. of Neuroscience",
        "Rotterdam",
        "computational neuroscience",
        "https://neuro.nl/person/Devika-Narain",
        "Bayesian computations in neural circuits; cortico-cerebellar loops; timing; NWO Vidi+ERC; 2025 Early Career Award",
    ),
    # ── EINDHOVEN (new) ───────────────────────────────────────────────────────
    make_entry(
        "Elena Petri",
        "Control Systems Technology, TU/e – Mechanical Engineering",
        "Eindhoven",
        "neuromorphic computing",
        "https://research.tue.nl/en/persons/elena-petri",
        "Neuromorphic controllers for hybrid dynamical systems; nuclear fusion plasma fuelling; CDC 2024/2025",
    ),
    make_entry(
        "Federico Corradi",
        "Neuromorphic Edge Computing Systems Lab, TU/e – Electrical Engineering",
        "Eindhoven",
        "neuromorphic computing",
        "https://research.tue.nl/en/persons/federico-corradi",
        "Leads NECS Lab; neuromorphic CMOS ICs; spiking NNs; BMI; previously IMEC Netherlands; EAISI",
    ),
    make_entry(
        "Bert de Vries",
        "BIASlab, TU/e – Signal Processing Systems",
        "Eindhoven",
        "computational neuroscience",
        "https://research.tue.nl/en/persons/a-bert-de-vries",
        "Active inference; factor graphs; Bayesian ML inspired by computational neuroscience; co-authored with Karl Friston",
    ),
    make_entry(
        "Wouter Kouw",
        "BIASlab, TU/e – Signal Processing Systems",
        "Eindhoven",
        "computational neuroscience",
        "https://research.tue.nl/en/persons/wouter-kouw",
        "Active inference agents; Bayesian message passing; MSc in Neuroscience (Maastricht); ELLIS 2025",
    ),
    make_entry(
        "Roel Jordans",
        "Neuromorphic Edge Computing Systems Lab, TU/e – Electrical Engineering",
        "Eindhoven",
        "neuromorphic computing",
        "https://research.tue.nl/en/persons/roel-jordans",
        "BrainSense EEG BCI headset PI; spiking processor hardware/compilers; co-teaches Neuro computation",
    ),
    # ── AMSTERDAM (new) ───────────────────────────────────────────────────────
    make_entry(
        "Serge Dumoulin",
        "Dumoulin Group / Spinoza Centre for Neuroimaging, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/dumoulin/",
        "Population receptive field (pRF) models; 7T fMRI; neural encoding models; biologically-inspired AI",
    ),
    make_entry(
        "Tomas Knapen",
        "Cognitive Psychology / IBBA, VU Amsterdam + NIN",
        "Amsterdam",
        "computational neuroscience",
        "https://research.vu.nl/en/persons/tomas-knapen",
        "Computational neuroimaging; pRF models; visual cortex; decision-making; reinforcement learning",
    ),
    make_entry(
        "Wietske van der Zwaag",
        "Spinoza Centre / Dumoulin Group, NIN Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/dumoulin/",
        "Ultra-high field MRI; laminar fMRI; cerebellar imaging; NWO Vici 2025",
    ),
    make_entry(
        "Marcel Oberlaender",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/marcel_oberlaender/",
        "Computational neuroanatomy; in silico brain sciences; 3D cortical circuit reconstruction",
    ),
    make_entry(
        "Klaus Linkenkaer-Hansen",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/linkenkaer-hansen_k/",
        "Brain oscillations; neuronal avalanches; self-organised criticality; EEG biomarkers",
    ),
    make_entry(
        "Conrado Bosman Vittini",
        "Cognitive and Systems Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/profile/b/o/c.a.bosmanvittini/c.a.bosmanvittini.html",
        "Cortical microcircuits; neural oscillations; gamma rhythms; multisensory integration; attention",
    ),
    make_entry(
        "Jan Willem de Gee",
        "Cognitive and Systems Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/profile/g/e/j.w.degee/j.w.de-gee.html",
        "Neuromodulation of decision computations; arousal; pupillometry; signal detection theory",
    ),
    make_entry(
        "Natalia Goriounova",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/natalia_goriounova/",
        "Human neuron circuits; cellular basis of intelligence; ERC Consolidator (HumanCircuits)",
    ),
    make_entry(
        "Huib Mansvelder",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/mansvelder_hd/",
        "Neural circuits; prefrontal cortex; neuromodulation; multi-electrode recordings; dept. head INF",
    ),
    make_entry(
        "Christiaan de Kock",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/cpj_kock/",
        "Cortical networks; single-neuron morphology; barrel cortex; somatosensory processing",
    ),
    make_entry(
        "Umberto Olcese",
        "Cognitive and Systems Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/profile/o/l/u.olcese/u.olcese.html",
        "Neural basis of consciousness; feedback circuits; large-scale neural recordings",
    ),
    make_entry(
        "Alexander Heimel",
        "Heimel Group, NIN Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/heimel/",
        "Visual circuits; mouse visual cortex; instinctive visual behaviour; optogenetics; two-photon imaging",
    ),
    make_entry(
        "Helmut Kessels",
        "Cellular and Circuit Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/content/research-groups/cellular-and-computational-neuroscience/cellular-and-circuit-neuroscience.html",
        "Synaptic plasticity; LTP/LTD; circuit homeostasis; network activity",
    ),
    make_entry(
        "Natalie Cappaert",
        "Cellular and Circuit Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/content/research-groups/cellular-and-computational-neuroscience/",
        "Hippocampal-cortical circuits; connectivity; circuit mapping",
    ),
    make_entry(
        "Marlies Oostland",
        "Cellular and Circuit Neuroscience, UvA SILS",
        "Amsterdam",
        "computational neuroscience",
        "https://sils.uva.nl/content/research-groups/cellular-and-computational-neuroscience/",
        "Cerebellar contribution to cognition; cortico-cerebellar circuits; development",
    ),
    make_entry(
        "Christiaan Levelt",
        "Levelt Group, NIN + CNCR VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/levelt/",
        "Visual cortex plasticity; critical periods; inhibitory neuron circuits; ocular dominance plasticity",
    ),
    make_entry(
        "Rogier Min",
        "INF / CNCR, VU Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://cncr.nl/people/min_r/",
        "Glial-neuron interactions; synaptic properties; circuit computations",
    ),
    make_entry(
        "Francesca Siclari",
        "Siclari Group, NIN Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/siclari/",
        "Sleep and dreaming; consciousness; EEG signatures of awareness; bistable brain dynamics",
    ),
    make_entry(
        "Maarten Kole",
        "Kole Group, NIN Amsterdam",
        "Amsterdam",
        "computational neuroscience",
        "https://nin.nl/research-groups/kole-2/",
        "Axonal signal conduction; action potential biophysics; myelin; computational electrophysiology",
    ),
    # ── LEIDEN (new) ──────────────────────────────────────────────────────────
    make_entry(
        "Anne Urai",
        "CoCoSys Lab, Leiden University – Cognitive Psychology",
        "Leiden",
        "computational neuroscience",
        "https://www.universiteitleiden.nl/en/staffmembers/anne-urai",
        "Bayesian decision computing; psychophysics; neurophysiology; Int'l Brain Lab; Rising Stars of Neuroscience 2025",
    ),
    make_entry(
        "Nic van der Wee",
        "LUMC – Dept. of Psychiatry / Brain Function and Behavior",
        "Leiden",
        "neuroimaging",
        "https://www.lumc.nl/en/research/themes-for-innovation/neuroscience/brain-function--behavior/",
        "Stress-related disorders; fMRI; low-field MRI; Brainformatics initiative; glymphatic imaging",
    ),
    make_entry(
        "Lydiane Hirschler",
        "LUMC – Dept. of Radiology / Brain Function and Behavior",
        "Leiden",
        "neuroimaging",
        "https://www.lumc.nl/en/research/themes-for-innovation/neuroscience/brain-function--behavior/",
        "Novel non-invasive MRI; low-field MRI; glymphatic system imaging; methodology-focused",
    ),
    # ── UTRECHT (new) ─────────────────────────────────────────────────────────
    make_entry(
        "Nick Ramsey",
        "Utrecht-BCI Lab, UMC Utrecht – Dept. of Neurology and Neurosurgery",
        "Utrecht",
        "brain-computer interface",
        "https://research.umcutrecht.nl/researchers/ramsey/",
        "World-first fully implanted home-use BCI for ALS/locked-in; ECoG; ERC Advanced Grant; utrecht-bci.nl",
    ),
    make_entry(
        "Julia Berezutskaya",
        "Utrecht-BCI Lab, UMC Utrecht – Dept. of Neurology and Neurosurgery",
        "Utrecht",
        "brain-computer interface",
        "https://research.umcutrecht.nl/researchers/julia-berezutskaya",
        "Brain signal decoding; ALPACA BCI for cerebral palsy; FES muscle reanimation; J Neural Engineering",
    ),
]

# Deduplicate against existing
added = 0
skipped = 0
for entry in NEW_ENTRIES:
    if entry["name"].lower() in existing_names:
        print(f"  SKIP (exists): {entry['name']}")
        skipped += 1
    else:
        data["labs"].append(entry)
        existing_names.add(entry["name"].lower())
        print(f"  ADD: {entry['name']} [{entry['location']}]")
        added += 1

# Fix Christos Strydis location from Delft → Rotterdam (primary lab)
for lab in data["labs"]:
    if lab["name"] == "Christos Strydis" and lab.get("location") == "Delft":
        lab["location"] = "Rotterdam"
        lab["lab"] = "Neurocomputing Lab, Erasmus MC – Dept. of Neurosciences"
        print("  FIXED: Christos Strydis location → Rotterdam")

# Fix Wouter Serdijn — he's primarily at TU Delft but added Rotterdam entry too
# The Delft entry already exists; no action needed (he truly has dual appointment)

# Update metadata
data["count"] = len(data["labs"])
data["generated"] = datetime.now(timezone.utc).isoformat()

with open("data/labs.json", "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nDone: +{added} added, {skipped} skipped. Total: {data['count']}")
