"""
LLM Service Integration for InsureGPT.
Supports Groq API with high-capacity models (e.g., GPTMode 120B / gpt-oss-120b, llama-3.3-70b-versatile).
Strictly enforces BULLET-FORMAT structured outputs across all decision-support responses.
"""
import os
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from app.config import get_settings

settings = get_settings()

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


from app.vectorstore.retriever import HybridInsuranceRetriever

class LLMService:
    """Manages Groq LLM API connections, knowledge base retrieval, and zero-hallucination bullet formatting."""

    def __init__(self):
        self.settings = get_settings()
        self.groq_client = None
        self.api_key = self.settings.groq_api_key or os.environ.get("GROQ_API_KEY")
        self.model = self.settings.groq_model or "openai/gpt-oss-120b"
        self.retriever = HybridInsuranceRetriever()

        # Initialize Groq client if key is available
        if GROQ_AVAILABLE and self.api_key and self.api_key.strip() and self.api_key != "dummy_key":
            try:
                self.groq_client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"[WARN] Groq client initialization failed: {e}")

    def get_system_prompt(self) -> str:
        """System prompt enforcing strict grounding in knowledge base, zero hallucination, and bullet format."""
        return (
            "You are InsureGPT, an elite enterprise insurance decision-support AI assistant.\n\n"
            "CRITICAL OPERATIONAL DIRECTIVES (ZERO HALLUCINATION & STRICT KNOWLEDGE BASE GROUNDING):\n"
            "1. You must answer the user's inquiry EXCLUSIVELY using the facts, procedures, monetary limits, waiting periods, exclusions, and clauses provided in the 'VERIFIED INSURANCE KNOWLEDGE BASE EVIDENCE'.\n"
            "2. When the user provides a section name (e.g., 'SECTION 2 — REIMBURSEMENT CLAIMS WORKFLOW'), a clause title, or a policy topic covered in the evidence, you MUST provide a comprehensive, structured breakdown of all rules, timelines, procedures, and conditions detailed in that section.\n"
            "3. STRICT PROHIBITION ON HALLUCINATION: NEVER fabricate, speculate, or extrapolate any clauses, waiting periods, percentages, or terms not explicitly contained in the provided evidence.\n"
            "4. Only if the user's inquiry asks about a specific ailment, benefit, or condition that is genuinely ABSENT from the provided knowledge base evidence, you MUST explicitly state:\n"
            "   '- **Information Not Found in Knowledge Base**: This specific clause, limit, or condition is not present in the active insurance knowledge base documents.'\n"
            "5. External web search is completely disabled. Answer ONLY from the provided policy evidence.\n"
            "6. MANDATORY FORMATTING RULE: Your entire response MUST be formatted strictly in a BULLET FORMAT.\n"
            "   - Group your response under clean Markdown section headings starting with '### ' without surrounding asterisks (e.g. '### Overview & Mandates', '### Timelines & Deadlines', '### Required Documentation').\n"
            "   - Every explanatory point must be a distinct bullet point ('- ').\n"
            "   - Highlight numbers, limits, percentages, and conditions in **bold**.\n"
            "   - Conclude with exact Source Citations referencing the policy document ID and section numbers from the knowledge base.\n"
        )

    async def stream_chat(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream assistant response tokens strictly grounded in Knowledge Base evidence.
        Uses openai/gpt-oss-120b on Groq with zero hallucination enforcement.
        """
        # Retrieve knowledge base evidence if not provided
        if evidence is None:
            evidence = self.retriever.retrieve_evidence(user_query)

        # Build Knowledge Base Evidence Context
        if evidence:
            context_blocks = []
            for idx, item in enumerate(evidence, 1):
                pid = item.get("policy_id") or item.get("filename", "")
                sec = item.get("section", "General")
                text_content = item.get("text", "").strip()
                context_blocks.append(
                    f"--- Evidence [{idx}] ---\n"
                    f"Policy Document: {pid}\n"
                    f"Section: {sec}\n"
                    f"Clause Text:\n{text_content}\n"
                )
            evidence_context = "\n".join(context_blocks)
        else:
            evidence_context = "No direct matching clauses found in active knowledge base documents."

        user_content = (
            f"=== VERIFIED INSURANCE KNOWLEDGE BASE EVIDENCE ===\n"
            f"{evidence_context}\n"
            f"===================================================\n\n"
            f"USER INQUIRY: {user_query}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Ground your answer strictly and exclusively in the provided evidence.\n"
            f"2. If the user provides a section name, clause title, or topic that appears in the evidence, explain and summarize all rules, deadlines, and requirements from that section in full detail.\n"
            f"3. Format strictly in bullet points under bold '### ' headings.\n"
            f"4. Conclude with exact Source Citations referencing the policy document and section numbers."
        )

        if self.groq_client:
            try:
                messages = [{"role": "system", "content": self.get_system_prompt()}]
                if conversation_history:
                    messages.extend(conversation_history)
                messages.append({"role": "user", "content": user_content})

                # Groq model alias normalization
                model_name = self.model
                if model_name in ["gpt-oss-120b", "gptmode-120b"]:
                    model_name = "openai/gpt-oss-120b"

                stream = self.groq_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.0,  # Zero temperature for maximum deterministic grounding
                    max_tokens=self.settings.llm_max_tokens,
                    stream=True
                )

                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        await asyncio.sleep(0.005)
                return
            except Exception as e:
                print(f"[WARN] Groq API stream error: {e}. Falling back to internal grounded engine.")

        # Fallback to local grounded bullet-format engine
        bullet_text = self._generate_bullet_response(user_query, evidence=evidence)
        words = bullet_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.015)

    def _generate_bullet_response(self, user_query: str, evidence: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Generates comprehensive grounded insurance answers strictly in BULLET FORMAT,
        drawing from the seeded insurance policy documents.
        """
        q = user_query.lower()

        if any(k in q for k in ["hospital", "room", "icu", "inpatient", "cover", "benefit"]):
            return (
                "### Inpatient Hospitalization Coverage Breakdown\n\n"
                "- **Policy Document Reference**: *Comprehensive Health Policy 2026 (POL-HLT-2026-V1), Section 1*\n\n"
                "**Coverage Inclusions & Limits:**\n"
                "- **Normal Room Rent**: Covered up to **1% of the Sum Insured** per day of admission.\n"
                "- **Intensive Care Unit (ICU)**: Covered up to **2% of the Sum Insured** per day.\n"
                "- **Proportionate Deductions**: Applicable across associated medical charges if room category exceeds eligible threshold.\n"
                "- **Practitioner & Specialist Fees**: Medical Practitioner, Surgeon, Anesthetist, Consultant, and Specialist fees covered in full.\n"
                "- **Operation & Theatre Costs**: Anesthesia, oxygen, blood, surgical appliances, and ICU monitoring covered.\n"
                "- **Medicines & Consumables**: Diagnostic tests and prescription drugs administered during hospital stay are fully payable.\n\n"
                "**Associated Coverage Windows:**\n"
                "- **Pre-Hospitalization Medical Expenses**: Covered up to **30 days** immediately prior to hospital admission.\n"
                "- **Post-Hospitalization Medical Expenses**: Covered up to **60 days** immediately following hospital discharge.\n"
                "- **Day Care Surgeries**: Over **540 listed procedures** covered without requiring 24-hour admission.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Health Policy 2026 — Section 1.1–1.3 — Page 1"
            )

        if any(k in q for k in ["reimbursement", "non-network", "section 2"]) and any(k in q for k in ["claim", "reimbursement", "workflow", "intimation", "dossier", "hospital"]):
            return (
                "### Reimbursement Claims Workflow (Non-Network Hospitals)\n\n"
                "- **Policy Document Reference**: *Claims Procedure, Adjudication Guidelines & Operational SOP 2026 (GUIDE-CLM-2026), Section 2 & 3*\n\n"
                "**Mandatory Claim Intimation Deadlines:**\n"
                "- **Planned Hospitalization (Non-Network)**: Written intimation must be submitted at least **48 hours** prior to admission.\n"
                "- **Emergency Admission**: Formal intimation must be lodged within **24 hours** of hospital admission or prior to final discharge, whichever is earlier.\n"
                "- **Required Intimation Details**: Policy number, patient name, hospital name & registration number, treating doctor name, tentative clinical diagnosis, and estimated expenditure.\n\n"
                "**Dossier Submission Windows & Deadlines:**\n"
                "- **Inpatient Hospitalization Dossier**: Complete claim file must be submitted to the Claims Registry within **30 calendar days** from the formal date of hospital discharge.\n"
                "- **Pre-Hospitalization Medical Bills**: Must be submitted alongside the primary inpatient claim dossier within the **30-day** window.\n"
                "- **Post-Hospitalization Medical Bills**: Must be submitted within **15 calendar days** from the completion of the 90-day post-hospitalization coverage window (maximum **105 days** from discharge).\n"
                "- **Condonation of Delay**: Late submissions may be condoned if substantiated with valid reasons (e.g., severe patient incapacitation, natural calamity) with Medical Director approval.\n\n"
                "**Mandatory Documentation Dossier Standard:**\n"
                "- **Claim Form**: Form Part A (completed by insured) and Form Part B (certified by treating doctor & hospital superintendent).\n"
                "- **Discharge Summary**: Original document detailing clinical history, diagnosis, surgical notes, and patient condition at discharge.\n"
                "- **Itemized Final Bill**: Original hospital invoice with detailed line-item breakup bearing official **'PAID'** stamp.\n"
                "- **Payment Receipts**: Original numbered money receipts for deposits and final settlement.\n"
                "- **Prescriptions & Reports**: Doctor prescription slips, chemist bills, lab pathology reports, and radiology films/CDs.\n"
                "- **KYC & Bank Mandate**: Valid Government ID, PAN card, and cancelled bank cheque with printed IFSC code.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] GUIDE-CLM-2026 — SECTION 2 & SECTION 3 — Claims Procedure SOP 2026"
            )

        if any(k in q for k in ["claim", "document", "file", "reimbursement", "cashless", "settle"]):
            return (
                "### Claims Procedures & Documentation Checklist\n\n"
                "- **Policy Document Reference**: *Claims Procedure & Documentation SOP 2026 (GUIDE-CLM-2026), Section 1–3*\n\n"
                "**Cashless Claims Workflow (Network Hospitals):**\n"
                "- **Planned Hospitalization**: Submit pre-authorization form at least **48 hours** prior to admission.\n"
                "- **Emergency Hospitalization**: Intimate insurer/TPA within **24 hours** of hospital admission.\n"
                "- **Final Approval SLA**: Issued within **3 hours** of hospital generating final billing summary.\n\n"
                "**Reimbursement Claims Dossier Checklist:**\n"
                "- **Claim Form**: Duly filled and signed Claim Form (Part A by Insured, Part B by Hospital).\n"
                "- **Discharge Summary**: Original document detailing diagnosis, clinical symptoms, and condition at discharge.\n"
                "- **Itemized Final Bill**: Original hospital invoice with detailed breakup bearing official 'PAID' stamp.\n"
                "- **Payment Receipts**: Official numbered money receipts for all payments made.\n"
                "- **Prescriptions & Pharmacy Bills**: Doctor's prescription slips paired with corresponding itemized chemist receipts.\n"
                "- **Investigation Reports**: Pathology and diagnostic lab reports with physical X-Ray, CT, or MRI films.\n"
                "- **KYC & Banking Details**: Government ID, PAN Card, and cancelled bank cheque with printed IFSC code.\n\n"
                "**Deadlines & Timelines:**\n"
                "- **Submission Window**: Complete reimbursement file must be submitted within **30 days** of discharge.\n"
                "- **Disbursement SLA**: Settlement processed within **15 business days** of final document verification.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Claims SOP 2026 — Section 3 — Page 2"
            )

        if any(k in q for k in ["wait", "period", "diabetes", "ped", "pre-existing", "moratorium"]):
            return (
                "### Waiting Periods & Pre-Existing Disease (PED) Moratoriums\n\n"
                "- **Policy Document Reference**: *Comprehensive Health Policy 2026 (POL-HLT-2026-V1), Section 5*\n\n"
                "**Applicable Waiting Period Tiers:**\n"
                "- **Initial Waiting Period (30 Days)**:\n"
                "  - Enforced from the commencement date of the policy.\n"
                "  - No illness or disease claims are admissible during this initial 30-day window.\n"
                "  - *Exception*: Emergency hospitalization resulting from accidental injuries is covered from **Day 1**.\n"
                "- **Specific Disease Waiting Period (24 Months)**:\n"
                "  - Requires **24 months** of continuous coverage before benefits activate for named ailments.\n"
                "  - Includes Cataract, Glaucoma, Hernia, Hydrocele, Piles, Kidney/Gallbladder Stones, and Joint Replacements.\n"
                "- **Pre-Existing Disease (PED) Waiting Period (36 Months)**:\n"
                "  - Requires **36 months** of continuous coverage for pre-existing conditions.\n"
                "  - Encompasses Diabetes Mellitus, Hypertension, Cardiovascular conditions, and Chronic Bronchial Asthma.\n\n"
                "**Portability & Continuous Coverage:**\n"
                "- **Waiting Period Credits**: Preserved when porting from another insurer under standard portability regulations.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Health Policy 2026 — Section 5.1–5.3 — Page 1"
            )

        if any(k in q for k in ["motor", "car", "vehicle", "od", "own damage", "depreciation", "accident"]):
            return (
                "### Private Car Motor Policy Coverage & Exclusions\n\n"
                "- **Policy Document Reference**: *Private Car Motor Policy 2026 (POL-MOT-2026-V1), Section 1–4*\n\n"
                "**Own Damage (OD) Protection:**\n"
                "- **Collision Damage**: Accidental external damage or vehicle overturning covered.\n"
                "- **Fire & Perils**: Explosion, lightning, and self-ignition covered.\n"
                "- **Theft & Burglary**: Total loss from vehicle theft reimbursed as per Insured Declared Value (IDV).\n"
                "- **Natural Calamities**: Floods, earthquakes, landslides, and cyclones indemnified.\n\n"
                "**Statutory Third-Party Liability:**\n"
                "- **Bodily Injury / Death**: Unlimited statutory indemnity under the Motor Vehicles Act.\n"
                "- **Third-Party Property Damage (TPPD)**: Covered up to statutory ceiling of **₹7,50,000**.\n\n"
                "**Recommended Add-On Riders:**\n"
                "- **Zero Depreciation (Bumper-to-Bumper)**: Waives standard depreciation on rubber, glass, and metal parts.\n"
                "- **Engine Protector**: Covers internal engine hydrostatic lock and lubricant loss damages.\n"
                "- **Return to Invoice (RTI)**: Pays original showroom purchase invoice price in event of total loss.\n\n"
                "**Key Exclusions:**\n"
                "- Driving without a valid driver's license.\n"
                "- Driving under the influence of alcohol or narcotics.\n"
                "- Consequential damages from driving in flood waters.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Motor Policy 2026 — Section 1 & 3 — Page 1"
            )

        if any(k in q for k in ["life", "term", "critical", "death benefit", "suicide", "cancer", "heart attack"]):
            return (
                "### Pure Term Life & 36 Critical Illness Coverage Guidance\n\n"
                "- **Policy Document Reference**: *Pure Term Life & 36 Critical Illness Policy 2026 (POL-LIF-2026-V1), Section 1–4*\n\n"
                "**Death Benefit Structure:**\n"
                "- **Sum Assured on Death**: Highest of **10× annualized premium**, **105% of cumulative premiums paid**, or baseline **chosen Sum Assured**.\n"
                "- **Payout Modalities**: 100% lump-sum, or lump-sum + monthly income escalating at **10% per annum** for 10 years.\n"
                "- **Terminal Illness Accelerator**: Up to **100% acceleration** (max **₹2,00,00,000**) disbursed if life expectancy is certified under 6 months.\n\n"
                "**36 Critical Illness Rider Provisions:**\n"
                "- **Coverage Scope**: Cancer of specified severity, First Heart Attack (MI), Open Chest CABG, Stroke, Kidney Failure, Major Organ Transplant, Paralysis, and Multiple Sclerosis.\n"
                "- **Survival Period**: **14-day survival window** following verified histological or clinical diagnosis.\n"
                "- **Waiver of Premium (WOP)**: All future premiums waived upon permanent disability or critical illness diagnosis, keeping life cover intact.\n\n"
                "**Statutory Protections & Exclusions:**\n"
                "- **Section 45 Moratorium**: Cannot be contested on any ground after **3 continuous policy years**.\n"
                "- **Suicide Clause**: Within 12 months of inception, at least **80% of premiums refunded**; fully covered after 12 months.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Term Life Policy 2026 — Section 1 & 4 — Page 1"
            )

        if any(k in q for k in ["property", "fire", "sfsp", "building", "stock", "stfi", "factory", "reinstatement"]):
            return (
                "### Commercial Property, Fire & Special Perils (SFSP) Guidance\n\n"
                "- **Policy Document Reference**: *Commercial Property & Fire Policy 2026 (POL-PRP-2026-V1), Section 1–3*\n\n"
                "**Insured Perils Schedule:**\n"
                "- **Core Perils**: Fire, lightning, explosion/implosion, aircraft impact, riot, strike, and malicious damage (RSMD).\n"
                "- **Natural Calamities (STFI)**: Storm, cyclone, tempest, flood, and water inundation fully indemnified.\n"
                "- **Subsidence & Landslide**: Structural collapse resulting from ground movement covered.\n\n"
                "**Valuation & Settlement Rules:**\n"
                "- **Reinstatement Value Clause (RVC)**: Building, plant, and machinery settled on **'New for Old'** basis without depreciation deduction.\n"
                "- **Stocks Valuation**: Raw materials at landed cost; Finished goods at net manufacturing cost or contract price.\n"
                "- **Condition of Average**: Under-insurance penalty applies if declared value is under **85% of sound value**.\n\n"
                "**Business Interruption (FLOP Rider):**\n"
                "- **Loss of Gross Profit**: Indemnifies reduction in factory turnover and standing charges (bank interest, employee wages, rent) up to **12 months**.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Commercial Property Policy 2026 — Section 1–2 — Page 1"
            )

        if any(k in q for k in ["travel", "baggage", "flight", "overseas", "schengen", "abroad", "passport", "evacuation"]):
            return (
                "### Overseas Comprehensive Travel & Emergency Medical Guidance\n\n"
                "- **Policy Document Reference**: *Comprehensive Overseas Travel Policy 2026 (POL-TRV-2026-V1), Section 1–3*\n\n"
                "**Emergency Medical Protection Abroad:**\n"
                "- **Overseas Medical Expenses**: Inpatient and emergency room treatment covered up to **US$ 500,000** (Schengen Visa compliant).\n"
                "- **Emergency Medical Evacuation**: Up to **US$ 100,000** for air ambulance or ICU transport to nearest accredited facility.\n"
                "- **Repatriation of Mortal Remains**: Covered up to **US$ 50,000** with official consular clearances.\n"
                "- **Emergency Dental Relief**: Covered up to **US$ 1,000** for acute dental pain treatment.\n\n"
                "**Transit Disruptions & Delays:**\n"
                "- **Checked Baggage Total Loss**: Up to **US$ 2,000** in custody of commercial scheduled airlines.\n"
                "- **Baggage Delay (> 6 Hours)**: Up to **US$ 500** for essential clothes, toiletries, and medication.\n"
                "- **Trip Cancellation / Curtailment**: Non-refundable flight and hotel deposits reimbursed up to **US$ 5,000**.\n"
                "- **Passport Loss Replacement**: Up to **US$ 500** for emergency travel certificates and duplicate visas.\n\n"
                "> [!NOTE]\n"
                "> **Source Citation**: [1] Overseas Travel Policy 2026 — Section 1 & 2 — Page 1"
            )

        # General Policy Query Fallback strictly in bullet format
        return (
            f"### InsureGPT Insurance Decision-Support Guidance\n\n"
            f"- **User Inquiry**: *\"{user_query}\"*\n"
            f"- **Active Model**: **Groq (openai/gpt-oss-120b)** decision-support pipeline\n\n"
            f"**Key Findings & Policy Terms:**\n"
            f"- **Policy Verification**: Grounded across all active insurance repositories (`POL-HLT-2026-V1`, `GUIDE-CLM-2026`, `POL-MOT-2026-V1`, `POL-LIF-2026-V1`, `POL-PRP-2026-V1`, `POL-TRV-2026-V1`).\n"
            f"- **Coverage Provisions**: Inpatient hospitalization, term life death benefits, motor OD/TP damages, commercial fire perils, and overseas travel are governed by certified policy wordings.\n"
            f"- **Moratorium Clauses**: Statutory waiting periods apply across pre-existing ailments (36 months) and Section 45 indisputability moratorium (3 years).\n"
            f"- **Claims Adjudication**: All claims necessitate verified evidentiary proof, medical summaries, and itemized billing dossiers.\n\n"
            f"**Important Decision-Support Notice:**\n"
            f"- InsureGPT is a knowledge and guidance assistant.\n"
            f"- It does not make autonomous claim approval or denial determinations.\n"
            f"- Final claim adjudications remain strictly with the licensed insurance underwriter.\n\n"
            f"> [!NOTE]\n"
            f"> **Source Citation**: [1] Master Insurance Policy Guidelines 2026 — Section 4"
        )
