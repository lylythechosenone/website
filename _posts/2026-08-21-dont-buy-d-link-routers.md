---
title: Don't buy D-Link routers
tags:
    - security-research
    - bypass
    - RCE
---

Recently, for no particular reason, I decided I would try to find bugs in [the latest firmware](https://legacyfiles.us.dlink.com/DIR-1260/REVA/FIRMWARE/DIR-1260_REVA_FIRMWARE_v1.02B06_HOTFIX.zip) for a D-Link DIR-1260 router. It's a fairly recent AC1200 router, marketed towards home users. Though it's [considered EOS](https://support.dlink.com/ProductInfo.aspx?m=DIR-1260#:~:text=January%2031%2C%202024%20NOTICE%20%2D%20This%20hardware%20revision%20will%20no%20longer%20receive%20firmware%20updates%20after%20the%20End%20of%20Support%20date%0A(EoS)%3A%20March%2031%2C%202024.) by D-Link, you can still buy one new on [Amazon](https://a.co/d/0g19nSJ1). (That's not an affiliate link, I swear; I very much don't want you to buy one.)

# TL;DR
Through my research, I found a chain that gave me unauthenticated RCE as root. You can find the PoC [here](https://github.com/lylythechosenone/website/blob/main/assets/pocs/dir1260_poc.py). Keep reading to understand how it happened.

# Getting in
After a first `binwalk -E` on the extracted firmware zip, I was greeted by this delightful graph:

![Entropy graph showing consistently high entropy for the entire binary](../assets/images/DIR-1260V2_V102B06_Beta.bin.png)

For those unfamiliar with reading entropy graphs, that yellow line going all the way across the top is showing that throughout the file, entropy is consistently very high. This tells me that the binary is encrypted, and I won't be able to extract it directly.

Luckily, [0xricksanchez has already done the work for me](https://github.com/0xricksanchez/dlink-decrypt). Apparently, no information is required other than the encrypted firmware itself. It also seems likely that D-Link uses this same firmware encryption scheme across their entire lineup. For more details on how it works, read [0xricksanchez's blog posts](https://archive.0x00sec.org/t/breaking-the-d-link-dir3060-firmware-encryption-recon-part-1/21943).

After a quick run of 0xricksanchez's script, I had a nice `dec.bin` I could actually run `binwalk` on, yielding me a beautiful `squashfs-root`:
```
├── bin
├── dev
├── etc
├── lib
├── media
├── mnt
├── overlay
├── proc
├── rom
├── root
├── sbin
├── sys
├── tmp
├── usr
├── var -> /tmp
└── www
```

# Poking around
I started my exploration in `etc`, finding a few points of interest:

- `openwrt_release`, which told me that this firmware is based on OpenWrt Chaos Calmer 15.05.1, and built for ramips/mt7621
- `lighttpd/lighttpd.conf`, which told me that lighttpd (almost certainly the router's main web server) is configured to use a specific FastCGI binary, `/usr/sbin/prog.cgi`, to handle everything that isn't a static HTML file

So I opened up `prog.cgi` in Binary Ninja and gathered my bearings. (Reader: this is where the fun starts.)

Because this was a release build, none of the symbols had names, but one string caught my eye immediately: `websOpenServer`. *`webs`*? That's the function prefix for GoAhead web server, an embeddable web server that's been in maintenance mode for over a decade; not to mention that this router *already has a web server*: lighttpd. What is GoAhead doing here?

It turns out that D-Link is cannibalizing GoAhead 2.x (over 2 decades old) as a request handler for their FastCGI binary, presumably because they just yanked most of the code from an older device and ported only the socket part. Instead of GoAhead's typical web server socket, this monstrosity simply feeds whatever FastCGI gave it directly into GoAhead's `wp`.

Luckily, this gave me easy access to the three important handlers:

- one at `/`, which contained a nice little `syslog` informing me that it was called `websSecurityHandler`
- one at `/HNAP1`, the HNAP (SOAP) endpoint, with another little `syslog` calling it `websFormHandler`
- one at `/cgi-bin`, with a `syslog` calling it `websCgiHandler`

# Login bypass

I decided to start with `websSecurityHandler`, since I was skeptical of the name: security and IoT devices don't generally go together. Checking inside, it took me to `websAuthHandler`, which simply checks the HTTP path, and if it's either `/HNAP1/Login` or `/HNAP1/Logout`, checks the SOAP body and routes to the corresponding handler based on the SOAP field `/Login/Action`.

I jumped right to the `login` path, and struck gold:
```c
// First, compute the correct HMAC given a challenge
struct HMAC_CTX hmac_ctx;
HMAC_CTX_init(&hmac_ctx);
HMAC_Init_ex(&hmac_ctx, correct_password, strlen(correct_password), EVP_md5(), 0);
HMAC_Update(&hmac_ctx, challenge, strlen(challenge));
HMAC_Final(&hmac_ctx, &hmac_out, &hmac_len);
HMAC_CTX_cleanup(&hmac_ctx);

// Convert the HMAC to hex
for (int i = 0; i != hmac_len; i += 1)
    sprintf(&hmac_hex + (i << 1), "%02x", (uint32_t)hmac_out[i]);

capitalize(&hmac_hex, 0x200);

// Compare the correct HMAC to my provided HMAC, *using my length*
int compare_hmac = strncmp(&hmac_hex, attacker_password, strlen(attacker_password));
```
The code comes so close to doing proper HMAC-based authentication, but falls short right on the last line. Because they used strncmp with an attacker-controlled length, I get to choose *exactly how much of the HMAC to compare*. That means that I can pass in an empty string and be allowed in.

This vulnerability is both funny and tragic to me because it's so easy to avoid:

- the author could have used the correct HMAC's length instead
- the author could have checked my HMAC's length before comparing the strings
- the author could have just used `strcmp` instead of `strncmp`

Any of these would have been correct. None were used.

# Command injection
Now that I had authentication covered, I looked through calls to `system` to find any that were in the HNAP handlers. Luckily, I found plenty, and two in particular were easily injectable: both `SetNTPServerSettings` and `SetNetworkTomographySettings` had unescaped `sprintf`s into `system` calls where I controlled one of the format arguments directly.

# PoC
I threw together a PoC that did the two-step HNAP login with an empty password, then attempted a command injection. Unfortunately, it didn't work. Upon further inspection of `websAuthHandler`, I realized why: `websAuthHandler` actually checks all login-protected endpoints for a specific `HNAP_AUTH` header.

# Login bypass, part 2
The `HNAP_AUTH` header was an HMAC just like before, except that this one incorporates the current time. However, I had an inkling about it which turned out to be exactly correct: `strncmp(&correct_hmac, &attacker_hmac, strlen(&attacker_hmac))`. Just like the login endpoint, this one was vulnerable to length manipulation.

Unfortunately, I couldn't just pass an empty string into the HNAP_AUTH header, because lighttpd would just filter it out. I had to think of an alternative. Let's see; what do I know?

- I'm expected to pass in an HMAC based on the user's password and the current time
- the HMAC should be hex-encoded with capital letters
- I only have to compare as much of the HMAC as I want to

Are you thinking what I was thinking?

I need to pass in *something*, but that doesn't mean I need to pass in the whole HMAC; I can just pass in a single character. I know that the character is one of 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, A, B, C, D, E, or F. If I just guess a random one of those characters, **I have a 6.25% chance of getting it right**.

# PoC, part 2
Finally, I had a full chain:

1. Send a SOAP request to `/HNAP1` with action `Login` and `/Login/Action` `request` to get my challenge.
2. Send another SOAP request to `/HNAP1` with action `Login`, but this time with `/Login/Action` `login`. Give it an empty password. This one actually logs me in.
3. Send a final SOAP request to `/HNAP1`, with either of the command injection actions this time. Put a single random character in `[0-9A-Z]` in the HNAP_AUTH header. If it fails, go back to step 1; if it succeeds, you won!

Look [here](https://github.com/lylythechosenone/website/blob/main/assets/pocs/dir1260_poc.py) for the full Python PoC.

# What's next
This isn't D-Link's first RCE, nor is it even their first on this model. In fact, the version I tested was specifically released to mitigate [an RCE bug reported by Exodus](https://blog.exodusintel.com/2022/05/11/d-link-dir-1260-getdevicesettings-pre-auth-command-injection-vulnerability/). Multiple other CVEs still apply to this exact model with this exact firmware, and very similar CVEs have been found on other models in D-Link's lineup.

The bottom line is this: don't buy D-Link routers. Inevitably, you will end up with an EOS router full of CVEs just waiting to be exploited. If you already have a D-Link router, get rid of it; and if you can't do that, make sure that its web server is not open to the internet, and disconnect as many critical devices from it as you can.

# A quick note on other routers
D-Link is potentially the worst example, but that doesn't mean it's alone in this field. Routers (and IoT devices in general) are plagued by vulnerabilities and backdoors. The firmware for them is often written by hardware people without much cybersecurity experience.

If you want a good, secure router, your best shot is studying up on cybersecurity, and running OpenWRT yourself on your own hardware.
