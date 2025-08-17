"""
Template filters for percentage calculations and formatting.
"""

from django import template

register = template.Library()


@register.filter
def smart_percentage(value, total):
    """
    Calculate percentage with smart formatting.
    Returns formatted percentage string with appropriate decimal places.
    """
    if not total or total == 0:
        return "0%"
    
    try:
        value = float(value) if value is not None else 0
        total = float(total)
        percentage = (value / total) * 100
        
        if percentage == 0:
            return "0%"
        elif percentage < 0.1:
            return "<0.1%"
        elif percentage < 1:
            return f"{percentage:.1f}%"
        elif percentage == 100:
            return "100%"
        else:
            return f"{percentage:.0f}%"
            
    except (ValueError, TypeError, ZeroDivisionError):
        return "0%"


@register.filter
def percentage(value, total):
    """
    Calculate simple percentage.
    Returns float value for calculations.
    """
    if not total or total == 0:
        return 0
    
    try:
        value = float(value) if value is not None else 0
        total = float(total)
        return (value / total) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def format_percentage(value, decimal_places=1):
    """
    Format a percentage value with specified decimal places.
    """
    if value is None:
        return "N/A"
    
    try:
        value = float(value)
        if decimal_places == 0:
            return f"{value:.0f}%"
        else:
            return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "N/A"


@register.filter
def progress_bar_width(value, total):
    """
    Calculate width for progress bar based on percentage.
    Returns percentage as integer for CSS width.
    """
    if not total or total == 0:
        return 0
    
    try:
        value = float(value) if value is not None else 0
        total = float(total)
        width = (value / total) * 100
        return min(100, max(0, int(width)))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def completion_status(value, total):
    """
    Return completion status class based on percentage.
    Useful for styling progress indicators.
    """
    percentage_val = percentage(value, total)
    
    if percentage_val >= 90:
        return "success"
    elif percentage_val >= 70:
        return "warning"
    elif percentage_val >= 30:
        return "info"
    else:
        return "danger"
