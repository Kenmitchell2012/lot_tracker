from django import template

register = template.Library()

@register.filter
def status_fill_color(status):
    return {
        "Tech Release": "bg-blue-600",
        "Final Labeling Release": "bg-pink-600",
        "Quality Release": "bg-cyan-600",
        "Done": "bg-green-600",
    }.get(status, "bg-gray-600")