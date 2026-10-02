import re

def parse_csv_line(line):
    return [item.strip() for item in line.split(',')]

def validate_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email))

def sanitize_html(html):
    # Extremely basic and flawed HTML sanitization for demonstration
    return re.sub(r'<[^>]*>', '', html)
