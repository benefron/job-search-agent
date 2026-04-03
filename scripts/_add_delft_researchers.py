#!/usr/bin/env python3
"""One-shot script to add newly discovered TU Delft neuro researchers to labs.json."""
import hashlib, urllib.parse, json, pathlib

ROOT = pathlib.Path(__file__).parent.parent
LABS_FILE = ROOT / "data" / "labs.json"


def make_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()[:16]


def google_url(name: str) -> str:
    q = urllib.parse.quote(f"{name} Delft University of Technology neuroscience research")
    return f"https://www.google.com/search?q={q}"


def scholar_url(name: str) -> str:
    q = urllib.parse.quote(f"{name} Delft University of Technology")
    return f"https://scholar.google.com/scholar?q={q}"


NEW_RESEARCHERS = [
    {
        "name": "Christos Strydis",
        "lab": "Neurocomputing Lab / Quantum & Computer Engineering, TU Delft",
        "topic": "brain simulation, computational neuroscience, implantable neural devices, functional ultrasound imaging",
        "url": "https://www.tudelft.nl/en/staff/c.strydis/",
        "notes": "Joint TU Delft (EEMCS Q&CE) / Erasmus MC appointment; heads Neurocomputing Lab (NCL); projects: BrainFrame (HPC brain sim), CUBE (fUS brain imaging), SiMS (implantable neural devices), Brain Dynamics (cerebellum)",
    },
    {
        "name": "Dante Gabriel Muratore",
        "lab": "Bioelectronics Section, TU Delft Microelectronics",
        "topic": "CMOS circuits for neurophysiology, mixed-signal implantable ICs, neural signal processing",
        "url": "https://www.tudelft.nl/en/staff/d.g.muratore/",
        "notes": "Designs analog/mixed-signal CMOS for biomedical and neural recording systems; circuit-algorithm co-design approach",
    },
    {
        "name": "Vasiliki Giagka",
        "lab": "Bioelectronics Section, TU Delft Microelectronics",
        "topic": "active neural interfaces, brain-machine interfaces, flexible neuroelectronics, implantable BCIs",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=372",
        "notes": "Develops flexible implantable devices for neural recording/stimulation; active BMIs targeting brain-spinal cord repair and restoration",
    },
    {
        "name": "Tiago Costa",
        "lab": "MITUS Lab / Bioelectronics Section, TU Delft Microelectronics",
        "topic": "focused ultrasound neuromodulation, analog ICs for neural stimulation, brain stimulation",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=628",
        "notes": "Heads MITUS lab (MIcroengineering Therapeutic UltraSound); IC front-ends for focused ultrasound neuromodulation and neuroelectronics",
    },
    {
        "name": "Wouter Serdijn",
        "lab": "Bioelectronics Section (Chair), TU Delft Microelectronics",
        "topic": "neuroprosthetics, BCI, electroceuticals, bioelectronic medicine, cochlear implants",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=4",
        "notes": "Section chair; bioinspired/energy-efficient analog circuits for neuroprosthetics, electroceuticals, and BCIs; cochlear implant signal processing",
    },
    {
        "name": "Johan Frijns",
        "lab": "Bioelectronics Section (Medical Delta Prof), TU Delft / LUMC",
        "topic": "electrical stimulation of the nervous system, cochlear implants, auditory neuroprosthetics",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=1084",
        "notes": "Medical Delta professor; primary appointment at LUMC; expert in cochlear implant modelling and electrical stimulation of auditory neurons",
    },
    {
        "name": "Yao-Hong Liu",
        "lab": "Bioelectronics Section (Guest) / imec-NL, TU Delft",
        "topic": "implantable BCIs, neuromorphic electronics, low-power RF and analog neural interface design",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=940",
        "notes": "Guest professor at TU Delft Bioelectronics; primary at imec-NL; miniaturised wireless BCIs and neuromorphic chips",
    },
    {
        "name": "Achilleas Savva",
        "lab": "The Reboot Lab / Bioelectronics Section, TU Delft Microelectronics",
        "topic": "organic bioelectronics, photostimulation of neurons, MEA neural recordings, 3D stem-cell neuromodels",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=915",
        "notes": "Heads The Reboot Lab; organic semiconductor devices for optogenetics-free photostimulation of neurons; electrophysiology from 3D human iPSC-derived neural models",
    },
    {
        "name": "Leon Abelmann",
        "lab": "Bioelectronics Section, TU Delft Microelectronics",
        "topic": "MEMS, magnetism, magnetic neurostimulation",
        "url": "https://bioelectronics.tudelft.nl/People/bio.php?id=874",
        "notes": "Associate professor; MEMS and magnetic device fabrication; MSc projects on magnetic neurostimulation coil arrays",
    },
    {
        "name": "Borbála Hunyadi",
        "lab": "Signal Processing Systems, TU Delft EEMCS",
        "topic": "functional ultrasound brain imaging, epilepsy EEG/SEEG analysis, neural tensor signal processing",
        "url": "https://research.tudelft.nl/en/persons/b-hunyadi",
        "notes": "NWO Vidi laureate 2024; mobile fUS brain imaging (Science Advances 2025); epilepsy brain connectivity from SEEG; tensor decomposition methods for neural data",
    },
    {
        "name": "Pieter Kruizinga",
        "lab": "Signal Processing Systems / Microelectronics, TU Delft",
        "topic": "functional ultrasound brain imaging, ultrasound signal processing, neurovascular imaging",
        "url": "https://www.tudelft.nl/en/staff/p.kruizinga/",
        "notes": "Dr.ir. in Signal Processing Systems (Microelectronics); mobile human brain imaging via fUS (Science Advances 2025); neurovascular and Williams-syndrome brain imaging",
    },
    {
        "name": "Heba Abunahla",
        "lab": "Computer Engineering / Quantum & Computer Engineering, TU Delft",
        "topic": "memristor-based neuromorphic computing, spiking neural networks, brain-inspired AI hardware",
        "url": "https://www.tudelft.nl/en/staff/h.n.abunahla/",
        "notes": "Delft Technology Fellowship; Review Editor Frontiers in Neuroscience (Neuromorphic Engineering); PhD student building memristor-based cerebellum emulation with Erasmus MC Neuroscience; RRAM-based SNNs",
    },
    {
        "name": "Frans van der Helm",
        "lab": "Biomechatronics & Human-Machine Control, TU Delft Mechanical Engineering",
        "topic": "neuromechanics, computational motor control, musculoskeletal modelling",
        "url": "https://www.tudelft.nl/en/staff/f.c.t.vanderhelm/",
        "notes": "Full professor; teaches Neuromechanics and Motor Control (MSc course); computational models of neuromuscular system dynamics and human movement",
    },
    {
        "name": "Winfred Mugge",
        "lab": "NeuroMuscular Control Lab (NMClab), TU Delft Mechanical Engineering",
        "topic": "neuromuscular control, movement disorders diagnostics, motor system identification, neurorehabilitation",
        "url": "https://www.tudelft.nl/en/staff/w.mugge/",
        "notes": "Co-heads NMClab (with Alfred Schouten); MRI-compatible haptic robotic device for probing pathological brain networks in movement disorders; NWO-TTW NeuroCIMT programme",
    },
]


def main():
    with open(LABS_FILE) as f:
        data = json.load(f)

    existing_names = {e["name"].lower() for e in data["labs"]}

    added = 0
    for r in NEW_RESEARCHERS:
        if r["name"].lower() in existing_names:
            print(f"SKIP (duplicate): {r['name']}")
            continue
        entry = {
            "id": make_id(r["name"]),
            "name": r["name"],
            "lab": r["lab"],
            "location": "Delft",
            "topic": r["topic"],
            "url": r["url"],
            "orcid_url": "",
            "google_url": google_url(r["name"]),
            "scholar_url": scholar_url(r["name"]),
            "works_count": 0,
            "source": "manual",
            "notes": r["notes"],
        }
        data["labs"].append(entry)
        existing_names.add(r["name"].lower())
        added += 1
        print(f"Added: {r['name']}")

    data["count"] = len(data["labs"])

    with open(LABS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Added {added} entries. Total: {data['count']}")


if __name__ == "__main__":
    main()
