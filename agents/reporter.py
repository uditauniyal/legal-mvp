from fpdf import FPDF
from agents.router import QueryPlan
import textwrap

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Legal MVP - Preliminary Advisory Report', border=False, align='C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

class ReporterAgent:
    def __init__(self):
        pass

    def generate_report(self, query: str, plan, answer_data: dict, filename="report.pdf"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # --- ROBUST TEXT SANITIZATION HELPER ---
        def clean_text(text):
            if not isinstance(text, str):
                return str(text)
            
            # 1. Replace common non-Latin characters
            replacements = {
                "₹": "Rs.",
                "—": "-",
                "–": "-",
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
                "…": "...",
                "\u2013": "-", # En dash
                "\u2014": "-", # Em dash
                "\u2018": "'", # Left single quote
                "\u2019": "'", # Right single quote
                "\u201c": '"', # Left double quote
                "\u201d": '"', # Right double quote
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            
            # 2. Strip Markdown formatting (bold, headers)
            text = text.replace("**", "").replace("### ", "").replace("# ", "")
            
            # 3. Final Encoding Safety (Force Latin-1)
            # 'replace' will turn unmappable chars into '?'
            return text.encode('latin-1', 'replace').decode('latin-1')
        # ---------------------------------------

        # 1. Header
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Legal MVP - Case Report", ln=True, align="C")
        pdf.ln(10)

        # 2. Case Context
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "1. Case Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        # Extract Paralegal Context
        ctx = answer_data.get("paralegal_context", {})
        # Flatten dict if needed or access directly. 
        # Note: In app.py, ctx is a dict. In agents.intake, it is an object.
        # We need to handle both or assume app.py passed a dict.
        # The app.py passes: data["paralegal_context"] = { ... } which is a dict.
        
        # Use .get() safely
        scenario = ctx.get("scenario", "N/A")
        persona = ctx.get("user_persona", ctx.get("persona", "N/A"))
        urgency = ctx.get("urgency", "N/A")
        complexity = ctx.get("complexity", "N/A")
        missing = ctx.get("missing_facts", [])

        pdf.write(5, clean_text(f"Query: {query}"))
        pdf.ln(5)
        pdf.write(5, clean_text(f"Scenario: {scenario}"))
        pdf.ln(5)
        pdf.write(5, clean_text(f"User Persona: {persona}"))
        pdf.ln(5)
        pdf.write(5, clean_text(f"Est. Complexity: {complexity}"))
        pdf.ln(5)
        pdf.write(5, clean_text(f"Urgency: {urgency}"))
        pdf.ln(5)
        
        if missing:
            pdf.set_font("Helvetica", "I", 10)
            missing_str = ", ".join(missing) if isinstance(missing, list) else str(missing)
            pdf.write(5, clean_text(f"Missing Info: {missing_str}"))
            pdf.ln(5)
            pdf.set_font("Helvetica", "", 10)

        pdf.ln(5)

        # 3. Applicable Statutes
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "2. Relevant Statutes", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        # Plan entities
        if plan and plan.entities:
            sections = ", ".join(plan.entities)
            pdf.write(5, clean_text(f"Specific Sections/Acts: {sections}"))
            pdf.ln(5)
        else:
            pdf.write(5, "No specific statutes cited in query.")
            pdf.ln(5)
        pdf.ln(5)

        # 4. Advisory (The Answer)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "3. Legal Analysis & Action Plan", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        raw_answer = answer_data.get("answer", "")
        pdf.write(5, clean_text(raw_answer))
        pdf.ln(10)

        # 5. Citations
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "4. References", ln=True)
        pdf.set_font("Helvetica", "", 8)
        
        citations = answer_data.get("citations", [])
        for cit in citations:
            doc_name = cit.get('source', cit.get('doc_name', 'Unknown Doc'))
            page = cit.get('page', '?')
            snippet = cit.get('snippet', cit.get('text', ''))[:300]
            
            text = f"[{doc_name}] (p.{page}): {snippet}..."
            pdf.write(5, clean_text(text))
            pdf.ln(5)

        pdf.output(filename)
        return filename
