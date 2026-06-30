"""
Candidate profile — used as the reference for job scoring.
Edit this file to reflect your skills, milestones, and preferences.
"""

PROFILE = {
    "name": "Your Name, PhD",
    "title": "Your Professional Title | Key Domain 1 | Key Domain 2 | Key Domain 3",
    "experience_years": 7,
    "current_role": "Your Current Role, Your Institution (year–present)",
    "phd": "Your Field, Your University (year–year)",
    "publication": "Author et al., Journal (Year) — Your publication title",

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
        "MATLAB (primary for R&D and control)",
        "C++",
        "Bash",
        "NumPy",
        "SciPy",
        "PyQt5",
        "DeepLabCut",
        "Facemap",
        "OpenCV",
        "machine vision",
        "high-speed video processing (400 fps)",
        "spiking neural models (Izhikevich, AdEx, MQIF)",
        "random forest",
        "GLMs",
        "adaptive Kalman filtering",
        "adaptive state-space inference",
        "multimodal sensor fusion",
        "model compression / quantization / sparsification",
        "AI agent development",
        # Real-time / hardware / embedded
        "hardware-in-the-loop (HIL)",
        "co-simulation",
        "Simulink",
        "event-gated processing",
        "finite state machine design",
        "EMI diagnosis and mitigation",
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
        "real-time signal processing",
        "FPGA-targeted algorithm design",
    ],

    # Key achievements for scoring context
    "achievements": [
        "Example: Built X system achieving Y-fold compression using Z technology (Python, PyTorch)",
        "Example: Designed hardware-in-the-loop integration with sub-millisecond closed-loop latency",
        "Example: Built GPU-accelerated multimodal sensor simulation framework (PyTorch, pluggable SNN models)",
        "Example: Built multimodal data acquisition platform from scratch (embedded controller, custom PCB, cameras)",
        "Example: Real-time signal processing pipeline for hundreds of channels, sub-millisecond feedback",
        "Example: First-author publication in peer-reviewed journal (Year)",
        "Example: Conference presentation on bio-inspired algorithms (Year)",
        "Example: Named postdoctoral scholarship or fellowship",
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
        "machine vision",
        "multimodal sensing",
        "real-time control systems",
        "sensor simulation",
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
        "data science",
        "machine learning engineering",
        "computer vision",
        "applied ML",
        "scientific ML",
        "biomedical engineering",
        "bioengineering",
        "computational biology",
        "control theory",
        "HIL/SIL simulation",
    ],

    # Role types
    "role_types": [
        "R&D scientist",
        "applied scientist",
        "research engineer",
        "neuromorphic engineer",
        "ML engineer",
        "machine learning engineer",
        "data scientist",
        "applied machine learning",
        "computer vision scientist",
        "signal processing engineer",
        "neuroengineering",
        "imaging AI engineer",
        "real-time systems engineer",
        "postdoctoral researcher",
        "postdoctoral researcher neuroscience",
        "consultant",
    ],

    # Location preferences — Belgium/Leuven is primary; NL is secondary
    "location_primary": ["Leuven", "Brussels", "Liège", "Belgium"],
    "location_secondary": ["Antwerp", "Ghent", "Mechelen", "Zaventem", "Hasselt", "Tervuren", "Netherlands", "Amsterdam", "Eindhoven", "Delft", "Utrecht", "Rotterdam", "Breda"],
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
        "lab technician (NL only — not worth relocating for)",
        "laboratory manager (NL only — not worth relocating for)",
    ],
}

# Milestone log — append new entries as career progresses
# Each entry is added to the scoring prompt so the model knows the latest state
MILESTONES = [
    "Year: Example — published first-author paper on [topic] in [journal]",
    "Year: Example — conference presentation on [topic] at [venue]",
    "Year: Example — targeting [technology] for [application]",
    "Year: Example — ongoing collaboration on [project]",
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
