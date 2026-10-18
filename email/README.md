# Sending the Save the Date

Everything here sends one personal email per guest from your iCloud address, in the guest's language.

| File | What it is |
|---|---|
| `guest-list.csv` | Your guest list: `First Name`, `Email Address`, `Language` (EN, ES or IT; blank means EN) |
| `save-the-date-email-en.html` / `-es` / `-it` | The emails. The card image links to `angelaandmichael.com`, `/es` or `/it` |
| `send_save_the_date.py` | Sends them. Needs only the Python that comes with macOS |
| `sent-log.csv` | Created as emails go out; anyone listed here is skipped next time |

## Before you send

1. **The card images must be live.** Push the site so `https://angelaandmichael.com/images/email/save-the-date-en.jpg` (and `-es`, `-it`) open in a browser.
2. **Make an app-specific password** for this script: go to appleid.apple.com, then Sign-In and Security, then App-Specific Passwords, and create one named "Save the Date". You'll paste it when the script asks. It is not your Apple Account password, and you can revoke it afterwards.
3. **Fill in `guest-list.csv`.** You can edit it in Numbers or Excel; export or save as CSV. For couples, put both names in First Name (for example `Sam & Alex`). Leave First Name empty to use a general greeting.

## Send

Run these from Terminal:

```bash
cd ~/Desktop/wedding/email
```

See who gets what (sends nothing):

```bash
python3 send_save_the_date.py
```

Send yourself one email in each language to check them:

```bash
python3 send_save_the_date.py --from you@icloud.com --test you@icloud.com
```

Send to everyone (it asks you to type `send` to confirm):

```bash
python3 send_save_the_date.py --from you@icloud.com --send
```

Replace `you@icloud.com` with the iCloud address you're sending from.

## Good to know

- It waits 5 seconds between emails, which stays well inside iCloud's sending limits. 150 guests takes about 13 minutes.
- If it stops partway (Wi-Fi drops, for example), run the same `--send` command again; it skips everyone in `sent-log.csv`.
- Emails sent this way don't appear in your iCloud Sent folder. `sent-log.csv` is your record of who got it and when.
- Replies come back to your iCloud inbox as normal.
