import logging

import pendulum
pendulum.set_locale('fr')

def parse_date(date: str):
    formats = [
        'DD/MM/YYYY HH:mm',
        'DD/MM/YYYY HH:mm:ss',
        'DD/MM/YYYY',
        'YYYY',
        'MM/YYYY',
        "DD/MM/YY-HH:mm"
    ]

    for fmt in formats:
        try:
            parsed = pendulum.from_format(date, fmt)
            return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            pass
    try:
        parsed = pendulum.from_timestamp(int(date))
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        pass
    # parsed = dateparser.parse(date,
    #                           date_formats=['%d/%m/%Y', '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S'],
    #                           settings={'PREFER_DAY_OF_MONTH': 'first', 'PREFER_MONTH_OF_YEAR': 'first'})
    try:
        parsed = pendulum.parse(date)
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        logging.getLogger().warning(f'Could not parse date: {date}')
        return ""



# print(parse_date('2022'))
# print(parse_date('02/2022'))
# print(parse_date('03/2022'))
# print(parse_date('04/03/2022'))
# print(parse_date('04/03/2022 10:30'))
# print(parse_date('04/03/2022 10:30:55'))
# print(parse_date("2022-03-04T13:33:00.000Z"))
# print(parse_date("1995/07/04 10:33:22"))
