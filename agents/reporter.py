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

    def generate_report(self, query: str, plan: QueryPlan, answer_data: dict, filename: str = "report.pdf") -> str:
        pdf = PDF()
        pdf.add_page()
        
        # 1. Title Section
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Legal Case Analysis", ln=True, align='L')
        pdf.ln(5)

        # 2. Fact Pattern & Triage
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "1. Intake Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        ctx = plan.case_context
        if ctx:
            # Use write instead of multi_cell to avoid "horizontal space" errors
            pdf.write(5, f"Scenario: {ctx.scenario}")
            pdf.ln(5)
            pdf.write(5, f"Urgency: {ctx.urgency} | Complexity: {ctx.complexity}")
            pdf.ln(5)
            pdf.write(5, f"User Persona: {ctx.user_persona}")
            pdf.ln(5)
            pdf.write(5, f"Est. Financial Status: {ctx.financial_status}")
            pdf.ln(5)
            
            if ctx.missing_facts:
                pdf.set_font("Helvetica", "I", 10)
                pdf.write(5, f"Missing Info: {', '.join(ctx.missing_facts)}")
                pdf.ln(5)
                pdf.set_font("Helvetica", "", 10)

        pdf.ln(5)

        # 3. Legal Issues
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "2. Legal Issues & Domain", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        if ctx and ctx.legal_issues:
            for issue in ctx.legal_issues:
                pdf.write(5, f"- {issue}")
                pdf.ln(5)
        else:
            pdf.write(5, "- General Legal Inquiry")
            pdf.ln(5)
        
        if ctx:
             pdf.write(5, f"Domain: {ctx.predicted_legal_domain}")
             pdf.ln(5)
        pdf.ln(5)

        # 4. Applicable Statutes
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "3. Relevant Statutes", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        if plan.entities:
            sections = ", ".join(plan.entities)
            pdf.write(5, f"Specific Sections: {sections}")
            pdf.ln(5)
        else:
            pdf.write(5, "No specific statutes cited in query.")
            pdf.ln(5)
        pdf.ln(5)

        # 5. Analysis (The LLM Answer)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "4. Advisory & Action Plan", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        raw_answer = answer_data.get("answer", "")
        # Remove markdown chars for PDF
        clean_answer = raw_answer.replace("**", "").replace("### ", "").replace("# ", "")
        SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,;:!?'\"()[]/-_@#$%&*")
        # Aggressive cleaning for standard PDF font
        safe_answer = clean_answer.encode('latin-1', 'replace').decode('latin-1')
        
        # Use write for long text as it wraps
        pdf.write(5, safe_answer)
        pdf.ln(10)

        # 6. Citations
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "5. References", ln=True)
        pdf.set_font("Helvetica", "", 8)
        
        citations = answer_data.get("citations", [])
        for cit in citations:
            doc_name = cit.get('source', cit.get('doc_name', 'Unknown Doc'))
            page = cit.get('page', '?')
            snippet = cit.get('snippet', cit.get('text', ''))[:300]
            text = f"[{doc_name}] (p.{page}): {snippet}..."
            
            # Remove characters that aren't in Latin-1
            # FPDF (standard) only supports Latin-1 fonts by default
            safe_text = text.encode('latin-1', 'replace').decode('latin-1')
            
            try:
                # Use write + ln for citations too
                pdf.write(5, safe_text)
                pdf.ln(5) # Spacing between citations
            except Exception as e:
                print(f"Error rendering citation: {e}")
                pass

        pdf.output(filename)
        return filename
