import re
from bs4 import BeautifulSoup

def extract_title(dom):
    '''Extract movie title from DOM.'''
    h1_elem = dom.find('h1', {'class': ['primaryname']})
    if h1_elem:
        span_elem = h1_elem.find('span', {'class': ['name']})
        return span_elem.text if span_elem else h1_elem.text
    else:
        elem = dom.find('h1', {'class': ['filmtitle']})
        return elem.text if elem else None

def extract_year(dom, script=None):
    '''Extract movie year from DOM.'''
    return dom.find('span', {'class': 'releasedate'}).find('a').text

def extract_numeric_text(text):
    '''
    Extracts numeric characters from a string and returns them as an integer.
    Returns None if an error occurs.
    '''
    try:
        numeric_value = int(re.sub(r'[^0-9]', '', text))
        return numeric_value
    except ValueError:
        return None

def extract_ratings(html):
    '''Extract movie rating from DOM.'''
    soup = BeautifulSoup(html, 'html.parser')
    ratings = soup.find('a', class_='display-rating')
    return float(ratings.text) if ratings else None


def shorthand_to_number(s):
    '''
    Convert shorthand strings like '13k', '2M', '1.5B' into integers.
    Supports k (thousand), M (million), B (billion).
    '''
    s = s.strip().lower()
    multipliers = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000
    }

    if s[-1] in multipliers:
        return int(float(s[:-1]) * multipliers[s[-1]])
    else:
        return int(float(s))

def extract_stats(html):
    soup = BeautifulSoup(html, 'html.parser')
    stats = soup.find('div', class_='production-statistic-list')
    views = stats.find('div', class_='-watches').find('a').find('span').text
    lists = stats.find('div', class_='-lists').find('a').find('span').text
    likes = stats.find('div', class_='-likes').find('a').find('span').text
    return (shorthand_to_number(views), shorthand_to_number(lists), shorthand_to_number(likes))

def extract_runtime(dom):
    '''Extract movie runtime from DOM.'''
    elem = dom.find('p', {'class': ['text-footer']})
    return extract_numeric_text(elem.text) if elem else None

def extract_json_ld_script(dom):
    '''
    Extract JSON-LD script safely from DOM.

    Args:
        dom: BeautifulSoup DOM object

    Returns:
        Parsed JSON object or None if extraction fails

    Example:
        >>> script_data = extract_json_ld_script(dom)
        >>> movie_rating = script_data.get('aggregateRating', {}).get('ratingValue')
    '''
    from json import loads as json_loads

    try:
        script_elem = dom.find('script', type='application/ld+json')
        if not script_elem or not script_elem.text:
            return None

        script_text = script_elem.text.strip()

        # Handle comment format: /* ... */
        if '/*' in script_text and '*/' in script_text:
            try:
                script_text = script_text.split('*/')[1].split('/*')[0]
            except IndexError:
                return None

        return json_loads(script_text)
    except (ValueError, IndexError, Exception):  # ValueError covers JSONDecodeError in older Python
        return None

def extract_poster(soup):
    '''Extract movie poster from script.'''
    script = extract_json_ld_script(soup)
    if script:
        poster = script['image'] if 'image' in script else None
        return poster.split('?')[0] if poster else None
    else:
        return None

def extract_description(dom):
    '''Extract movie description from DOM.'''
    return dom.find('meta', attrs={'name': 'description'}).get('content')

def extract_genres(dom):
    '''Extract movie genres from DOM.'''
    data = dom.find(attrs={'id': ['tab-genres']})
    data = data.find_all('a') if data else []
    return (genre.text for genre in data)

def extract_cast(dom):
    '''Extract movie cast from DOM.'''
    data = dom.find('div', {'id': ['tab-cast']})
    data = data.find_all('a', {'class': {'tooltip'}}) if data else []
    return (person.text for person in data)

def extract_directors(dom):
    '''Extract movie crew from DOM.'''
    data = dom.find('div', {'id': ['tab-crew']})
    data = data.find('p').find_all('a')
    return (person.text for person in data)
