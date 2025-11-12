from django import template

register = template.Library()

@register.filter
def humanize_count(value):
    '''
    Converts large numbers to compact form:
      950  -> '950'
      1200 -> '1.2K'
      1500000 -> '1.5M'
      2300000000 -> '2.3B'
    '''
    try:
        num = int(value)
    except (TypeError, ValueError):
        return value

    if num >= 1_000_000_000:
        return f'{num / 1_000_000_000:.1f}B'
    elif num >= 1_000_000:
        return f'{num / 1_000_000:.1f}M'
    elif num >= 1_000:
        return f'{num / 1_000:.1f}K'
    else:
        return str(num)
