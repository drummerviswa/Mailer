import re
import socket
import smtplib
import subprocess

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
MX_CACHE = {}

def get_mx_records(domain):
    domain = domain.lower().strip()
    if domain in MX_CACHE:
        return MX_CACHE[domain]

    mx_list = []
    try:
        res = subprocess.run(
            ['nslookup', '-type=mx', domain],
            capture_output=True,
            text=True,
            timeout=4
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if 'mail exchanger =' in line:
                parts = line.split('mail exchanger =')
                if len(parts) == 2:
                    mx_host = parts[1].strip().rstrip('.')
                    mx_list.append(mx_host)
    except Exception:
        pass

    if not mx_list:
        try:
            socket.gethostbyname(domain)
            mx_list.append(domain)
        except Exception:
            pass

    MX_CACHE[domain] = mx_list
    return mx_list

def verify_email_deliverability(email):
    """
    Validates DNS MX and performs SMTP handshake verification.
    """
    if not email:
        return {
            "deliverability_status": "MISSING",
            "mx_record": "",
            "details": "No email provided"
        }

    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return {
            "deliverability_status": "INVALID_SYNTAX",
            "mx_record": "",
            "details": "Malformed email format"
        }

    try:
        domain = email.split('@')[1].lower()
    except Exception:
        return {
            "deliverability_status": "INVALID_SYNTAX",
            "mx_record": "",
            "details": "Invalid domain structure"
        }

    mx_hosts = get_mx_records(domain)
    if not mx_hosts:
        return {
            "deliverability_status": "NO_MX_RECORDS",
            "mx_record": "",
            "details": f"No active MX records for domain {domain}"
        }

    primary_mx = mx_hosts[0]
    status = "MX_ACTIVE"
    details = f"Active MX: {primary_mx}"

    try:
        server = smtplib.SMTP(timeout=3)
        server.connect(primary_mx, 25)
        server.helo('placement-verification.edu.in')
        server.mail('outreach-verify@placement-verification.edu.in')
        code, msg = server.rcpt(email)

        if code == 250:
            status = "DELIVERABLE"
            details = "Mailbox exists and accepts incoming outreach (Code 250)"
        elif code in (450, 451, 452):
            status = "GREYLISTED_ACTIVE"
            details = f"Server active (Greylisting/Rate-limit Code {code})"
        elif code >= 500:
            if "5.1.1" in str(msg) or "does not exist" in str(msg).lower():
                status = "REJECTED_DOES_NOT_EXIST"
            else:
                status = "REJECTED_OR_BLOCKED"
            details = f"Server response code {code}"
        else:
            status = "DELIVERABLE"
            details = f"Server accepted with code {code}"

        try:
            server.quit()
        except Exception:
            pass
    except smtplib.SMTPServerDisconnected:
        status = "MX_ACTIVE_NO_VRFY"
        details = f"MX active ({primary_mx}), handshake closed after EHLO"
    except (socket.timeout, TimeoutError):
        status = "MX_ACTIVE_TIMEOUT"
        details = f"MX active ({primary_mx}), port 25 timed out (firewalled)"
    except Exception as e:
        status = "MX_ACTIVE"
        details = f"MX active ({primary_mx})"

    return {
        "deliverability_status": status,
        "mx_record": primary_mx,
        "details": details
    }
