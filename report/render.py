from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# Set up the Jinja2 environment and load the template
env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")))
tpl = env.get_template("answer.html.j2")

def render_html(answer_json: dict) -> str:
    """
    Render the HTML report from the LLM's JSON output.
    
    :param answer_json: Dict containing keys 'query', 'answer', 'citations'
    :return: Rendered HTML string
    """
    return tpl.render(**answer_json)
