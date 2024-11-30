from django import template
import re
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def highlight_query(text, query):
    """
    Highlights the search query within the text by wrapping it with <b></b> tags.
    """
    if not query:
        return text  # Return original text if no query is provided

    # Escape special characters in the query for use in regex
    escaped_query = re.escape(query)
    # Use regex to find case-insensitive matches of the query in the text
    pattern = re.compile(escaped_query, re.IGNORECASE)
    # Replace matches with the bolded version
    highlighted_text = pattern.sub(lambda match: f'<b>{match.group()}</b>', text)

    # Mark the result as safe HTML to prevent Django from escaping it
    return mark_safe(highlighted_text)
