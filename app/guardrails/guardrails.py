"""
Comprehensive Multi-Layer AI Guardrails Module for InsureGPT.
Protects against prompt injection, jailbreaks, PII leakage, out-of-scope queries,
and unauthorized claims adjudication statements.
Designed for a friendly, trustworthy experience for non-technical users.
"""
import re
from typing import Tuple, Dict, Any, Optional


class AIGuardrails:
    """Multi-layer safety and scope guardrails for insurance decision support."""

    def __init__(self):
        self.max_length = 4000

        # Pattern sets for Prompt Injections & Jailbreaks
        self.injection_patterns = [
            r"ignore\s+(all\s+|previous\s+|any\s+|prior\s+)?instructions",
            r"disregard\s+(all\s+|previous\s+|any\s+|prior\s+)?(instructions|prompts|rules)",
            r"forget\s+(all\s+|previous\s+|everything|your\s+instructions)",
            r"(reveal|show|print|display|tell\s+me)\s+(your\s+)?(system\s+prompt|initial\s+prompt|instructions|hidden\s+prompt)",
            r"(systeminfo|system_info|operating\s+system\s+info|print\s+env|getenv)",
            r"\b(jailbreak|dan\s+mode|developer\s+mode|unrestricted\s+mode)\b",
            r"(you\s+are\s+now|act\s+as)\s+(an\s+unrestricted|a\s+hacker|dan|evil)",
            r"(bypass|disable|override)\s+(guardrails|safety|security|rules|filters)",
            r"(pretend|simulate)\s+(there\s+are\s+no\s+rules|you\s+have\s+no\s+ethics)",
            r"\b(cat\s+/etc/passwd|drop\s+table|exec\s*\()",
            r"(api[_\s]?key|secret[_\s]?key|pinecone[_\s]?key|groq[_\s]?key)\s*(reveal|leak|print|show)",
        ]

        # Explicit out-of-scope non-insurance programming / hacking / recipe queries
        self.out_of_scope_patterns = [
            r"^(write|generate|create)\s+(a\s+)?(python|javascript|typescript|c\+\+|java|php|sql|html|css)\s+(code|script|program|app|function)",
            r"^(how\s+to\s+)?(bake|cook|make)\s+(a\s+)?(cake|pizza|pasta|cookies|recipe)",
            r"^(who\s+won|who\s+is\s+the\s+winner\s+of)\s+(the\s+)?(world\s+cup|super\s+bowl|ipl|champions\s+league|election)",
            r"^(write\s+a\s+)?(poem|story|song|rap|essay)\s+about",
            r"^(how\s+to\s+)?(hack|crack|bypass)\s+(wifi|facebook|instagram|password|website)",
            r"^solve\s+this\s+math\s+equation",
        ]

        # Insurance domain keywords for context confirmation
        self.insurance_keywords = {
            "policy", "insurance", "claim", "claims", "hospital", "hospitalization", "icu", "room rent",
            "cashless", "reimbursement", "coverage", "cover", "covered", "exclusion", "exclusions",
            "waiting period", "deductible", "co-pay", "copay", "premium", "pre-existing", "ped",
            "motor", "car", "vehicle", "own damage", "third party", "zero dep", "engine protector",
            "term life", "death benefit", "sum assured", "critical illness", "cancer", "heart attack",
            "commercial property", "fire", "sfsp", "reinstatement", "stocks", "factory",
            "travel", "baggage", "flight delay", "overseas", "evacuation", "emergency medical",
            "doctor", "surgery", "mediclaim", "tpa", "ayush", "maternity", "newborn", "day care",
            "nominee", "nomination", "moratorium", "section 45", "dispute", "ombudsman", "dossier",
            "discharge summary", "invoice", "receipt", "kyc", "fir", "mlc"
        }

    def validate_input(self, user_query: str) -> Tuple[bool, str, str]:
        """
        Validate input against length limits, prompt injection, PII, and domain scope.
        Returns:
            Tuple[is_safe (bool), category (str), message (str)]
        """
        if not user_query or not user_query.strip():
            return False, "EMPTY_INPUT", "Please enter a question or policy topic to get started."

        text = user_query.strip()

        # Length guardrail
        if len(text) > self.max_length:
            return False, "LENGTH_EXCEEDED", f"Your question is too long ({len(text)} characters). Please limit your question to {self.max_length} characters."

        text_lower = text.lower()

        # 1. Prompt Injection & Jailbreak Guardrail
        for pattern in self.injection_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                guardrail_response = (
                    "### 🛡️ InsureGPT Security Guardrail Active\n\n"
                    "- **Security Directive**: InsureGPT operates strictly as a secure policy guidance and claims decision-support advisor.\n"
                    "- **Instruction Protection**: System instruction overrides, administrative commands, prompt extraction, and jailbreak attempts are strictly prohibited.\n"
                    "- **How I Can Help**: Please ask any question regarding your **health, motor, term life, commercial property, or travel insurance policies**, such as coverage limits, required claim forms, or waiting periods."
                )
                return False, "PROMPT_INJECTION", guardrail_response

        # 2. Sensitive Financial PII Guardrail (Credit card numbers, bank PINs)
        # Matches 13-16 digit numbers with hyphens/spaces
        cc_match = re.search(r"\b(?:\d[ -]*?){13,16}\b", text)
        if cc_match:
            digits_only = re.sub(r"\D", "", cc_match.group(0))
            if len(digits_only) in [15, 16] and (digits_only.startswith("4") or digits_only.startswith("5") or digits_only.startswith("3")):
                guardrail_response = (
                    "### 🛡️ Privacy & Data Protection Notice\n\n"
                    "- **Sensitive Data Detected**: For your security and financial privacy, please do not submit credit card numbers, CVVs, passwords, or personal banking PINs.\n"
                    "- **Safe Usage**: InsureGPT only requires general policy inquiries, coverage conditions, or claims procedures to assist you."
                )
                return False, "SENSITIVE_PII", guardrail_response

        # 3. Explicit Out-of-Scope Guardrail
        for pattern in self.out_of_scope_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Ensure no insurance keywords are present before blocking
                has_insurance_ctx = any(k in text_lower for k in self.insurance_keywords)
                if not has_insurance_ctx:
                    guardrail_response = (
                        "### 🛡️ InsureGPT Insurance Scope Notice\n\n"
                        "- **Dedicated Scope**: InsureGPT is designed exclusively to assist policyholders with insurance policies, coverage rules, claims workflows, and documentation requirements.\n"
                        "- **Out-of-Scope Topic**: Your question appears to be outside of the insurance decision-support domain.\n"
                        "- **What You Can Ask**:\n"
                        "  - **🏥 Health & Hospitalization**: Room rent sub-limits, ICU caps, day-care procedures, waiting periods.\n"
                        "  - **📄 Claims Documentation**: Reimbursement checklist, cashless pre-authorization, intimation deadlines.\n"
                        "  - **🚗 Car Insurance**: Own Damage (OD) repairs, Third-Party Liability, Zero Depreciation add-on.\n"
                        "  - **🛡️ Life & Critical Illness**: 36 critical illnesses, terminal illness acceleration, Section 45 rules.\n"
                        "  - **🏢 Commercial Property**: Fire and special perils (SFSP), machinery reinstatement, stocks valuation.\n"
                        "  - **✈️ International Travel**: Emergency medical evacuation, trip cancellation, baggage delay abroad."
                    )
                    return False, "OUT_OF_SCOPE", guardrail_response

        return True, "SAFE", ""

    def validate_output(self, response_text: str) -> str:
        """
        Verify output safety:
        - Prevents unauthorized claims approval guarantees.
        - Ensures standard decision-support disclaimer is present.
        """
        approval_phrases = [
            r"your claim is (hereby )?approved",
            r"we have approved your claim",
            r"claim has been sanctioned for payout",
            r"amount will be transferred to your account tomorrow"
        ]

        text = response_text
        for pat in approval_phrases:
            if re.search(pat, text, re.IGNORECASE):
                text = re.sub(
                    pat,
                    "this claim condition meets standard eligibility guidelines for evaluation",
                    text,
                    flags=re.IGNORECASE
                )

        # Ensure decision-support notice is attached if not already present
        if "decision-support" not in text.lower() and "source" not in text.lower():
            text += (
                "\n\n> [!NOTE]\n"
                "> **Official Notice**: InsureGPT provides policy guidance and eligibility estimation. "
                "It does not issue autonomous claim approvals or financial settlements. "
                "Final adjudications remain solely with the authorized insurance underwriter."
            )

        return text
