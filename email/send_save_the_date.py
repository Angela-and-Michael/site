#!/usr/bin/env python3
"""Send the Save the Date email to everyone in guest-list.csv from an iCloud Mail account.

Each guest gets their own email in their language (EN, ES or IT), addressed with their first name.

  python3 send_save_the_date.py                         # dry run: shows who gets what, sends nothing
  python3 send_save_the_date.py --test you@icloud.com   # sends one email per language to you
  python3 send_save_the_date.py --send                  # sends to the whole guest list

Sign-in uses an app-specific password (appleid.apple.com > Sign-In and Security > App-Specific Passwords),
never your Apple Account password. The script asks for it, or reads ICLOUD_APP_PASSWORD if set.
Already-sent guests are recorded in sent-log.csv and skipped on later runs, so a stopped run can be resumed.
"""
import argparse
import csv
import getpass
import html
import os
import re
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

HERE = os.path.dirname(os.path.abspath(__file__))
SMTP_HOST, SMTP_PORT = 'smtp.mail.me.com', 587   # iCloud Mail, STARTTLS
SENDER_NAME = 'Angela & Michael'
LOG_PATH = os.path.join(HERE, 'sent-log.csv')

# Greeting with a first name, and the neutral one used when a guest has no first name in the list.
GREETING = {
    'en': ('Dear {{First Name}},', 'Dear friends,'),
    'es': ('Hola, {{First Name}}:', '¡Hola!'),
    'it': ('Ciao {{First Name}},', 'Ciao!'),
}
# Plain-text versions, shown by email apps that don't display HTML (and they help with spam filters).
TEXT = {
    'en': ('{greeting}\n\n'
           'We would love for you to save the date for our wedding on Friday, June 11, 2027, in Ontario, Canada.\n\n'
           'Visit our website: https://angelaandmichael.com/\n\n'
           'Formal invitation to follow.\n\n'
           'With love,\nAngela & Michael\n'),
    'es': ('{greeting}\n\n'
           'Nos encantaría que reserven la fecha de nuestra boda: viernes 11 de junio de 2027, en Ontario, Canadá.\n\n'
           'Visiten nuestra página: https://angelaandmichael.com/es\n\n'
           'La invitación formal llegará pronto.\n\n'
           'Con cariño,\nAngela y Michael\n'),
    'it': ('{greeting}\n\n'
           'Segnate la data del nostro matrimonio: venerdì 11 giugno 2027, in Ontario, Canada.\n\n'
           'Visitate il nostro sito: https://angelaandmichael.com/it\n\n'
           'Seguirà l’invito ufficiale.\n\n'
           'Con affetto,\nAngela e Michael\n'),
}
LANGS = {'en': 'en', 'english': 'en', 'es': 'es', 'spanish': 'es', 'español': 'es', 'espanol': 'es',
         'it': 'it', 'italian': 'it', 'italiano': 'it', '': 'en'}
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def load_templates():
    """Reads the three HTML emails; each one's <title> is its subject line."""
    templates = {}
    for lang in TEXT:
        path = os.path.join(HERE, 'save-the-date-email-%s.html' % lang)
        with open(path, encoding='utf-8') as f:
            body = f.read()
        subject = html.unescape(re.search(r'<title>(.*?)</title>', body, re.S).group(1).strip())
        templates[lang] = (subject, body)
    return templates


def load_guests(path):
    """Returns (guests, problems). Excel-saved CSVs (with a byte-order mark) are fine."""
    guests, problems, seen = [], [], set()
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        need = {'First Name', 'Email Address', 'Language'}
        missing = need - set(reader.fieldnames or [])
        if missing:
            sys.exit('guest-list.csv is missing column(s): %s' % ', '.join(sorted(missing)))
        for line, row in enumerate(reader, start=2):
            name = (row.get('First Name') or '').strip()
            email = (row.get('Email Address') or '').strip()
            lang = LANGS.get((row.get('Language') or '').strip().lower())
            if not email and not name:
                continue
            if not EMAIL_RE.match(email):
                problems.append('row %d: "%s" is not a valid email address' % (line, email))
                continue
            if lang is None:
                problems.append('row %d: language "%s" should be EN, ES or IT' % (line, row.get('Language')))
                continue
            if email.lower() in seen:
                problems.append('row %d: %s appears more than once (only the first is used)' % (line, email))
                continue
            seen.add(email.lower())
            guests.append({'name': name, 'email': email, 'lang': lang})
    return guests, problems


def already_sent():
    if not os.path.exists(LOG_PATH):
        return set()
    with open(LOG_PATH, encoding='utf-8', newline='') as f:
        return {row['email'].lower() for row in csv.DictReader(f)}


def log_sent(guest):
    new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, 'a', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['email', 'first_name', 'language', 'sent_at'])
        w.writerow([guest['email'], guest['name'], guest['lang'].upper(), datetime.now().isoformat(timespec='seconds')])


def build_message(guest, templates, sender):
    subject, body = templates[guest['lang']]
    named, neutral = GREETING[guest['lang']]
    if guest['name']:
        greeting_text = named.replace('{{First Name}}', guest['name'])
        body = body.replace('{{First Name}}', html.escape(guest['name']))
    else:
        greeting_text = neutral
        assert named in body, 'greeting not found in %s template' % guest['lang']
        body = body.replace(named, html.escape(neutral))
    msg = EmailMessage()
    msg['From'] = formataddr((SENDER_NAME, sender))
    msg['To'] = formataddr((guest['name'], guest['email'])) if guest['name'] else guest['email']
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=sender.split('@')[1])
    msg.set_content(TEXT[guest['lang']].format(greeting=greeting_text))
    msg.add_alternative(body, subtype='html')
    return msg


def main():
    ap = argparse.ArgumentParser(description='Send the Save the Date email from iCloud Mail.')
    ap.add_argument('--guests', default=os.path.join(HERE, 'guest-list.csv'), help='CSV with First Name, Email Address, Language')
    ap.add_argument('--from', dest='sender', default=os.environ.get('ICLOUD_EMAIL'),
                    help='your iCloud email address (or set ICLOUD_EMAIL)')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--send', action='store_true', help='actually send to the guest list')
    mode.add_argument('--test', metavar='ADDRESS', help='send one email per language to ADDRESS only')
    ap.add_argument('--delay', type=float, default=5, help='seconds between emails (default 5, keeps iCloud happy)')
    args = ap.parse_args()

    templates = load_templates()
    guests, problems = load_guests(args.guests)
    for p in problems:
        print('  ! ' + p)

    if args.test:
        recipients = [{'name': 'Test', 'email': args.test, 'lang': lang} for lang in TEXT]
    else:
        done = already_sent()
        recipients = [g for g in guests if g['email'].lower() not in done]
        skipped = len(guests) - len(recipients)
        counts = {l: sum(g['lang'] == l for g in recipients) for l in TEXT}
        print('%d guest(s) to email: %d English, %d Spanish, %d Italian%s' % (
            len(recipients), counts['en'], counts['es'], counts['it'],
            ' (%d already sent, skipped)' % skipped if skipped else ''))
        for g in recipients:
            print('  %-2s  %-24s %s' % (g['lang'].upper(), g['name'] or '(no first name)', g['email']))
        if not args.send:
            print('\nDry run only: nothing was sent. Use --test you@icloud.com to try it, then --send.')
            return

    if not recipients:
        print('Nothing to send.')
        return
    if not args.sender:
        sys.exit('Add --from your@icloud.com (the iCloud address to send from).')
    if args.send:
        mins = len(recipients) * args.delay / 60
        answer = input('\nSend %d email(s) from %s now (about %.0f min)? Type "send" to confirm: '
                       % (len(recipients), args.sender, max(1, mins)))
        if answer.strip().lower() != 'send':
            print('Cancelled; nothing was sent.')
            return

    password = os.environ.get('ICLOUD_APP_PASSWORD') or getpass.getpass('iCloud app-specific password: ')
    sent = 0
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(args.sender, password)
        for i, guest in enumerate(recipients, start=1):
            try:
                smtp.send_message(build_message(guest, templates, args.sender))
            except smtplib.SMTPException as e:
                print('  x %s: %s (stopping; run again to resume from here)' % (guest['email'], e))
                break
            sent += 1
            if not args.test:
                log_sent(guest)
            print('  ✓ %d/%d  %s  %s' % (i, len(recipients), guest['lang'].upper(), guest['email']))
            if i < len(recipients):
                time.sleep(args.delay)
    print('\nSent %d of %d.%s' % (sent, len(recipients), '' if args.test else ' Log: ' + LOG_PATH))


if __name__ == '__main__':
    main()
