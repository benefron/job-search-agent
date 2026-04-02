"""
One-shot curation: apply keep/discard decisions to labs.json based on
manual domain analysis of all 222 entries.

Run: python scripts/_curate_labs_auto.py
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

labs_data = json.loads((DATA_DIR / "labs.json").read_text())
labs = labs_data["labs"]

# ─── DISCARD: clearly irrelevant domains ─────────────────────────────────────
DISCARD = {
    "A. E. Eiben": "evolutionary computing / CS, not neuroscience",
    "Albert J. Menkveld": "finance professor (asset pricing), unrelated",
    "Alexandru Iosup": "distributed systems / cloud computing",
    "Alida A. Gouw": "proteomics / molecular neuroscience (clinical)",
    "Arianna Bisazza": "NLP / computational linguistics (Groningen)",
    "Claudia D. van Borkulo": "psychological network analysis (clinical)",
    "Erik Rietveld": "philosophy of mind / phenomenology",
    "Freek Ariese": "analytical chemistry / spectroscopy",
    "Iacer Calixto": "NLP / machine translation",
    "J. Swinbank": "radio astronomy (ASTRON)",
    "Jaap Kamps": "information retrieval / text mining",
    "Joppe W. Hovius": "infectious diseases (Lyme disease)",
    "Julian Kiverstein": "philosophy of consciousness (Dutch Cancer Society)",
    "L. Bähren": "radio astronomy (ASTRON)",
    "M.H. Lamoree": "environmental chemistry / ecotoxicology",
    "Maarten Marsman": "Bayesian stats / psychometrics",
    "Maarten de Rijke": "information retrieval / text search",
    "Marian Joëls": "hormone effects on brain stress (UMCG, not target region)",
    "Menno M. Schoonheim": "multiple sclerosis neuroimaging (clinical)",
    "Pim de Voogt": "environmental chemistry / water research",
    "Ravi Selker": "psychiatry / mental health (Altrecht GGZ)",
    "Sebastiaan Mathôt": "pupillometry (Groningen, not target region)",
    "Shahram Janbaz": "soft robotics / metamaterials (CWI)",
    "Warner S. Simonides": "cardiac muscle physiology",
    "Wim van den Brink": "addiction psychiatry",
    "Frank A. W. Coumans": "extracellular vesicles / biochemistry",
    "Frederik Barkhof": "neuroradiology (clinical MS imaging)",
    "Dóra Matzke": "Bayesian statistics in cognitive science",
    "Eric\u2011Jan Wagenmakers": "Bayesian statistics methodology",
    "Daniël Schreij": "cognitive science (junior, low impact)",
    # Dóra alternative spelling
    "Eric-Jan Wagenmakers": "Bayesian statistics methodology",
    "Joris J. Carmiggelt": "nanoscale physics (not neuroscience)",
    "Hanneke K. M. Meeren": "clinical neurophysiology (epilepsy surgery - clinical)",
    "Alejandro M. Aragón": "computational mechanics (FEM)",
    "Aurora Micheli": "graph neural networks (pure ML, no bio-neuro angle)",
    "Bart De Schutter": "control theory / traffic control",
    "Caiseal Beardow": "very junior / 2 papers only",
    "D. W. F. van Krevelen": "augmented reality / IT company (Almende)",
    "June Sallou": "software quality at Wageningen (wrong region + domain)",
    "Luís Cruz": "sustainable software engineering",
    "Mohammad J. Mirzaali": "biomechanics / 3D-printed bone scaffolds",
    "Toeno van der Sar": "quantum physics / NV centers",
    "Alex Alvarado": "information theory / communications engineering",
    "B. Koopmans": "spintronic neuromorphic (materials physics, too tangential)",
    "Charles\u2011Théophile Coen": "very junior / 4 papers only",
    "Daniël Lakens": "open science / statistics methodology",
    "Jaap M. J. den Toonder": "microfluidics / soft matter",
    "Michael G. Debije": "luminescent solar concentrators",
    "Nicola Calabretta": "optical packet switching / networks",
    "Setareh Kazemzadeh": "very junior / 6 papers",
    "Bart Verkuil": "health psychology (stress-related illness)",
    "Catholijn M. Jonker": "multi-agent systems / normative AI",
    "Eiko I. Fried": "psychiatric network epidemiology",
    "H. T. Intema": "radio astronomy (Leiden)",
    "Rebecca Schaefer": "music cognition (not engineering)",
    "Robert Passier": "stem cell biology / cardiac",
    "Sebo Uithol": "philosophy of action",
    "Suzan Verberne": "NLP / information retrieval",
    "A. Kirilyuk": "nonlinear magnetics / condensed matter physics",
    "A. V. Kimel": "spintronics / laser-induced spin dynamics",
    "Anouk Scheres": "ADHD / developmental (clinical psych)",
    "Arnt Schellekens": "addiction medicine (NIN — clinical, not research lab)",
    "D. Afanasiev": "quantum physics / condensed matter",
    "Gabriëlle Ras": "explainable AI (no neuro angle)",
    "H. Bekkering": "duplicate of Harold Bekkering",
    "Heiko Ramm": "unclear / low papers",
    "Iris Hendrickx": "computational linguistics / NLP",
    "Iris van Rooij": "theoretical psychology / computational complexity",
    "J.R. Hörandel": "cosmic ray astrophysics",
    "Jeroen Geuze": "very low papers / unclear domain",
    "Johan H. Mentink": "spintronics / magnon dynamics",
    "Johan Mentink": "duplicate of Johan H. Mentink / 1 paper",
    "M. Anastasoaie": "astrophysics",
    "Nikolas Leßmann": "deep learning for radiology (clinical imaging, not neuro)",
    "P. Groot": "machine learning / medical informatics",
    "Peter Pickkers": "intensive care medicine (clinical)",
    "Rutger Vlek": "ecological acoustics at Wageningen (wrong domain + region)",
    "Th. Rasing": "spintronics / photonics (condensed matter)",
    "A. J. van der Lely": "endocrinology (growth hormone, Erasmus MC)",
    "Amber Yaqub": "clinical neurology / aging imaging (Erasmus MC)",
    "Guy Shpak": "biological pest control (Koppert Biological Systems)",
    "Luc E. Coffeng": "infectious disease epidemiology",
    "Natasja M.S. de Groot": "cardiac electrophysiology (atrial fibrillation)",
    "Richard Franciscus Johannes Haans": "entrepreneurship / marketing (Erasmus)",
    "Witte J.G. Hoogendijk": "depression / psychiatry (Erasmus MC)",
    "E. R. de Kloet": "neuroendocrinology (cortisol / glucocorticoids)",
    "Erno Vreugdenhil": "molecular neurobiology of epilepsy (LUMC)",
    "Harsha D. Devalla": "cardiac development / iPSC (Amsterdam UMC listed in The Hague)",
    "Jan J.G.M. Verschuuren": "neuromuscular disease / myasthenia gravis (clinical)",
    "Marcelo C. Ribeiro": "CRO / toxicology (Charles River Laboratories)",
    "Valeria V. Orlova": "vascular biology / endothelial cells",
    "Albert J. M. van Wijck": "pain medicine / anesthesiology (Utrecht, clinical)",
    "Annemarie P. van Wezel": "Dutch language / linguistics",
    "Bianca Kramer": "research data management / open science",
    "Duco Veen": "Bayesian statistics / measurement",
    "Francesca Grisoni": "AI for drug discovery (HU Utrecht)",
    "Hajo A. Reijers": "business process management",
    "Herbert Hoijtink": "Bayesian statistics",
    "Karel G.M. Moons": "clinical epidemiology (UMC Utrecht)",
    "M. R. Duvoort": "unclear / low relevance",
    "Maarten van Smeden": "clinical epidemiology / diagnostic research",
    "Marco Helbich": "spatial epidemiology / geospatial health",
    "Rens van de Schoot": "Bayesian statistics methodology",
    "Tim Stevens": "genome organization (Utrecht, wrong domain)",
    "Willem Stoorvogel": "systems control theory (pure engineering maths)",
    "Anton Nijholt": "BCI / HCI at U Twente (outside target region — Enschede)",
    "Roland Bullens": "Philips researcher / sparse record — unclear domain",
    "Aaron Yi Ding": "mobile/edge computing (tangential, low relevance for labs)",
    "Douwe den Blanken": "bio-inspired flight control (TU Delft, very junior — 4 papers)",
}

# ─── KEEP with notes ─────────────────────────────────────────────────────────
KEEP = {
    # Amsterdam
    "Bernadette C.M. van Wijk": "neural oscillations / computational neuroscience, Amsterdam Neuroscience",
    "Marijn van Wingerden": "electrophysiology of decision-making circuits, Tilburg",
    "Andreas Daffertshofer": "neural oscillations / motor neuroscience, VU Amsterdam",
    "Christian N. L. Olivers": "visual working memory / attentional selection, VU Amsterdam",
    "Cornelis J. Stam": "brain network dynamics / computational neuroscience, NIN",
    "Cyriel M. A. Pennartz": "systems and computational neuroscience, UvA Amsterdam",
    "F. H. Lopes da Silva": "EEG pioneer / neural networks (NIN, emeritus — low priority)",
    "Fernando H. Lopes da Silva": "EEG pioneer (NIN) — same as above, duplicate",
    "Floris G. Wouterlood": "neuroanatomy / tracing, Amsterdam Neuroscience",
    "Jan Theeuwes": "visual attention / oculomotor neuroscience, NIN Amsterdam",
    "Jorge F. Mejías": "theoretical / computational neuroscience, NIN — high priority!",
    "K. Richard Ridderinkhof": "cognitive neuroscience / executive control, UvA",
    "Maurits W. van der Molen": "cognitive neuroscience / ERP, UvA Amsterdam",
    "Max C. Keuken": "basal ganglia ultra-high-field MRI, UvA Amsterdam",
    "Max Welling": "deep learning / graph neural nets / equivariance, UvA/Microsoft",
    "Milan Jelisavcic": "evolutionary robotics, VU Amsterdam",
    "Pieter R. Roelfsema": "visual cortex computation / feedback / neuromorphic vision, NIN director — top priority!",
    "Sander M. Bohté": "spiking neural networks / neuromorphic computing, NIN — top priority!",
    "Sindy Löwe": "self-supervised learning / neural latent structure, UvA",
    "Victor A. F. Lamme": "visual cortex / feedforward-feedback dynamics, NIN",
    "Jeroen Meijer": "circadian pacemaker / in vivo electrophysiology (NIN/VU Amsterdam)",
    # Delft
    "Abhairaj Singh": "neuromorphic hardware / memristive devices, TU Delft",
    "Alfred C. Schouten": "neuro-robotics / brain-machine interface, TU Delft",
    "Anne C. Sittig": "haptic perception / sensorimotor neuroscience, TU Delft",
    "Charlotte Frenkel": "neuromorphic VLSI chip design, TU Delft — top priority!",
    "David A. Abbink": "human-robot shared control / neural adaptation, TU Delft",
    "Gijs Huisman": "haptic technology / social touch, TU Delft",
    "Guido de Croon": "neuromorphic drone navigation / event cameras, TU Delft — top priority!",
    "Herman van der Kooij": "exoskeleton neurorehabilitation, U Twente (adjacent region)",
    "J. Micah Prendergast": "bio-inspired optical-flow sensing, TU Delft",
    "Luka Peternel": "adaptive human-in-the-loop robotics, TU Delft",
    "Nergis Tömen": "bio-inspired visual computing / attention, TU Delft",
    "Said Hamdioui": "neuromorphic in-memory computing, TU Delft — top priority!",
    "Sorin Cotöfană": "beyond-CMOS / neuromorphic circuits, TU Delft",
    "Tom Driessen": "haptic interfaces / tactile feedback, TU Delft (junior)",
    # Eindhoven / imec
    "Aida Todri\u2011Sanial": "neuromorphic circuit design, TU/e — top priority!",
    "Amirreza Yousefzadeh": "event-driven vision / SNN hardware, imec NL — top priority!",
    "Chengyao Shi": "neuromorphic sensor processing, imec NL",
    "Dimitrios A. Koutsouras": "organic neuromorphic transistors, imec NL — top priority!",
    "Emilia Barakova": "social robotics / HRI, TU/e Eindhoven",
    "Filip Sabo": "neuromorphic signal processing, TU/e",
    "Geert Langereis": "sensor IC / bioelectronics, imec NL",
    "Gert-Jan van Schaik": "neural signal processing, imec NL",
    "Guangzhi Tang": "SNN for event cameras / robotics, imec NL — top priority!",
    "Henk Corporaal": "embedded processor / neuromorphic architectures, TU/e",
    "Jan Stuijt": "ultra-low-power neuromorphic IC, imec NL",
    "Joaquin Vanschoren": "AutoML / meta-learning / OpenML, TU/e",
    "Kanishkan Vadivel": "neuromorphic SNN hardware, imec NL",
    "Kevin Shidqi": "neuromorphic processor design, imec NL",
    "Koen de Bruin": "spike-based computing (TU/e, junior)",
    "Manolis Sifalakis": "neuromorphic computing systems, imec NL",
    "Mario Konijnenburg": "mixed-signal IC / bioelectronics, imec NL",
    "Martijn Timmermans": "event-driven sensor processing, TU/e",
    "Paul Hueber": "imec NL neuromorphic sensor",
    "Pieter Harpe": "ultra-low-power ADC / bioelectronics IC, TU/e",
    "Sander Stuijk": "embedded / dataflow computing for AI, TU/e",
    "Shenqi Wang": "imec NL neuromorphic",
    "Shrishail Patki": "neuromorphic computing, imec NL",
    "Stan van der Ven": "imec NL event-driven sensor IC",
    "Stefano Traferro": "neuromorphic processor design, imec NL",
    "Yingfu Xu": "SNN accelerator IC design, imec NL",
    # Leiden
    "Aske Plaat": "deep reinforcement learning, Leiden University",
    "Bernhard Hommel": "action-perception coupling / cognitive neuroscience, Leiden",
    "Eveline A. Crone": "developmental cognitive neuroscience / fMRI, Leiden",
    "Jesper E. van Engelen": "semi-supervised / graph ML, Leiden (junior)",
    "Joost Broekens": "affective computing / HRI emotion, Leiden",
    "Marieke Jepma": "pain neuroscience / pupil-linked arousal, Leiden",
    "Roman Yasenkov": "in vivo sleep recording / Leiden",
    "Roy de Kleijn": "neural models of saccades / robotics-neuro, Leiden",
    "Sander Nieuwenhuis": "locus coeruleus-NE / pupil / cognitive control, Leiden — high priority!",
    "Serge A.R.B. Rombouts": "neuroimaging methods / MRI connectivity, Leiden",
    # Nijmegen / Donders
    "A.M.L. Coenen": "EEG / epilepsy neurophysiology, Radboud",
    "Alan G. Sanfey": "neuroeconomics / social decision neuroscience, Donders",
    "André F. Marquand": "normative modeling / comp psychiatry, Donders — high priority!",
    "Atsuko Takashima": "memory consolidation / sleep oscillations, Radboud",
    "Christian F. Beckmann": "fMRI methods / ICA / resting-state, Donders",
    "Eric Maris": "EEG cluster permutation testing, Donders",
    "Erno J. Hermans": "stress and episodic memory / neural systems, Donders",
    "Harold Bekkering": "motor cognition / action understanding / development, Donders",
    "Jan\u2011Mathijs Schoffelen": "EEG/MEG connectivity / network analysis, Donders",
    "Jason Farquhar": "BCI / EEG signal processing, Donders/MPI",
    "Lieke van Lieshout": "motivation / motor cognition, Donders",
    "Luke E. Miller": "somatosensory / sensorimotor integration, Donders",
    "Marcel van Gerven": "computational neuroscience / deep-net brain models, Donders — top priority!",
    "Marloes J. A. G. Henckens": "stress-fear memory circuits / CRF, Donders",
    "Martin Vinck": "neural population coding / gamma oscillations, Singer-Lab alumni / Donders",
    "Micha Heilbron": "predictive coding / linguistics EEG, Donders",
    "Michael X Cohen": "EEG oscillation analysis / time-frequency methods, Donders",
    "Pablo Lanillos": "active inference / neurorobotics / body perception, Donders — top priority!",
    "Peter Desain": "music BCI / neural decoding, Donders",
    "Peter Hagoort": "language neuroscience / semantic memory / MRI, Donders/MPI",
    "Pim Haselager": "BCI ethics / embedded cognition / neuroethics, Donders",
    "Robert J. van Beers": "sensorimotor integration / Bayesian estimation, Radboud",
    "Robert Oostenveld": "FieldTrip EEG/MEG toolbox / analysis methods, Donders",
    "Roemer van der Meij": "rhythmic dynamics / wavelet / TF analysis, Donders",
    "Rolf Kötter": "computational connectomics / graph theory neuroscience, Radboud",
    "Roshan Cools": "dopamine / cognitive control / decision making, Donders",
    "Sabine Hunnius": "developmental sensorimotor / infant action learning, Donders",
    "Sander M. Daselaar": "episodic memory / fMRI, Donders",
    "Saskia Haegens": "alpha oscillations / somatosensory attention, Donders",
    "Stan Gielen": "motor control / sensorimotor computation, Radboud",
    "Maarten Peeters": "in vivo electrophysiology (very junior, Radboud)",
    "Peter Indefrey": "language BCI / language neuroscience, Radboud",
    "Pim Haselager": "BCI ethics and applications, Donders",
    # Rotterdam
    "Michaéla C. Schippers": "resilience neuroscience / fMRI, Erasmus University",
    # Utrecht
    "Dennis J.L.G. Schutter": "TMS / brain stimulation / psychophysiology, Utrecht",
    "Egon L. van den Broek": "affective multimodal biosignals / physiological computing, Utrecht",
    "Elly M. Hol": "astrocyte biology / glial-neural interactions, Utrecht",
    "Louk J. M. J. Vanderschuren": "reward circuits / in vivo electrophysiology, Utrecht",
    "Lukas P.A. Arts": "spike-based computing / LC modeling (junior, Utrecht)",
}

# ─── Apply ────────────────────────────────────────────────────────────────────
discard_ids = set()
keep_ids = set()
curation_out = {}
discarded_out = []

for lab in labs:
    name = lab["name"]
    lab_id = lab["id"]

    if name in DISCARD:
        discarded_out.append({**lab, "discard_reason": DISCARD[name]})
        discard_ids.add(lab_id)
    elif name in KEEP:
        curation_out[lab_id] = {
            "status": "keep",
            "name": name,
            "lab": lab["lab"],
            "notes": KEEP[name],
        }
        keep_ids.add(lab_id)

(DATA_DIR / "labs_curation.json").write_text(json.dumps(curation_out, indent=2, ensure_ascii=False))
(DATA_DIR / "labs_discarded.json").write_text(json.dumps(discarded_out, indent=2, ensure_ascii=False))

# Filtered labs.json — remove discarded entries
remaining = [l for l in labs if l["id"] not in discard_ids]
labs_data["labs"] = remaining
labs_data["count"] = len(remaining)
(DATA_DIR / "labs.json").write_text(json.dumps(labs_data, indent=2, ensure_ascii=False))

print(f"Total input:       {len(labs)}")
print(f"Kept (annotated):  {len(keep_ids)}")
print(f"Discarded:         {len(discard_ids)}")
remaining_total = len(remaining)
undecided = [l for l in remaining if l["id"] not in keep_ids]
print(f"Remaining in JSON: {remaining_total} (kept + undecided)")
print(f"Undecided:         {len(undecided)}")
if undecided:
    print("\nUndecided entries:")
    for l in undecided:
        print(f"  {l.get('name','?')[:40]} | {l.get('lab','?')[:40]} | {l.get('topic','?')[:35]}")
