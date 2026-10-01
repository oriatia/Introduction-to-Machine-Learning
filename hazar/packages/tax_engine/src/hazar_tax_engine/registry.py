"""Rule registry: every rule the engine knows, the facts it needs, and the documents it relies on.

The questionnaire asks only for facts some rule needs. No tax values live here: rules reference their per-year
values in tables/{year}.yaml (Sprint 3+).

Hebrew titles/explanations are placeholder copy pending review. `legal_ref` stays None until the tax advisor
supplies and verifies the section of the Income Tax Ordinance (CLAUDE.md principles 2 and 3).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Fact(StrEnum):
    """Facts about the taxpayer the questionnaire can collect."""

    RESIDENT = "resident"
    SEX = "sex"
    MARITAL_STATUS = "marital_status"
    CHILDREN = "children"
    SINGLE_PARENT = "single_parent"
    DEGREES = "degrees"
    DISCHARGE = "discharge"
    ALIYAH = "aliyah"
    DISABILITY = "disability"
    MULTIPLE_EMPLOYER_YEARS = "multiple_employer_years"
    DONATION_YEARS = "donation_years"
    LIFE_INSURANCE_YEARS = "life_insurance_years"
    PENSION_SELF_YEARS = "pension_self_years"
    LOCALITIES = "localities"
    PARTIAL_YEARS = "partial_years"


class DocumentType(StrEnum):
    FORM_106 = "form_106"
    FORM_867 = "form_867"
    DONATION_RECEIPT = "donation_receipt"
    INSURANCE = "insurance"
    PENSION = "pension"
    OTHER = "other"


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    title_he: str
    explanation_he: str
    required_facts: tuple[Fact, ...]
    documents: tuple[DocumentType, ...] = (DocumentType.FORM_106,)
    # Usually already applied by the employer via Form 101; not reported as a finding by itself.
    baseline: bool = False
    legal_ref: str | None = None
    legal_ref_verified: bool = False


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="credit.resident",
        title_he="נקודות זיכוי לתושב ישראל",
        explanation_he="כל תושב ישראל זכאי לנקודות זיכוי בסיסיות. בדרך כלל המעסיק כבר מחשב אותן.",
        required_facts=(Fact.RESIDENT,),
        baseline=True,
    ),
    Rule(
        rule_id="credit.woman",
        title_he="נקודות זיכוי לאישה",
        explanation_he="לנשים יש נקודות זיכוי נוספות. בדרך כלל המעסיק כבר מחשב אותן.",
        required_facts=(Fact.SEX,),
        baseline=True,
    ),
    Rule(
        rule_id="credit.children",
        title_he="נקודות זיכוי על ילדים",
        explanation_he="הורים זכאים לנקודות זיכוי לפי גילי הילדים בכל שנת מס.",
        required_facts=(Fact.CHILDREN, Fact.SEX, Fact.MARITAL_STATUS),
    ),
    Rule(
        rule_id="credit.single_parent",
        title_he="נקודות זיכוי להורה יחיד",
        explanation_he="הורה יחיד שמגדל ילדים עשוי להיות זכאי לנקודות זיכוי נוספות.",
        required_facts=(Fact.SINGLE_PARENT, Fact.CHILDREN, Fact.MARITAL_STATUS),
    ),
    Rule(
        rule_id="credit.academic_degree",
        title_he="נקודות זיכוי לבעלי תואר אקדמי",
        explanation_he="מי שסיים תואר אקדמי עשוי להיות זכאי לנקודות זיכוי בשנים שאחרי סיום הלימודים.",
        required_facts=(Fact.DEGREES,),
        documents=(DocumentType.FORM_106, DocumentType.OTHER),
    ),
    Rule(
        rule_id="credit.discharged_soldier",
        title_he="נקודות זיכוי לחיילים משוחררים ולמסיימי שירות לאומי",
        explanation_he="מי שסיים שירות סדיר או לאומי עשוי להיות זכאי לנקודות זיכוי בשנים שאחרי השחרור.",
        required_facts=(Fact.DISCHARGE,),
        documents=(DocumentType.FORM_106, DocumentType.OTHER),
    ),
    Rule(
        rule_id="credit.new_immigrant",
        title_he="נקודות זיכוי לעולים חדשים ולתושבים חוזרים",
        explanation_he="עולים חדשים עשויים להיות זכאים לנקודות זיכוי בשנים הראשונות בארץ.",
        required_facts=(Fact.ALIYAH,),
        documents=(DocumentType.FORM_106, DocumentType.OTHER),
    ),
    Rule(
        rule_id="credit.disability",
        title_he="הטבות מס בשל נכות",
        explanation_he="נכות של מגיש הבקשה או של בן משפחה עשויה לזכות בהטבות מס.",
        required_facts=(Fact.DISABILITY,),
        documents=(DocumentType.FORM_106, DocumentType.OTHER),
    ),
    Rule(
        rule_id="income.multiple_employers",
        title_he="כמה מעסיקים בלי תיאום מס",
        explanation_he="מי שעבד אצל כמה מעסיקים באותה שנה בלי תיאום מס, ייתכן שנוכה ממנו מס ביתר.",
        required_facts=(Fact.MULTIPLE_EMPLOYER_YEARS,),
    ),
    Rule(
        rule_id="income.partial_year",
        title_he="שנה שבה לא עבדת את כל השנה",
        explanation_he="מי שעבד רק בחלק מהשנה, ייתכן שנוכה ממנו מס לפי הכנסה שנתית גבוהה מהאמיתית.",
        required_facts=(Fact.PARTIAL_YEARS,),
    ),
    Rule(
        rule_id="deduction.donations",
        title_he="זיכוי על תרומות",
        explanation_he="תרומות למוסדות מוכרים עשויות לזכות בזיכוי ממס.",
        required_facts=(Fact.DONATION_YEARS,),
        documents=(DocumentType.DONATION_RECEIPT,),
    ),
    Rule(
        rule_id="deduction.life_insurance",
        title_he="זיכוי על ביטוח חיים",
        explanation_he="תשלומים פרטיים לביטוח חיים עשויים לזכות בזיכוי ממס.",
        required_facts=(Fact.LIFE_INSURANCE_YEARS,),
        documents=(DocumentType.INSURANCE,),
    ),
    Rule(
        rule_id="deduction.pension_self",
        title_he="הפקדות עצמאיות לפנסיה",
        explanation_he="הפקדות לפנסיה שלא דרך המעסיק עשויות לזכות בהטבת מס.",
        required_facts=(Fact.PENSION_SELF_YEARS,),
        documents=(DocumentType.PENSION,),
    ),
    Rule(
        rule_id="credit.eligible_locality",
        title_he="הטבת מס ליישובים מזכים",
        explanation_he="תושבי יישובים מסוימים זכאים להטבת מס. נבדוק את היישוב מול הרשימה הרשמית לכל שנה.",
        required_facts=(Fact.LOCALITIES,),
    ),
)

RULES_BY_ID: dict[str, Rule] = {r.rule_id: r for r in RULES}


def required_facts() -> set[Fact]:
    """Every fact that at least one rule needs. The questionnaire asks for exactly these."""
    return {f for r in RULES for f in r.required_facts}
