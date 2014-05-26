from datetime import datetime


def parse_date(line):
    parsed = datetime.strptime(line.replace('th', ''), "%B %d, %Y")
    return parsed.strftime("%Y-%m-%d")
