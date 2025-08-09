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

@register.filter(name='status_badge_color')
def status_badge_color(status_text):
    text = status_text.lower() if status_text else ''
    if 'released' in text:
        return 'bg-green-900 text-green-200'
    if 'hold' in text or 'req' in text:
        return 'bg-yellow-900 text-yellow-200'
    if 'fail' in text or 'reject' in text:
        return 'bg-red-900 text-red-200'
    if 'sent' in text or 'in process' in text:
        return 'bg-blue-900 text-blue-200'
    return 'bg-gray-700 text-gray-300' # Default color