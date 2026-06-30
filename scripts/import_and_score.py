"""
One-shot script: re-import jobs.json into the SQLite DB and apply scores
that were evaluated against the candidate's profile (bypassing the LLM API).

Run from repo root:
    python scripts/import_and_score.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import db

# ---------------------------------------------------------------------------
# the candidate's manually evaluated scores
# Format: id -> (score, fit_category, key_matches, key_gaps, rationale)
# ---------------------------------------------------------------------------
SCORES = {
    # ── TNO energy / environment ── (no description, unrelated domain)
    "90ccc189c858888f": (12, "poor", [], ["unrelated domain", "no description"], "Energy infrastructure is unrelated to neuromorphic/neuro/AI the candidate's target domains."),
    "bc47c846086e74c8": (12, "poor", [], ["unrelated domain", "no description"], "Sustainable materials R&D at TNO is outside the candidate's domain expertise."),
    "97aadb506e5756e1": (12, "poor", [], ["unrelated domain", "no description"], "Carbon-neutral industry focus does not overlap with the candidate's profile."),
    "b06242ee8f12a6da": (10, "poor", [], ["unrelated domain", "no description"], "Circular feedstock chemistry is unrelated to neurotech/AI."),
    "667984e267ceadba": (10, "poor", [], ["unrelated domain", "no description"], "Generic 'Industry' TNO page — domain unclear but likely unrelated."),
    "844d110cd3cd371f": (10, "poor", [], ["unrelated domain", "no description"], "Energy systems transition is outside the candidate's expertise."),
    "881e8288fb50ff77": (10, "poor", [], ["unrelated domain", "no description"], "Offshore wind farms domain is not relevant to the candidate."),
    "8bcaa9f33b5737f0": (10, "poor", [], ["unrelated domain", "no description"], "Solar device technology is outside the candidate's domain."),
    "552c798812349dcb": (10, "poor", [], ["unrelated domain", "no description"], "Sustainable solar panels — unrelated to neuro/AI."),
    "6f29de79315c043c": (10, "poor", [], ["unrelated domain", "no description"], "Solar applications — not relevant to the candidate's profile."),
    "ce3a17ef46d29efb": (10, "poor", [], ["unrelated domain", "no description"], "Energy supply domain is not a fit."),
    "581d50febdb07333": (8, "poor", [], ["unrelated domain", "no description"], "Greenhouse horticulture — completely unrelated."),
    "cc79b2fe3eecfc0c": (15, "poor", ["monitoring", "measurement systems"], ["unrelated domain", "no description"], "Monitoring/measurement role — minor signal but still mismatched domain."),
    "acefc04c4cb75dbd": (8, "poor", [], ["unrelated domain", "no description"], "Heating/cooling systems — not relevant."),
    "0931f3c1f50e8b3f": (10, "poor", [], ["unrelated domain", "no description"], "Energy storage — not relevant to the candidate's profile."),
    "a1fdc7ec24c1dc37": (8, "poor", [], ["unrelated domain", "no description"], "Built environment sustainability — not a match."),
    "e48d1ce58348f88a": (8, "poor", [], ["unrelated domain", "no description"], "Energy in the built environment — not a match."),
    "f8398d387cdfc7d8": (20, "poor", ["remote sensing", "signal processing adjacent"], ["unrelated domain", "environmental science"], "Sentinel-5 is a satellite sensor program — faint signal processing overlap but wrong domain."),
    "e59ec24ce06229c7": (12, "poor", [], ["unrelated domain", "no description"], "Clean Air atmospheric research — not relevant."),
    "51a1792ae99d8903": (18, "poor", ["satellite sensor systems"], ["remote sensing", "not neuroscience"], "EarthCARE is a satellite radar instrument — sensor engineering overlap is minor and tangential."),
    "aed04a47064b9f0b": (18, "poor", ["satellite sensor systems"], ["remote sensing", "not neuroscience"], "TANGO satellite — same reasoning as EarthCARE."),
    "e1de9f07d83f586f": (18, "poor", ["remote sensing"], ["environmental focus", "not neuroscience/AI"], "Earth observation — sensor systems tangential overlap, wrong domain."),
    "ea7e63fe9948919c": (8, "poor", [], ["unrelated domain", "no description"], "Asset lifecycle / information management — unrelated."),
    "b9a628856dc59a76": (8, "poor", [], ["unrelated domain", "no description"], "Safety of buildings — not relevant."),
    "2bef16421172eff2": (8, "poor", [], ["unrelated domain", "no description"], "Safe efficient care building — healthcare construction, not neuroscience."),
    "da51a4be0c86aa32": (8, "poor", [], ["unrelated domain", "no description"], "Industrial construction — unrelated."),
    "d9bc108885ac7bd1": (8, "poor", [], ["unrelated domain", "no description"], "Building materials — not relevant."),
    "3c5cb865f62cb52d": (8, "poor", [], ["unrelated domain", "no description"], "Bio-based building materials — biology in wrong context."),
    "c4754085eb1b3f35": (8, "poor", [], ["unrelated domain", "no description"], "Circular construction — not relevant."),
    "f4dd60eddbf6fea7": (0, "poor", [], ["Dutch-language posting", "unrelated domain"], "Dutch-language posting at TNO — hard exclusion."),

    # ── Industry / Tech ──
    "e3b3dc73fc3a235b": (88, "strong", ["imec", "systems & algorithms", "AI architecture", "Eindhoven", "research institute"], ["seniority may be higher than postdoc"], "Senior AI Architect (Systems & Algorithms) at imec NL in Eindhoven — directly in the candidate's current employer domain with perfect skill overlap in AI systems and algorithm design."),
    "76390b7e96021a43": (68, "moderate", ["audio signal processing", "standardisation", "Philips Eindhoven", "DSP", "algorithm development"], ["audio domain not neuroscience"], "Audio signal processing and standardisation R&D at Philips Eindhoven — strong DSP/algorithm overlap even if domain is audio rather than neural."),
    "ec11ce808e42be66": (72, "strong", ["sensing architecture", "hardware+algorithm", "Eindhoven", "sensor systems", "TMC"], ["consulting/contracting nature"], "Sensing Architect (hardware & algorithm) at TMC Eindhoven — excellent match: sensor system design + algorithm development, core of the candidate's imec work."),
    "8a7a0bd7402ea9aa": (52, "moderate", ["calibration algorithms", "signal processing", "Eindhoven", "TMC"], ["calibration not core interest"], "Calibration Algorithm Engineer at TMC Eindhoven — solid algorithm + sensing fit, good location; calibration specialisation is a partial overlap."),
    "6f1d7ccb2809513b": (52, "moderate", ["embedded software", "Delft", "engineering"], ["embedded-only, no neuro/AI angle"], "Embedded Software Engineer in Delft — core embedded skills apply; no description so domain unknown, likely industrial embedded without neuro angle."),
    "adaa27d4fe209dec": (62, "moderate", ["hardware full-stack", "sensor systems", "Next Generation Sensors"], ["Maastricht location", "no description available"], "Hardware Full Stack Developer at Next Generation Sensors — company name and hardware+sensing alignment are promising; Maastricht is secondary location."),
    "8b28fd4ffd65d745": (52, "moderate", ["Innatera neuromorphic chip company", "Netherlands"], ["program manager role not technical", "non-research position"], "Staff Program Manager at Innatera — Innatera is a neuromorphic chip startup directly in the candidate's domain; PM role is a career shift but the company fit is exceptional."),
    "ac8fe9348d530cff": (52, "moderate", ["Innatera neuromorphic chip company", "Netherlands"], ["program manager role not technical", "non-research position"], "Staff Program Manager at Innatera Nanosystems — same as above, Indeed version."),
    "990f3557dcb1cc2c": (48, "stretch", ["analog electronics", "hardware", "sensor systems adjacent"], ["analog IC focus", "Geldrop", "no neuroscience"], "Senior Analog Electronic Engineer at Manus Machinae — Manus makes haptic/motion-capture gloves; analog hardware for human-machine interfaces is tangentially relevant."),
    "ace112a7b70898c4": (48, "stretch", ["embedded software", "hardware company", "human-machine interface"], ["not neuroscience-focused", "Geldrop"], "Medior Embedded Software Engineer at Manus Machinae — same Manus haptic gloves context; embedded SW at a neuro-adjacent hardware company."),
    "2df7aff6dec4933b": (62, "moderate", ["robot world models", "AI", "UvA", "Toyota research", "computational modelling"], ["robotics not neuro", "postdoc level"], "Postdoc on Robot World Models (UvA+TOYOTA) — robotics+AI world modelling at UvA with Toyota; strong AI/computational modelling overlap, good alignment for broadened scope."),
    "55d98a508f7fb3e8": (32, "stretch", ["AI engineer", "Belgium"], ["generic AI role", "no neuro/sensing angle"], "AI Engineer at Kingfisher Recruitment (Belgium) — generic AI, no neuro/sensing angle; Belgium location acceptable but stretch."),
    "414b697b02104db2": (28, "poor", ["hardware systems", "RF/digital", "Eindhoven"], ["project management not research", "airborne systems not neuro"], "Technical Project Manager RF/Digital/Hardware at KRUSH Labs — hardware PM role, not research; airborne systems domain mismatch."),
    "7ad3a0c0a1768c0d": (30, "stretch", ["TNO scientist", "research institute", "Netherlands"], ["cyber security not core domain"], "Medior Scientist Cyber Security at TNO (Groningen) — TNO research scientist role; cyber security domain is a stretch but systems/algorithm skills transfer partially."),
    "5ac535835b89d750": (30, "stretch", ["TNO scientist", "research institute", "The Hague"], ["cyber security not core domain"], "Medior Scientist Cyber Security at TNO (The Hague) — same as Groningen role; The Hague is in target location list."),
    "34fc3d11e25e3c6e": (28, "poor", ["founding engineer", "startup"], ["no description", "no location", "unknown domain"], "Senior Founding Engineer at Syntera — early-stage startup with no description or location; could be interesting but insufficient information."),
    "3de798b83de8ddd1": (28, "poor", ["data science", "control systems", "Amsterdam"], ["agriculture domain", "no neuro angle"], "Data Scientist Control Systems at Source.ag — control systems knowledge transfers but agriculture domain and no neuro/AI fit."),
    "41bbcb18fdc6d7b8": (22, "poor", [], ["no description", "no location", "generic data science"], "Data Scientist at Maince — no location or description; generic data science likely not relevant."),
    "53089a4299ce0008": (15, "poor", [], ["retail domain", "no neuro/sensing"], "AI Engineer at Wehkamp Retail — retail recommender systems, not relevant to the candidate's expertise."),
    "ad06f5c4108c45f7": (10, "poor", [], ["Azure/.NET stack", "consulting", "no research"], "AI Developer .NET/Azure AI Foundry at Devoteam — vendor-specific cloud/dev stack, not research, not relevant."),
    "3e05fff7746c7538": (15, "poor", [], ["automation/workflow AI", "no research", "no neuro"], "AI Automation Engineer at AFS Group — business process automation AI, not relevant."),
    "59e37d933075e0f5": (15, "poor", [], ["product AI", "startup", "no neuro/sensing"], "AI Engineer (Product-focused) at Zeno — product startup AI, no domain overlap."),
    "0259384ef4de43b5": (22, "poor", [], ["no description", "contractor", "defence/oil adjacent"], "AI Engineer at Airswift — staffing agency, likely oil/gas/defence sector, no description."),
    "00565482545d1a32": (18, "poor", [], ["non-profit", "Eindhoven", "no description"], "AI Engineer at Code for Good — non-profit AI, potentially interesting but no description to evaluate domain."),
    "1e4e1cb13b539376": (12, "poor", [], ["crypto/financial ML", "evaluation role"], "Senior Evaluation ML Engineer at kaiko.ai — cryptocurrency ML evaluation, unrelated domain."),
    "9316d2a782f2cf1b": (20, "poor", [], ["generic IT consulting", "Rijswijk"], "AI Engineer/Data Scientist at EPAM — consulting house, generic AI/DS work, no research."),
    "fdf4b908f0353376": (12, "poor", [], ["traffic ML", "ride-hailing", "not research"], "Staff Software Engineer Traffic ML at Uber — traffic ML at a ride-hailing company, not research, unrelated domain."),
    "9b71390e5cf77a5a": (18, "poor", [], ["generic data science", "Eindhoven"], "Senior Data Scientist at Magno IT Recruitment — generic DS role through recruiter, no specialisation."),
    "df8065a51a376854": (12, "poor", [], ["data engineering", "no research"], "ML/AI Data Engineer at GeekSoft — data pipeline engineering, not research-focused."),
    "aa90db4748aef081": (15, "poor", [], ["energy forecasting", "wrong domain"], "Senior Data Scientist Energy Forecasting at Groendus — energy sector DS, unrelated to neuro/AI research."),
    "f281448a5735192c": (15, "poor", [], ["ML data engineering", "consulting"], "Senior ML & Data Engineer at Ubique — data engineering focus, consulting firm."),
    "32ef7591fc779bfd": (0, "poor", [], ["Dutch fluency required", "consulting"], "AI/ML Engineer with Dutch at Us3 Consulting — 'With Dutch' in title signals Dutch language requirement; hard exclusion."),
    "587970ba9ffe0b27": (18, "poor", [], ["generic ML engineering"], "Sr. Machine Learning Engineer at Merqato — generic ML engineering, no domain info."),
    "48aa4cb58b0357c6": (22, "poor", ["life sciences adjacent"], ["no neuro focus", "Breda"], "ML Engineer at SIRE Life Sciences — life sciences is faintly adjacent to neuroscience but role is generic ML."),
    "40b92723adc534fe": (8, "poor", [], ["credit risk finance", "unrelated domain"], "Senior Data Scientist Credit Risk at BridgeFund — financial risk modelling, completely unrelated."),
    "c36c06785fa767ee": (12, "poor", [], ["MLOps/GenAI", "cloud engineering", "relocation"], "ML Engineer Cloud/MLOps/GenAI at Wypoon — cloud MLOps focus, not research, relocation offer suggests remote hire."),
    "f127d5bb50bef642": (10, "poor", [], ["travel tech", "unrelated domain"], "ML Engineer at FareHarbor — travel/ticketing software, unrelated to the candidate's domain."),
    "4cb5aea3073781cf": (18, "poor", [], ["InSAR/satellite", "civil engineering"], "Lead InSAR Engineer at SkyGeo — satellite radar for infrastructure monitoring, unrelated."),
    "d5d757eabf685030": (15, "poor", [], ["atmospheric science", "TNO", "wrong domain"], "Experienced Scientist Source Apportionment at TNO — atmospheric pollution science, TNO but wrong domain."),

    # ── Academic / Postdoc ──
    "744df1660f7f08b3": (42, "stretch", ["multimodal AI", "research role", "Amsterdam"], ["Singapore location", "LLM focus not neuro", "no description"], "Applied Scientist/Research Engineer Multimodal at Mistral AI — strong AI research role but posted for Singapore, not Netherlands."),
    "38c41665548f5f64": (45, "stretch", ["neuroscience", "postdoc", "VU Amsterdam"], ["neuron-glia molecular focus", "not computational/systems"], "Postdoc Neuron-glia interactions in memory at VU Amsterdam — neuroscience postdoc but molecular/cellular focus, not systems or computational."),
    "3271e7f372891fd3": (45, "stretch", ["neuroscience", "postdoc", "VU Amsterdam"], ["neuron-glia molecular focus", "not computational/systems"], "Same neuron-glia postdoc at VU Amsterdam — LinkedIn version."),
    "deca3cf76fa59ef1": (45, "stretch", ["neuroscience", "postdoc", "Amsterdam"], ["molecular focus", "not computational/systems"], "Neuron-glia postdoc at Athena — same position, different listing."),
    "ea81cf79977dd66a": (10, "poor", [], ["ethics/philosophy focus", "not technical"], "Postdoc Ethics of Technology at TU/e — humanities research, no technical overlap."),
    "2a38722da79abcfd": (38, "stretch", ["neuroscience", "postdoc", "Leiden", "neuroimaging"], ["language processing not systems neuro", "clinical MRI focus"], "Postdoc Neuroimaging of Language at Leiden — neuroscience but language+MRI domain, not computational systems neuro."),
    "1a574cac48c00bb1": (38, "stretch", ["neuroscience", "neuroimaging", "Leiden postdoc"], ["language domain", "MRI not electrophysiology"], "Postdoc Neuroimaging of Language at Leiden (Indeed) — same role, Indeed listing."),
    "04d88178cfddc0c0": (32, "stretch", ["AI/ML", "medical imaging", "Amsterdam UMC"], ["oncology imaging not neuro", "clinical focus", "no electrophysiology"], "Postdoc AI Imaging Biomarkers in Oncology at Amsterdam UMC — ML applied to medical imaging; domain stretch (not neuroscience), but ML skills transfer."),
    "1d877a32eca79c48": (0, "poor", [], ["Dutch-language posting", "Tilburg"], "Postdoctoraal onderzoeker at Tilburg University — Dutch title indicates Dutch-language position; hard exclusion."),
    "3d250a6c13951ba2": (0, "poor", [], ["Dutch-language posting", "education research"], "Postdoc onderzoeker educatie at Erasmus MC — Dutch-language education research; hard exclusion."),
    "5f0ee6e259ad9689": (5, "poor", [], ["molecular biology", "bacteria", "not neuroscience"], "Postdoc Stress responses in bacteria at VU — molecular microbiology, completely unrelated."),
    "0a42caa05d3ab1eb": (12, "poor", [], ["plasma physics", "materials science", "not neuro/AI"], "PostDoc In-situ Diagnostics PLD4Energy at DIFFER — materials science/plasma physics, unrelated."),
    "3afc19d6d58df4bc": (20, "poor", ["KNAW", "research institute"], ["research assistant underqualified for PhD holder", "generic support role"], "Research Assistant at KNAW — The candidate is overqualified; generic research support role at a prestigious institute."),
    "de926456b1549d53": (5, "poor", [], ["media/web research", "social science"], "Postdoc Media & Web Diets Observatory at UvA — social science/media research, completely unrelated."),
    "05a7faf431bed63c": (22, "poor", ["AI ethics", "VU Amsterdam"], ["philosophy/AI alignment focus", "not technical neuroscience"], "PostDoc Hybrid Intelligence at VU — AI alignment/ethics research; some AI overlap but no neuroscience or engineering fit."),
    "36dcb9a361cd6a1d": (22, "poor", ["AI ethics", "Amsterdam"], ["same hybrid intelligence role", "philosophy focus"], "PostDoc Hybrid Intelligence at Athena — same role as VU listing."),
    "c420d2fb2d3953fe": (42, "stretch", ["Donders Centre", "cognitive neuroscience", "Radboud", "Nijmegen"], ["research assistant level", "overqualified", "no description"], "Research Assistant at Donders Centre for Cognition Radboud — prestigious neuroscience institute; RA level is below the candidate's qualification, but domain overlap is good."),
    "e4db6c6c5a8e5f95": (18, "poor", ["Donders Centre", "neuroscience"], ["summer school not a job", "temporary"], "Research Assistant at Radboud Summer School — this appears to be a summer school context, not a full research position."),
    "420749b062d603b0": (42, "stretch", ["Donders Centre", "cognitive neuroscience", "Radboud", "Nijmegen"], ["research assistant level", "overqualified"], "Research Assistant at Donders Centre (Indeed) — same role as LinkedIn listing."),
    "3acf72c9115c61d7": (42, "stretch", ["Donders Centre", "cognitive neuroscience", "Radboud", "Nijmegen"], ["research assistant level", "overqualified"], "Research Assistant at Donders Centre (Indeed, duplicate) — same position."),
    "72bbe453cf1d3b6b": (20, "poor", [], ["program management", "AI transformation", "not research"], "Senior AI Program Manager at Akkodis — program management/consultancy, not a research or engineering position."),
    "fcbb4f3a0adf6eb3": (12, "poor", [], ["director-level", "logistics/retail", "not research"], "Director of AI enablement at Bleckmann — C-suite level, logistics/retail focus, not relevant."),
    "b5de93837e01ec24": (12, "poor", [], ["director-level", "logistics/retail", "not research"], "Director of AI enablement at Bleckmann (Indeed) — same role."),
    "998df35721936588": (5, "poor", [], ["protein science", "food industry", "not relevant"], "Sr. Protein Scientist at Danone — food science biology, completely unrelated."),
    "5031f993175e599c": (5, "poor", [], ["Saudi Arabia", "environmental science", "not relevant"], "Lifecycle Analysis Scientist at Aramco — Saudi Arabia, oil/environmental science."),
    "e47594628b9bf14d": (15, "poor", [], ["no description", "generic title", "Zeeland"], "Generic 'Engineer' role at Russell Tobin — recruiter listing with no description or specialisation."),
    "a6ff9251a1c4853d": (22, "poor", ["hardware", "Eindhoven region"], ["OEM engineering", "no description", "unknown domain"], "OEM Engineer at ALGOTEQUE Innovation Hub Boxmeer — hardware/system integration role, no description, borderline location."),
    "4d1f403ae08428fc": (15, "poor", [], ["no description", "recruiter listing"], "Generic 'Engineer' at Recense recruitment — no description or domain information."),
    "04c2ba45bb52153f": (15, "poor", [], ["consulting", "no description"], "Senior Engineer at Sia consulting — generic senior engineer at a consultancy, no useful info."),
    "d8c9db553c7c99b7": (5, "poor", [], ["safety officer", "Arabic company", "Saudi Arabia"], "Safety Officer at Alturki Holding — Middle East safety role, completely unrelated."),
    "09233f800582562d": (10, "poor", [], ["mechanical engineering", "not the candidate's domain"], "Mechanical Engineer at Monumental — not relevant to the candidate's profile."),
    "48b2e121c0e19dcc": (5, "poor", [], ["QA testing", "software", "not research"], "QA/Test Engineer at Blinqx — software testing role, not research or engineering the candidate's domain."),
    "9f4b0bb5adce6bef": (12, "poor", [], ["product design", "offshore/GIS", "not neuro"], "Product Design Engineer at Fugro — offshore/geotechnical engineering, not relevant."),
    "41b9fb549476e480": (10, "poor", [], ["product design", "water tech", "not neuro"], "Product Design Engineer at Aquablu — water purification product design, not relevant."),
    "c21d4ab631a003eb": (5, "poor", [], ["technical writer", "not research"], "Technical Writer at Nebius — documentation role, not a fit for the candidate as researcher/engineer."),
    "e4db6c6c5a8e5f95": (18, "poor", ["Donders Centre"], ["summer school", "temporary role"], "Research Assistant Donders Summer School — temporary/summer position, not a real research job."),
}

# ---------------------------------------------------------------------------
# Import jobs.json → DB, then apply scores
# ---------------------------------------------------------------------------
def main() -> None:
    db.init_db()

    with open("data/jobs.json") as f:
        data = json.load(f)
    jobs = data.get("jobs", [])
    print(f"Loaded {len(jobs)} jobs from jobs.json")

    imported = 0
    for job in jobs:
        url = job.get("url", "")
        if not url:
            continue
        if db.is_seen(url):
            continue
        db.insert_job(
            source=job.get("source", "unknown"),
            url=url,
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location", ""),
            description=job.get("description", "") or "",
            date_posted=job.get("date_posted"),
        )
        imported += 1
    print(f"Imported {imported} jobs into DB")

    scored = 0
    skipped = 0
    for job in jobs:
        job_id = job.get("id")
        if not job_id or job_id not in SCORES:
            skipped += 1
            continue
        score, fit_cat, matches, gaps, rationale = SCORES[job_id]
        db.update_score(
            job_id=job_id,
            score=score,
            fit_category=fit_cat,
            key_matches=matches,
            key_gaps=gaps,
            rationale=rationale,
        )
        scored += 1

    print(f"Scored {scored} jobs, skipped {skipped} (not in scoring table)")

    stats = db.get_stats()
    print(f"\nDB stats: total={stats['total']}, scored={stats['scored']}")


if __name__ == "__main__":
    main()
