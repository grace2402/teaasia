#!/usr/bin/env python3

import os
import requests
import json
import argparse
import csv
from dotenv import load_dotenv
from datetime import datetime

MOCK_API = os.getenv('MOCK_API', 'true').lower() in ['1','true','yes']

def api_req(method, api_path, json_body=None):
    url = 'https://api.iijmobile.jp'
    load_dotenv()
    token = os.getenv('IIJ_TOKEN')
    sa = os.getenv('SERVICE_ACCOUNT')

    headers = {
        'X-IIJ-Mobile-Token': token,
        'Content-Type': 'application/json;charset=UTF-8',
        'X-IIJ-Mobile-Administrator': sa
    }

    full_url = f'{url}{api_path}'

    # 印出完整的 Request 資訊
    print('-' * 80)
    kwargs = {'json': json_body} if json_body is not None else {}
    req = requests.Request(method, full_url, headers=headers, **kwargs)
    prepared = req.prepare()

    # 印出 Method 與 URL
    print(f'{prepared.method} {prepared.url}')
    print('-' * 80)

    # 印出 Headers
    for k, v in prepared.headers.items():
        print(f'{k}: {v}')
    print('-' * 80)

    # 印出 Body (若有)
    if prepared.body:
        try:
            body_json = json.loads(prepared.body)
            print(json.dumps(body_json, indent=2, ensure_ascii=False))
        except (ValueError, TypeError):
            # 若 body 不是 json，直接印出
            print(prepared.body)
    else:
        print('<no body>')
    print('-' * 80)

    # 發出 Request
    session = requests.Session()
    response = session.send(prepared)
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

    return response.json()  # 或 response.tex

def api_post(iccid, json_body=None):
    return api_req('POST', f'/v1/subscribers/kiw87103139/{iccid}', json_body)

# convert date_obj to YYYYmmdd
def date2str(date=None):
    if date is None:
        date_obj = datetime.now()
    elif isinstance(date, str):
        date_obj = datetime.strptime(date, '%Y%m%d')
    elif isinstance(date, datetime):
        date_obj = date
    else:
        raise ValueError('date has to be datetime object or YYYYmmdd')
    return date_obj.strftime('%Y%m%d')

def iij_query(**keywords):
    allowed_keys = {
        'activated_date', 'subscriber', 'status', 'trigger', 'sms', 'cancel_date', 'sim_type',
        'roaming_plan', 'start_date', 'subscriber', 'iccid', 'puk', 'sim_type', 'imei', 'imsi',
        'msisdn', 'puk', 'roaming_plan', 'sim_type', 'start_date', 'subscriber', 'status',
        'trigger', 'sms', 'roaming_plan', 'sim_type', 'start_date', 'subscriber'
    }

    invalid = set(keywords) - allowed_keys
    if invalid:
        raise ValueError(f"Invalid keyword: {', '.join(invalid)}")

    query_str = '&'.join(f'{k}={v}' for k, v in keywords.items())
    return api_req('GET', f'/v1/subscribers/kiw87103139?{query_str}')

def iij_activate(iccid, date=None):
    if MOCK_API:
        print(f"[MOCK API] activate  ➜  ICCID={iccid}, date={date}")
        return {"mock": "activate_success", "iccid": iccid}
    date_str = date2str(date)
    return api_post(iccid, {"reserved_activated_date": date_str})

def iij_suspend(iccid, date=None):
    if MOCK_API:
        print(f"[MOCK API] suspend   ➜  ICCID={iccid}, date={date}")
        return {"mock": "suspend_success", "iccid": iccid}
    date_str = date2str(date)
    return api_post(iccid, {"status": "suspend", "reserved_date": date_str})

def iij_resume(iccid, date=None):
    date_str = date2str(date)
    return api_post(iccid, {"status": "active", "reserved_date": date_str})

def iij_cancel(iccid, date=None):
    if MOCK_API:
        print(f"[MOCK API] cancel    ➜  ICCID={iccid}, date={date}")
        return {"mock": "cancel_success", "iccid": iccid}
    date_str = date2str(date)
    return api_post(iccid, {"cancel_date": date_str})

# iij_memo("12345678", memo1='aaa', memo2='bbb', memo3='ccc')
def iij_memo(iccid, **memos):
    # Keys must be "memo1", "memo2", or "memo3"
    if not memos:
        raise ValueError('iij_memo: memos needs at least one argument')
    allowed_keys = {'memo1', 'memo2', 'memo3'}
    invalid_keys = set(memos) - allowed_keys
    if invalid_keys:
        raise ValueError(f"Wrong parameters: {', '.join(invalid_keys)}")
    memo_json = {"memo": memos}
    return api_post(iccid, memo_json)

def iij_oplogs(iccid, start_date, end_date=None):
    # GET /v1/opelogs/{management}/{subscriber}?start=YYYYMMDD&end=YYYYMMDD
    dict_date = {
        "start": date2str(start_date),
        "end": date2str(end_date)
    }
    query_str = '&'.join(f'{k}={v}' for k, v in dict_date.items())
    return api_req('GET', f'/v1/opelogs/kiw87103139/{iccid}?{query_str}')

def read_iccid_csv(filename):
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        rows = list(reader)
        if not rows:
            return []

        # Check if the csv file has header row.
        header = rows[0]
        if 'ICCID' in header:
            iccid_idx = header.index('ICCID')
            return [row[iccid_idx] for row in rows[1:] if len(row) > iccid_idx]
        else:
            # If there's no header, it takes row[0] as iccid.
            return [row[0] for row in rows]

def get_iccid_list(iccid_list, iccid_file):
    iccids = iccid_list or []
    if iccid_file:
        iccids += read_iccid_csv(iccid_file)
    if not iccids:
        raise ValueError("Please provide at least 1 iccid either from -i or -f")
    return list(set(iccids)) # Remove duplicated iccids


def cli_main():
    parser = argparse.ArgumentParser(description='IIJ SIM Managment Tool')
    subparsers = parser.add_subparsers(dest='action', required=True)

    # activate
    parser_activate = subparsers.add_parser('activate', help='Activate SIM')
    parser_activate.add_argument('-i', '--iccid', nargs="+", required=True, help='ICCID list')
    parser_activate.add_argument('-f', '--iccid-file', type=str, help='Read ICCID from a csv file')
    parser_activate.add_argument('-d', '--date', required=True, help='Date YYYYMMDD')

    # suspend
    parser_suspend = subparsers.add_parser('suspend', help='Suspend SIM')
    parser_suspend.add_argument('-i', '--iccid', nargs="+", required=True, help='ICCID list')
    parser_suspend.add_argument('-f', '--iccid-file', type=str, help='Read ICCID from a csv file')
    parser_suspend.add_argument('-d', '--date', help='Date YYYYMMDD')

    # resume
    parser_resume = subparsers.add_parser('resume', help='Resume SIM')
    parser_resume.add_argument('-i', '--iccid', nargs="+", required=True, help='ICCID lise')
    parser_resume.add_argument('-f', '--iccid-file', type=str, help='Read ICCID from a csv file')
    parser_resume.add_argument('-d', '--date', help='Date YYYYMMDD')

    # cancel
    parser_cancel = subparsers.add_parser('cancel', help='Cancel SIM')
    parser_cancel.add_argument('-i', '--iccid', nargs="+", required=True, help='ICCID list')
    parser_cancel.add_argument('-f', '--iccid-file', type=str, help='Read ICCID from a csv file')
    parser_cancel.add_argument('-d', '--date', help='Date YYYYMMDD')

    # query
    p_query = subparsers.add_parser(
        'query',
        help='Query SIM information',
        formatter_class=argparse.RawTextHelpFormatter
    )
    p_query.add_argument(
        'keywords',
        nargs="+",
        metavar='KEY=VALUE',
        help='KEY only accepts the following,\n'
             'activated_date, subscriber, status, trigger, sms, cancel_date, sim_type,\n'
             'roaming_plan, start_date, subscriber, iccid, puk, sim_type, imei, imsi,\n'
             'msisdn, puk, roaming_plan, sim_type, start_date, subscriber, status,\n'
             'trigger, sms, roaming_plan, sim_type, start_date, subscriber\n'
             'Example: iccid=8981030000012624000 memo=ART'
    )

    # memo
    p_memo = subparsers.add_parser(
        'memo',
        help='Set memo',
        formatter_class=argparse.RawTextHelpFormatter
    )
    p_memo.add_argument('-i', '--iccid', required=True, help='ICCID')
    p_memo.add_argument(
        '-m',
        '--memo',
        nargs='+',
        required=True,
        metavar='KEY=VALUE',
        help='KEY only accepts memo1, memo2, memo3.\n'
             'Example: --memo memo1=111, memo2=222'
    )

    # oplogs
    parser_cancel = subparsers.add_parser('oplogs', help='Get operation logs')
    parser_cancel.add_argument('-i', '--iccid', required=True, help='ICCID list')
    parser_cancel.add_argument('start_date', help='Start date(YYYYMMDD), it has to be within 6 months')
    parser_cancel.add_argument('end_date', nargs="?", default=date2str(), help='End date(YYYYMMDD), default is today')

    args = parser.parse_args()

    if args.action == 'activate':
        iccids = get_iccid_list(args.iccid, args.iccid_file)
        for iccid in iccids:
            iij_activate(iccid, args.date)
    elif args.action == 'suspend':
        iccids = get_iccid_list(args.iccid, args.iccid_file)
        for iccid in iccids:
            iij_suspend(iccid, args.date)
    elif args.action == 'resume':
        iccids = get_iccid_list(args.iccid, args.iccid_file)
        for iccid in iccids:
            iij_resume(iccid, args.date)
    elif args.action == 'cancel':
        iccids = get_iccid_list(args.iccid, args.iccid_file)
        for iccid in iccids:
            iij_cancel(iccid, args.date)
    elif args.action == 'query':
        kw = dict(item.split('=', 1) for item in args.keywords)
        iij_query(**kw)
    elif args.action == 'memo':
        memo_dict = dict(item.split('=', 1) for item in args.memo)
        iij_memo(args.iccid, **memo_dict)
    elif args.action == 'oplogs':
        iij_oplogs(args.iccid, args.start_date, args.end_date)

if __name__ == "__main__":
    cli_main() 
