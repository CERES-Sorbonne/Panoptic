import dateparser
import pendulum
pendulum.set_locale('fr')

def parse_date(date: str):
    try:
        parsed = pendulum.from_format(date, 'DD/MM/YYYY HH:mm')
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        pass
    try:
        parsed = pendulum.from_format(date, 'DD/MM/YYYY HH:mm:ss')
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        pass
    try:
        parsed = pendulum.from_format(date, 'DD/MM/YYYY')
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        pass
    try:
        parsed = pendulum.from_format(date, 'YYYY')
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        pass
    try:
        parsed = pendulum.from_format(date, 'MM/YYYY')
        return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        pass
    # parsed = dateparser.parse(date,
    #                           date_formats=['%d/%m/%Y', '%d/%m/%Y %H:%M', '%d/%m/%Y %H:%M:%S'],
    #                           settings={'PREFER_DAY_OF_MONTH': 'first', 'PREFER_MONTH_OF_YEAR': 'first'})
    parsed = pendulum.parse(date)
    return parsed.strftime('%Y-%m-%dT%H:%M:%SZ')




# print(parse_date('2022'))
# print(parse_date('02/2022'))
# print(parse_date('03/2022'))
# print(parse_date('04/03/2022'))
# print(parse_date('04/03/2022 10:30'))
# print(parse_date('04/03/2022 10:30:55'))
# print(parse_date("2022-03-04T13:33:00.000Z"))
# print(parse_date("1995/07/04 10:33:22"))
