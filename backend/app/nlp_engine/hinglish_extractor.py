import re
from dataclasses import dataclass
from functools import lru_cache
from app.models.schemas import Entity

# Explainable v1 lexicon: English, Roman Hindi and ten Indian language scripts.
LEXICON = [
    ("anaphylaxis", "symptom", 95, r"anaphylaxis|anaphylactic|सांस.{0,8}दिक्कत"),
    (
        "throat swelling",
        "symptom",
        95,
        r"throat swelling|throat.{0,10}clos|गला.{0,8}सूज",
    ),
    ("hives", "symptom", 70, r"hives|urticaria|पित्ती|చర్మ దద్దుర్లు|त्वचेवर पुरळ"),
    ("itchy throat", "symptom", 65, r"itchy throat|gale? me.{0,8}khujli|गले में खुजली"),
    (
        "vomiting",
        "symptom",
        45,
        r"vomit\w*|ulti|उल्टी|বমি|வாந்தி|వాంతి|ಛರ್ಡಿ|ಓಕಳಿ|ഛർദ്ദി|ਉਲਟੀ|ଝାଡ଼ା|ઊલટી",
    ),
    (
        "diarrhea",
        "symptom",
        45,
        r"diarrh\w*|loose motions?|pet kharab|पेट खराब|जुलाब|পাতলা পায়খানা|வயிற்றுப்போக்கு|విరేచనాలు|ಜಲಭೇದಿ|വയറിളക്കം|ਦਸਤ|ଅତିସାର|ઝાડા",
    ),
    (
        "jaundice / liver injury",
        "symptom",
        90,
        r"jaundice|hepatotoxic\w*|liver injury|yellow eyes|पीलिया|ಕಾಮಾಲೆ|കാമാല|காமாலை",
    ),
    (
        "palpitations",
        "symptom",
        35,
        r"heart racing|palpitation\w*|dil tez|दिल.{0,10}धड़क",
    ),
    ("distress", "symptom", 15, r"tension me|anxious|घबराहट"),
    ("ferbam residue", "hazard", 90, r"ferbam|फरबम"),
    (
        "heavy metals",
        "hazard",
        90,
        r"arsenic|mercury|lead contamination|heavy metals?|आर्सेनिक",
    ),
    (
        "suspected undeclared allergen",
        "hazard",
        75,
        r"nut.free.{0,65}(?:badam|almond|peanut)|undeclared allergen",
    ),
    (
        "suspected drug spiking",
        "hazard",
        85,
        r"steroid spik\w*|nsaid spik\w*|spiked with steroids?",
    ),
    (
        "missing hologram",
        "counterfeit",
        65,
        r"missing.{0,12}hologram|no.{0,8}hologram|hologram.{0,8}(?:missing|nahi)|नकली सील|nakli seal",
    ),
    (
        "failed QR authentication",
        "counterfeit",
        60,
        r"qr.{0,35}(?:fail|not scan|nahi|wrong domain)|barcode.{0,20}fail",
    ),
    (
        "broken seal",
        "counterfeit",
        50,
        r"broken.{0,10}seal|seal.{0,10}(?:broken|toot|open)",
    ),
    (
        "label inconsistencies",
        "counterfeit",
        40,
        r"spelling (?:error|mistake)|label typo|bizarre font|blurry hologram",
    ),
    (
        "powder clumping",
        "counterfeit",
        25,
        r"clump\w*|room.temperature.{0,25}(?:residue|dissolv)|powder.{0,20}residue",
    ),
    (
        "syrup adulteration allegation",
        "counterfeit",
        55,
        r"[cn][ -]?(?:3|4).{0,35}syrup|rice.syrup|sugar.syrup|nmr.{0,25}adulter",
    ),
    (
        "cold-chain spoilage",
        "hazard",
        50,
        r"sour|curdled|thawed|expired milk|khatta|खट्टा|புளித்த|పులిసిన|ಹುಳಿ|പുളിച്ച|টক|ખાટું|ଆମ୍ବିଳ|ਖੱਟਾ",
    ),
    ("pest damage", "hazard", 55, r"pest|rat.damage|chewed carton|चूहे"),
]


def extract_entities(text: str) -> list[Entity]:
    entities = []
    for normalized, kind, severity, pattern in LEXICON:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        preceding = text[max(0, match.start() - 18) : match.start()].lower()
        if kind == "symptom" and re.search(
            r"(?:no|without|denies|not reporting)\s+$", preceding
        ):
            continue
        entities.append(
            Entity(
                text=match.group(), kind=kind, normalized=normalized, severity=severity
            )
        )
    for match in re.finditer(
        r"\b(?:lot[- ]|batch[ :#-]*)([A-Za-z0-9]+(?:-[A-Za-z0-9]+){0,4})\b", text, re.I
    ):
        entities.append(
            Entity(text=match.group(), kind="batch", normalized=match.group().strip())
        )
    return entities


@dataclass(frozen=True)
class TransformerFusion:
    """Optional locally provisioned encoders and COMET generation; never downloaded on boot."""

    hinglish_model: str
    indic_model: str
    comet_model: str = ""

    @lru_cache(maxsize=1)
    def _encoders(self):
        from transformers import AutoModel, AutoTokenizer

        return [
            (
                AutoTokenizer.from_pretrained(model, local_files_only=True),
                AutoModel.from_pretrained(model, local_files_only=True).eval(),
            )
            for model in (self.hinglish_model, self.indic_model)
        ]

    def embeddings(self, text: str) -> list[list[float]]:
        import torch

        output = []
        for tokenizer, model in self._encoders():
            encoded = tokenizer(
                text, return_tensors="pt", truncation=True, max_length=256
            )
            with torch.no_grad():
                hidden = model(**encoded).last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
            output.append(pooled[0].tolist())
        return output

    def commonsense(self, text: str) -> list[str]:
        if not self.comet_model:
            return []
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            self.comet_model, local_files_only=True
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            self.comet_model, local_files_only=True
        ).eval()
        tokens = tokenizer(
            f"{text} xEffect [GEN]", return_tensors="pt", truncation=True
        )
        output = model.generate(**tokens, max_new_tokens=40, do_sample=False)
        return tokenizer.batch_decode(output, skip_special_tokens=True)
