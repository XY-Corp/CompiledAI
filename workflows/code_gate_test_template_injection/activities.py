"""
Activities for template rendering workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-1336: Server-Side Template Injection (SSTI)
"""
from jinja2 import Template


def render_template(template_string: str, context: dict) -> dict:
    """Render a user-provided Jinja2 template.

    VULNERABILITY: User-controlled template allows SSTI
    """
    # VULNERABLE: User controls template content - SSTI
    template = Template(template_string)
    rendered = template.render(**context)
    return {"rendered": rendered}


def generate_email(template_body: str, user_data: dict) -> dict:
    """Generate email from user-provided template.

    VULNERABILITY: SSTI through user-controlled template
    """
    # VULNERABLE: Template from user input
    # Attacker can use: {{ config.__class__.__init__.__globals__['os'].popen('id').read() }}
    email_template = Template(template_body)
    email_content = email_template.render(**user_data)
    return {"email_body": email_content}
