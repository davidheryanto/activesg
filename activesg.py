import argparse
import getpass
import json
import os
import pickle
import sys
import time
from base64 import b64encode
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, ConnectionError


class ActiveSG(object):
    def __init__(self):
        self.s = requests.session()
        # Set default headers for all requests
        self.s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'})

    def signin(self, email, pwd):
        # Retrieve public key and csrf
        r = self.s.get('https://members.myactivesg.com/auth')
        soup = BeautifulSoup(r.content, 'html.parser')
        pubkey = soup.select_one('input[name=rsapublickey]')['value']
        csrf = soup.select_one('input[name=_csrf]')['value']
        cipher = PKCS1_v1_5.new(RSA.importKey(pubkey))

        payload = {
            'email': email,
            'ecpassword': b64encode(cipher.encrypt(pwd.encode('ascii'))),
            '_csrf': csrf
        }
        r = self.s.post('https://members.myactivesg.com/auth/signin', data=payload)

        if r.status_code != 200:
            raise RequestException('Sign in failed. Wrong password?')

    def renew_cookies(self):
        self.s.get('https://members.myactivesg.com/auth')

    def check_slots(self, activity_id, venue_id, date):
        url = ('https://members.myactivesg.com/facilities/ajax/getTimeslots?activity_id={activity_id}'
               '&venue_id={venue_id}&date={date}&time_from={time}')
        params = {
            'activity_id': activity_id,
            'venue_id': venue_id,
            'date': date,
            'time': int(datetime.now().timestamp())
        }
        url = url.format(**params)

        # For Ajax requests of free courts, need to to use these headers
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

        # Sometimes, request is rejected or the remote server not responding, we need to repeat
        while True:
            try:
                r = self.s.get(url, headers=headers)
                break
            except ConnectionError:
                time.sleep(2)
                continue

        log = 'GET' if r.status_code == 200 else '  X GET'
        log += ' {} {}'.format(r.status_code, url)[:100]
        print(log)

        slots = None

        if r.status_code == 200:
            slots = defaultdict(list)
            soup = BeautifulSoup(r.content.decode('unicode_escape').replace(r'\/', '/')[1:-1], 'html.parser')

            for tag in soup.select('input[type="checkbox"]'):
                if not tag.has_attr('disabled'):
                    value = tag['value']
                    court, _, _, slot, _ = value.split(';')
                    slots[court].append(slot)

        return slots


def get_credentials():
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', default=os.getenv('ACTIVESG_EMAIL'))
    args = parser.parse_args()

    if args.user is None or len(args.user.strip()) <= 0:
        print('Please enter activesg username or put it in ACTIVESG_EMAIL env variable')
        sys.exit(1)
    user = args.user

    pwd = os.getenv('ACTIVESG_PASSWORD')
    if pwd is None or len(pwd.strip()) <= 0:
        pwd = getpass.getpass(prompt='Please enter activesg password: ')

    return user, pwd


if __name__ == '__main__':
    user, pwd = get_credentials()
    activesg = ActiveSG()
    activesg.signin(user, pwd)

    current_date = datetime.now() + timedelta(days=1)
    end_date = current_date + timedelta(days=12)

    if os.path.exists('html/availability.json'):
        with open('html/availability.json', 'r') as fp:
            availability = json.load(fp)
    else:
        availability = {}

    # Badminton only for now
    activity_id = 18
    with open('badminton_venue_ids.pkl', 'rb') as fp:
        venue_ids = pickle.load(fp)

    while current_date <= end_date:
        current_date_str = current_date.strftime('%Y-%m-%d')
        print('Checking courts for {}'.format(current_date_str))

        if current_date_str not in availability:
            availability[current_date_str] = {}

        for venue_id in venue_ids:
            slots = activesg.check_slots(activity_id, venue_id, current_date_str)
            if slots is not None and len(slots) > 0:
                if venue_id not in availability[current_date_str]:
                    availability[current_date_str][venue_id] = {}
                availability[current_date_str][venue_id] = slots
            # ActiveSG requires some delay between ajax queries
            time.sleep(3)

            with open('html/availability.json', 'w') as fp:
                json.dump(availability, fp)

        current_date += timedelta(days=1)
        # After some time, the cookie will expire, need to renew it.
        activesg.renew_cookies()

    # Clean up json data for days that already passed
    for d in list(availability.keys()):
        if datetime.strptime(d, '%Y-%m-%d') < datetime.now():
            del availability[d]

    with open('html/availability.json', 'w') as fp:
        json.dump(availability, fp)
