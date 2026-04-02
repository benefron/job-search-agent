"""
Ben Efron's profile — used as the reference for job scoring.
Edit this file to reflect new skills, milestones, or updated preferences.
"""

PROFILE = {
    "name": "Ben Efron, PhD",
    "title": "Systems Neuroscientist | Neuromorphic Computing | Bio-Inspired Sensory Encoding | Hardware-Software Integration",
    "experience_years": 7,
    "current_role": "Postdoctoral Researcher, University of Liège / imec (2024–present)",
    "phd": "Systems Neuroscience, Weizmann Institute of Science (2017–2024)",
    "publication": "Efron et al., Current Biology (2025) — Neural encoding and behavioral detection of whisker-generated sounds in mice",

    # Core technical skills
    "skills": [
        # Neuroscience / domain
        "systems neuroscience",
        "computational neuroscience",
        "neural computation",
        "sensory encoding",
        "mechanoreceptor modelling (SA/RA)",
        "spiking neural networks (SNN)",
        "bio-inspired algorithms",
        "electrophysiology (in vivo, in vitro HD-MEA)",
        "closed-loop control",
        "neural decoding",
        "spike sorting (Kilosort, SpikeInterface)",
        "population dynamics",
        "Bayesian estimation",
        # ML / software
        "Python",
        "PyTorch",
        "MATLAB",
        "NumPy",
        "SciPy",
        "PyQt5",
        "DeepLabCut",
        "Facemap",
        "OpenCV",
        "spiking neural models (Izhikevich, AdEx, MQIF)",
        "random forest",
        "GLMs",
        "AI agent development",
        # Hardware / embedded
        "Arduino",
        "Raspberry Pi",
        "NI DAQ",
        "Open Ephys",
        "Bonsai RX",
        "PCB design (JLCPCB)",
        "CAD (Autodesk Inventor)",
        "3D printing",
        "DSP",
        "sub-millisecond sensor synchronisation",
        "imec HD-MEA",
        "Neuropixels",
        "custom PCB",
        "real-time signal processing",
        "high-speed video (400 fps)",
    ],

    # Key achievements for scoring context
    "achievements": [
        "16× compression of 6,400-channel tactile sensor array to 400 spiking channels (SA/RA model, PyTorch)",
        "Real-time HD-MEA pipeline: hundreds of channels >10 kHz, sub-millisecond closed-loop feedback (imec)",
        "Built multimodal acquisition platform from scratch: Arduino master, custom PCB, NI DAQ, cameras, encoders, touch sensors",
        "200+ recorded neural units, tens of surgical sessions, published in Current Biology",
        "PyQt5 experiment management GUI (1,000+ lines)",
        "Presented bio-inspired spiking estimation and filters at BENELUX Systems and Control Conference (March 2026)",
        "Capo Caccia Neuromorphic Engineering Workshop attendee",
        "WBI Postdoctoral Excellence Scholarship",
    ],

    # Domains of genuine interest (used for scoring fit_category)
    "domains_primary": [
        "neuromorphic computing",
        "spiking neural processors",
        "neuroengineering",
        "experimental neuroscience",
        "brain-inspired computing",
        "edge AI",
        "embedded AI",
        "event-driven sensing",
        "bio-inspired algorithms",
        "neuroAI",
        "sensory processing",
    ],
    "domains_secondary": [
        "signal processing",
        "embedded systems",
        "wearable sensing",
        "computational modelling",
        "systems neuroscience",
        "in vivo electrophysiology",
        "applied neuroscience",
        "closed-loop neural interfaces",
        "BCI",
        "semiconductor R&D",
        "research scientist",
        "applied scientist",
    ],

    # Role types
    "role_types": [
        "R&D scientist",
        "applied scientist",
        "research engineer",
        "neuromorphic engineer",
        "ML engineer",
        "signal processing engineer",
        "neuroengineering",
        "postdoctoral researcher",
        "postdoctoral researcher neuroscience",
        "consultant",
    ],

    # Location preferences
    "location_primary": ["Netherlands", "Amsterdam", "Eindhoven", "Delft", "Utrecht", "Rotterdam", "Nijmegen"],
    "location_secondary": ["Leuven", "Zaventem", "Brussels", "Belgium"],
    "open_to_remote": True,

    # Hard negatives — deprioritise these in scoring
    "not_interested": [
        "animal surgery",
        "animal handling",
        "preclinical rodent",
        "sales",
        "account management",
        "chip design",
        "IC design",
        "VLSI",
        "digital design RTL",
        "VHDL Verilog",
        "PhD position",
        "doctoral candidate",
        "internship",
        "working student",
        "Dutch fluency required",
    ],
}

# Milestone log — append new entries as career progresses
# Each entry is added to the scoring prompt so the model knows the latest state
MILESTONES = [
    "2025: Published first-author paper in Current Biology on neural encoding of whisker-generated sounds",
    "2025: COSYNE 2025 — co-author on accepted abstract on calcium-based plasticity",
    "2026-03: Presented 'Bio-inspired estimation and filters with spiking neurons' at BENELUX Systems and Control Conference",
    "2026: Targeting FPGA and dedicated neural accelerators for real-time deployment of SA/RA encoding framework",
    "2026: Active imec collaboration on real-time HD-MEA streaming pipeline (hundreds of channels, >10 kHz)",
]


def get_profile_text() -> str:
    """Return a concise text representation of the profile for use in LLM prompts."""
    skills_str = ", ".join(PROFILE["skills"][:30])  # top 30 to keep prompt focused
    domains_str = ", ".join(PROFILE["domains_primary"] + PROFILE["domains_secondary"])
    locations_str = ", ".join(PROFILE["location_primary"] + PROFILE["location_secondary"])
    achievements_str = "\n".join(f"  - {a}" for a in PROFILE["achievements"])
    milestones_str = "\n".join(f"  - {m}" for m in MILESTONES)
    not_interested_str = ", ".join(PROFILE["not_interested"])

    return f"""
CANDIDATE PROFILE: {PROFILE["name"]}
Title: {PROFILE["title"]}
Experience: {PROFILE["experience_years"]}+ years in systems neuroscience and neuroengineering
Current role: {PROFILE["current_role"]}
PhD: {PROFILE["phd"]}
Key publication: {PROFILE["publication"]}

CORE SKILLS:
{skills_str}

KEY ACHIEVEMENTS:
{achievements_str}

RECENT MILESTONES:
{milestones_str}

DOMAINS OF INTEREST:
Primary: {", ".join(PROFILE["domains_primary"])}
Secondary: {", ".join(PROFILE["domains_secondary"])}

TARGET ROLE TYPES: {", ".join(PROFILE["role_types"])}

PREFERRED LOCATIONS (primary): {", ".join(PROFILE["location_primary"])}
PREFERRED LOCATIONS (secondary): {", ".join(PROFILE["location_secondary"])}
Open to remote: {PROFILE["open_to_remote"]}

NOT INTERESTED IN (score down strongly if job is primarily about): {not_interested_str}
""".strip()
