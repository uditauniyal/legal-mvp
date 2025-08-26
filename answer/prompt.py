from jinja2 import Template

SYS = """You are a legal assistant for Indian law.
Answer only using the numbered snippets provided below.
If missing info, reply exactly: "Insufficient information in provided sources."
Return ONLY valid JSON with keys: query, answer, citations.
In "answer", write in the user's language and include inline markers [1][2] that refer to the snippet numbers.
"citations" is an array of {source, page, snippet}. For the "snippet" value, use the full text from the corresponding numbered snippet.
Ensure 'page' is always an integer. If the snippet has no page, use page 0.
Do not include any text outside JSON.
"""

USR_TMPL = Template("""Question:
{{ q }}

Snippets:
{% for s in snippets -%}
[{{s.n}}] ({{s.source}}, p.{{s.page}}): {{s.snippet}}
{% endfor %}

Return JSON only.
""")

def build_messages(q, snippets):
    return [
        {"role": "system", "content": SYS},
        {"role": "user", "content": USR_TMPL.render(q=q, snippets=snippets)}
    ]