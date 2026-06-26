"""HTML e-mail templates for RackForge (NL / EN)."""
from __future__ import annotations

import re

from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

TOKEN_VALID_HOURS = 2

LOGO_CID = "rackforge-logo"
LOGO_SEARCH_PATHS = (
    Path("/var/www/html/icons/rackforge-avatar.png"),
    Path("/home/stef/rackforge/icons/rackforge-avatar.png"),
    Path(__file__).resolve().parent.parent / "icons" / "rackforge-avatar.png",
)


def normalize_lang(lang: str | None) -> str:
    value = (lang or "nl").strip().lower()
    return value if value in ("nl", "en") else "nl"


def token_valid_for_text(lang: str, *, code: bool = False) -> str:
    lng = normalize_lang(lang)
    hours = TOKEN_VALID_HOURS
    if code:
        return (
            f"Deze code is {hours} uur geldig."
            if lng == "nl"
            else f"This code is valid for {hours} hours."
        )
    return (
        f"Deze link is {hours} uur geldig."
        if lng == "nl"
        else f"This link is valid for {hours} hours."
    )


def token_link_label_text(lang: str, *, reset: bool = False) -> str:
    lng = normalize_lang(lang)
    hours = TOKEN_VALID_HOURS
    if reset:
        return (
            f"Resetlink · {hours} uur geldig"
            if lng == "nl"
            else f"Reset link · valid for {hours} hours"
        )
    return (
        f"Bevestigingslink · {hours} uur geldig"
        if lng == "nl"
        else f"Confirmation link · valid for {hours} hours"
    )


COPY: dict[str, dict[str, str]] = {
    "nl": {
        "greeting": "Hallo,",
        "button": "E-mail bevestigen",
        "footer_auto": "Automatisch bericht van RackForge.",
        "footer_noreply": "Antwoorden op dit e-mailadres worden niet gelezen.",
        "plain_footer": (
            "\n\n---\n"
            "Dit is een automatisch bericht van RackForge. "
            "Antwoorden op dit e-mailadres worden niet gelezen.\n"
        ),
        "register_subject": "Bevestig je e-mailadres — RackForge",
        "register_headline": "Welkom",
        "register_preheader": "Welkom bij RackForge — bevestig je e-mailadres om te starten.",
        "register_intro": (
            "Welkom bij RackForge! "
            "Bevestig je e-mailadres om je account te activeren en je rack te plannen."
        ),
        "change_subject": "Bevestig je nieuwe e-mailadres — RackForge",
        "change_headline": "Nieuw e-mailadres",
        "change_preheader": "Bevestig je nieuwe e-mailadres voor RackForge.",
        "change_intro": (
            "Je hebt je e-mailadres gewijzigd. "
            "Klik op de knop hieronder om je nieuwe adres te bevestigen."
        ),
        "test_subject": "Bevestig je e-mailadres — RackForge (test)",
        "test_headline": "Testmail",
        "test_preheader": "Voorbeeld van het RackForge bevestigingsmail.",
        "test_intro": "Dit is een testmail om het RackForge e-mailontwerp te bekijken.",
        "test_note": "Dit is een test — de bevestigingslink werkt niet echt.",
        "test_plain_extra": "Deze link is alleen een test en werkt niet echt.",
        "reset_subject": "Wachtwoord resetten — RackForge",
        "reset_headline": "Wachtwoord vergeten",
        "reset_preheader": "Stel een nieuw wachtwoord in voor je RackForge-account.",
        "reset_intro": (
            "Je hebt een wachtwoord-reset aangevraagd. "
            "Voer onderstaande code in op de inlogpagina om een nieuw wachtwoord in te stellen."
        ),
        "reset_code_label": "Jouw resetcode",
        "reset_button": "Nieuw wachtwoord instellen",
        "admin_reset_subject": "Panel wachtwoord resetten — RackForge",
        "admin_reset_headline": "RackForge Panel",
        "admin_reset_preheader": "Resetcode voor het RackForge beheerpanel.",
        "admin_reset_intro": (
            "Je hebt een wachtwoord-reset aangevraagd voor het RackForge Panel. "
            "Voer onderstaande code in om een nieuw wachtwoord in te stellen."
        ),
    },
    "en": {
        "greeting": "Hello,",
        "button": "Confirm email",
        "footer_auto": "Automated message from RackForge.",
        "footer_noreply": "Replies to this email address are not monitored.",
        "plain_footer": (
            "\n\n---\n"
            "This is an automated message from RackForge. "
            "Replies to this email address are not monitored.\n"
        ),
        "register_subject": "Confirm your email — RackForge",
        "register_headline": "Welcome",
        "register_preheader": "Welcome to RackForge — confirm your email to get started.",
        "register_intro": (
            "Welcome to RackForge! "
            "Confirm your email address to activate your account and start planning your rack."
        ),
        "change_subject": "Confirm your new email — RackForge",
        "change_headline": "New email address",
        "change_preheader": "Confirm your new email address for RackForge.",
        "change_intro": (
            "You changed your email address. "
            "Click the button below to confirm your new address."
        ),
        "test_subject": "Confirm your email — RackForge (test)",
        "test_headline": "Test email",
        "test_preheader": "Preview of the RackForge confirmation email.",
        "test_intro": "This is a test email to preview the RackForge email design.",
        "test_note": "This is a test — the confirmation link does not work.",
        "test_plain_extra": "This link is for testing only and does not work.",
        "reset_subject": "Reset your password — RackForge",
        "reset_headline": "Forgot password",
        "reset_preheader": "Set a new password for your RackForge account.",
        "reset_intro": (
            "You requested a password reset. "
            "Enter the code below on the login page to set a new password."
        ),
        "reset_code_label": "Your reset code",
        "reset_button": "Set new password",
        "admin_reset_subject": "Reset panel password — RackForge",
        "admin_reset_headline": "RackForge Panel",
        "admin_reset_preheader": "Reset code for the RackForge admin panel.",
        "admin_reset_intro": (
            "You requested a password reset for the RackForge Panel. "
            "Enter the code below to set a new password."
        ),
    },
}


def admin_reset_code_email_content(lang: str, code: str) -> dict[str, str]:
    lng = normalize_lang(lang)
    t = COPY[lng]
    return {
        "lang": lng,
        "subject": t["admin_reset_subject"],
        "headline": t["admin_reset_headline"],
        "preheader": t["admin_reset_preheader"],
        "intro": t["admin_reset_intro"],
        "greeting": t["greeting"],
        "code_label": t["reset_code_label"],
        "code": code,
        "footer_auto": t["footer_auto"],
        "footer_noreply": t["footer_noreply"],
        "plain_footer": t["plain_footer"],
        "valid_for": token_valid_for_text(lng, code=True),
    }


def render_reset_code_html(code: str) -> str:
    """Outlook-safe: no letter-spacing (it inserts real spaces when copying)."""
    digits = re.sub(r"\D", "", code)
    spans = "".join(
        (
            '<span style="display:inline;font-family:\'Courier New\',Courier,monospace;'
            "font-size:34px;font-weight:700;line-height:1;color:#f59e0b !important;"
            'margin:0;padding:0;">'
            f"{digit}</span>"
        )
        for digit in digits
    )
    return f'<div style="margin:0;padding:0;line-height:1;">{spans}</div>'


def reset_code_email_content(lang: str, code: str) -> dict[str, str]:
    lng = normalize_lang(lang)
    t = COPY[lng]
    return {
        "lang": lng,
        "subject": t["reset_subject"],
        "headline": t["reset_headline"],
        "preheader": t["reset_preheader"],
        "intro": t["reset_intro"],
        "greeting": t["greeting"],
        "code_label": t["reset_code_label"],
        "code": code,
        "footer_auto": t["footer_auto"],
        "footer_noreply": t["footer_noreply"],
        "plain_footer": t["plain_footer"],
        "valid_for": token_valid_for_text(lng, code=True),
    }


def verification_email_content(
    purpose: str, lang: str, link: str, *, test: bool = False
) -> dict[str, str]:
    lng = normalize_lang(lang)
    t = COPY[lng]
    prefix = "test" if test else ("change" if purpose == "change_email" else "register")
    return {
        "lang": lng,
        "subject": t[f"{prefix}_subject"],
        "headline": t[f"{prefix}_headline"],
        "preheader": t[f"{prefix}_preheader"],
        "intro": t[f"{prefix}_intro"],
        "greeting": t["greeting"],
        "button": t["button"],
        "link_label": token_link_label_text(lng),
        "footer_auto": t["footer_auto"],
        "footer_noreply": t["footer_noreply"],
        "plain_footer": t["plain_footer"],
        "valid_for": token_valid_for_text(lng),
        "test_note": t["test_note"] if test else "",
        "test_plain_extra": t["test_plain_extra"] if test else "",
    }


def find_logo_bytes() -> bytes | None:
    for path in LOGO_SEARCH_PATHS:
        if path.is_file():
            return path.read_bytes()
    return None


def build_verification_html(content: dict[str, str], *, logo_src: str, link: str) -> str:
    lang = content["lang"]
    test_block = ""
    if content.get("test_note"):
        test_block = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin:0 0 20px;">'
            "<tr><td bgcolor=\"#1a2d42\" style=\"padding:10px 12px;background-color:#1a2d42;"
            "border:1px solid #2a4a6a;border-radius:8px;"
            'font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;'
            f'color:#9ec9ff !important;">{content["test_note"]}</td></tr></table>'
        )

    return f"""<!DOCTYPE html>
<html lang="{lang}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>{content["headline"]}</title>
  <!--[if mso]>
  <noscript>
    <xml>
      <o:OfficeDocumentSettings>
        <o:AllowPNG/>
        <o:PixelsPerInch>96</o:PixelsPerInch>
      </o:OfficeDocumentSettings>
    </xml>
  </noscript>
  <![endif]-->
  <style type="text/css">
    #outlook a {{ padding: 0; }}
    body, table, td, p, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; border-collapse: collapse; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; display: block; }}
    .rf-bg {{ background-color: #0a0f14 !important; }}
    .rf-card {{ background-color: #111a22 !important; }}
    .rf-header {{ background-color: #141f29 !important; }}
    .rf-footer {{ background-color: #0d141c !important; }}
    .rf-text {{ color: #e8f0f7 !important; }}
    .rf-muted {{ color: #7a92a8 !important; }}
    .rf-orange {{ color: #f59e0b !important; }}
    @media (prefers-color-scheme: dark) {{
      .rf-bg {{ background-color: #0a0f14 !important; }}
      .rf-card {{ background-color: #111a22 !important; }}
      .rf-text {{ color: #e8f0f7 !important; }}
    }}
  </style>
</head>
<body class="rf-bg" bgcolor="#0a0f14" style="margin:0;padding:0;background-color:#0a0f14 !important;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
    {content["preheader"]}
  </div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0a0f14" class="rf-bg" style="background-color:#0a0f14 !important;">
    <tr>
      <td align="center" bgcolor="#0a0f14" class="rf-bg" style="padding:40px 16px;background-color:#0a0f14 !important;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;">
          <tr>
            <td height="5" bgcolor="#f59e0b" style="height:5px;line-height:5px;font-size:5px;background-color:#f59e0b !important;border-radius:14px 14px 0 0;">&nbsp;</td>
          </tr>
          <tr>
            <td bgcolor="#111a22" class="rf-card" style="background-color:#111a22 !important;border:1px solid #2a3f52;border-top:none;border-radius:0 0 14px 14px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" bgcolor="#141f29" class="rf-header" style="padding:36px 32px 18px;background-color:#141f29 !important;">
                    <img src="{logo_src}" width="84" height="84" alt="RackForge"
                      style="display:block;width:84px;height:84px;border-radius:18px;border:1px solid #2a3f52;">
                    <p class="rf-text" style="margin:18px 0 6px;font-family:Arial,Helvetica,sans-serif;font-size:28px;font-weight:700;line-height:1.1;color:#e8f0f7 !important;letter-spacing:-0.03em;">
                      Rack<font color="#f59e0b"><span class="rf-orange" style="color:#f59e0b !important;">Forge</span></font>
                    </p>
                    <p class="rf-muted" style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:#7a92a8 !important;">
                      {content["headline"]}
                    </p>
                  </td>
                </tr>
                <tr>
                  <td bgcolor="#111a22" class="rf-card" style="padding:28px 32px 8px;background-color:#111a22 !important;font-family:Arial,Helvetica,sans-serif;">
                    <p class="rf-text" style="margin:0 0 14px;font-size:17px;line-height:1.5;color:#e8f0f7 !important;">{content["greeting"]}</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.65;color:#c5d4e3 !important;">{content["intro"]}</p>
                    {test_block}
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td align="center" bgcolor="#f59e0b" style="border-radius:10px;background-color:#f59e0b !important;">
                          <!--[if mso]>
                          <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{link}"
                            style="height:46px;v-text-anchor:middle;width:240px;" arcsize="18%"
                            strokecolor="#f59e0b" fillcolor="#f59e0b">
                            <w:anchorlock/>
                            <center style="color:#0a0f14;font-family:Arial,sans-serif;font-size:15px;font-weight:bold;">
                              {content["button"]}
                            </center>
                          </v:roundrect>
                          <![endif]-->
                          <!--[if !mso]><!-->
                          <a href="{link}"
                            style="display:inline-block;padding:14px 30px;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#0a0f14 !important;text-decoration:none;background-color:#f59e0b;border-radius:10px;">
                            {content["button"]}
                          </a>
                          <!--<![endif]-->
                        </td>
                      </tr>
                    </table>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0a0f14"
                      style="margin-top:28px;background-color:#0a0f14 !important;border:1px solid #243444;border-radius:10px;">
                      <tr>
                        <td bgcolor="#0a0f14" style="padding:14px 16px;background-color:#0a0f14 !important;">
                          <p class="rf-muted" style="margin:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#7a92a8 !important;">
                            {content["link_label"]}
                          </p>
                          <a href="{link}"
                            style="font-family:Consolas,Monaco,monospace;font-size:12px;line-height:1.5;color:#3b9eff !important;word-break:break-all;text-decoration:none;">
                            {link}
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td bgcolor="#0d141c" class="rf-footer" style="padding:22px 32px 30px;border-top:1px solid #243444;background-color:#0d141c !important;">
                    <p class="rf-muted" style="margin:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;color:#7a92a8 !important;">
                      {content["footer_auto"]}
                    </p>
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;color:#5f7386 !important;">
                      {content["footer_noreply"]}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_plain_body(content: dict[str, str], link: str) -> str:
    extra = ""
    if content.get("test_plain_extra"):
        extra = f"\n\n{content['test_plain_extra']}"
    return (
        f"{content['greeting']}\n\n"
        f"{content['intro']}\n\n"
        f"{link}\n\n"
        f"{content['valid_for']}{extra}{content['plain_footer']}"
    )


def build_reset_code_html(content: dict[str, str], *, logo_src: str) -> str:
    lang = content["lang"]
    code_html = render_reset_code_html(content["code"])
    return f"""<!DOCTYPE html>
<html lang="{lang}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{content["headline"]}</title>
</head>
<body bgcolor="#0a0f14" style="margin:0;padding:0;background-color:#0a0f14 !important;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0a0f14" style="background-color:#0a0f14 !important;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;">
          <tr>
            <td height="5" bgcolor="#f59e0b" style="height:5px;background-color:#f59e0b !important;border-radius:14px 14px 0 0;">&nbsp;</td>
          </tr>
          <tr>
            <td bgcolor="#111a22" style="background-color:#111a22 !important;border:1px solid #2a3f52;border-top:none;border-radius:0 0 14px 14px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td align="center" bgcolor="#141f29" style="padding:36px 32px 18px;background-color:#141f29 !important;">
                    <img src="{logo_src}" width="84" height="84" alt="RackForge" style="display:block;width:84px;height:84px;border-radius:18px;border:1px solid #2a3f52;">
                    <p style="margin:18px 0 6px;font-family:Arial,Helvetica,sans-serif;font-size:28px;font-weight:700;color:#e8f0f7 !important;">
                      Rack<font color="#f59e0b">Forge</font>
                    </p>
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:#7a92a8 !important;">
                      {content["headline"]}
                    </p>
                  </td>
                </tr>
                <tr>
                  <td bgcolor="#111a22" style="padding:28px 32px 8px;background-color:#111a22 !important;font-family:Arial,Helvetica,sans-serif;">
                    <p style="margin:0 0 14px;font-size:17px;line-height:1.5;color:#e8f0f7 !important;">{content["greeting"]}</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.65;color:#c5d4e3 !important;">{content["intro"]}</p>
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#0a0f14" style="background-color:#0a0f14 !important;border:1px solid #243444;border-radius:10px;">
                      <tr>
                        <td align="center" style="padding:22px 16px;background-color:#0a0f14 !important;">
                          <p style="margin:0 0 10px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#7a92a8 !important;">
                            {content["code_label"]}
                          </p>
                          {code_html}
                        </td>
                      </tr>
                    </table>
                    <p style="margin:24px 0 0;font-size:13px;line-height:1.55;color:#7a92a8 !important;">{content["valid_for"]}</p>
                  </td>
                </tr>
                <tr>
                  <td bgcolor="#0d141c" style="padding:22px 32px 30px;border-top:1px solid #243444;background-color:#0d141c !important;">
                    <p style="margin:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;color:#7a92a8 !important;">{content["footer_auto"]}</p>
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.55;color:#5f7386 !important;">{content["footer_noreply"]}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_reset_code_plain(content: dict[str, str]) -> str:
    code = re.sub(r"\D", "", content["code"])
    return (
        f"{content['greeting']}\n\n"
        f"{content['intro']}\n\n"
        f"{content['code_label']}: {code}\n\n"
        f"{content['valid_for']}{content['plain_footer']}"
    )


def build_reset_code_message(
    *,
    to_email: str,
    from_addr: str,
    content: dict[str, str],
    app_url: str,
) -> EmailMessage | MIMEMultipart:
    logo_url = f"{app_url.rstrip('/')}/icons/rackforge-avatar.png"
    logo_bytes = find_logo_bytes()
    logo_src = f"cid:{LOGO_CID}" if logo_bytes else logo_url
    plain = build_reset_code_plain(content)
    html = build_reset_code_html(content, logo_src=logo_src)

    if logo_bytes:
        msg: EmailMessage | MIMEMultipart = MIMEMultipart("related")
        msg["Subject"] = content["subject"]
        msg["From"] = from_addr
        msg["To"] = to_email

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(plain, "plain", "utf-8"))
        alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)

        image = MIMEImage(logo_bytes, _subtype="png")
        image.add_header("Content-ID", f"<{LOGO_CID}>")
        image.add_header("Content-Disposition", "inline", filename="rackforge-avatar.png")
        msg.attach(image)
        return msg

    simple = EmailMessage()
    simple["Subject"] = content["subject"]
    simple["From"] = from_addr
    simple["To"] = to_email
    simple.set_content(plain, charset="utf-8")
    simple.add_alternative(html, subtype="html", charset="utf-8")
    return simple


def build_verification_message(
    *,
    to_email: str,
    from_addr: str,
    content: dict[str, str],
    link: str,
    app_url: str,
) -> EmailMessage | MIMEMultipart:
    logo_url = f"{app_url.rstrip('/')}/icons/rackforge-avatar.png"
    logo_bytes = find_logo_bytes()
    logo_src = f"cid:{LOGO_CID}" if logo_bytes else logo_url
    plain = build_plain_body(content, link)
    html = build_verification_html(content, logo_src=logo_src, link=link)

    if logo_bytes:
        msg: EmailMessage | MIMEMultipart = MIMEMultipart("related")
        msg["Subject"] = content["subject"]
        msg["From"] = from_addr
        msg["To"] = to_email

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(plain, "plain", "utf-8"))
        alt.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alt)

        image = MIMEImage(logo_bytes, _subtype="png")
        image.add_header("Content-ID", f"<{LOGO_CID}>")
        image.add_header("Content-Disposition", "inline", filename="rackforge-avatar.png")
        msg.attach(image)
        return msg

    simple = EmailMessage()
    simple["Subject"] = content["subject"]
    simple["From"] = from_addr
    simple["To"] = to_email
    simple.set_content(plain, charset="utf-8")
    simple.add_alternative(html, subtype="html", charset="utf-8")
    return simple