import logging

from exceptions import ValidationError
from helpers import get_config, set_config


def get_smtp_config():
    return {
        'host': get_config('smtp_host', ''),
        'port': get_config('smtp_port', '587'),
        'security': get_config('smtp_security', 'tls'),
        'user': get_config('smtp_user', ''),
        'password': get_config('smtp_password', ''),
        'from_addr': get_config('smtp_from', ''),
        'from_name': get_config('smtp_from_name', 'Derby des Groins'),
        'enabled': get_config('smtp_enabled', '0') == '1',
    }


def send_email(to_addr, subject, body_html):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    cfg = get_smtp_config()
    if not cfg['enabled']:
        return False, "L'envoi d'emails est desactive."
    if not cfg['host'] or not cfg['from_addr']:
        return False, "Configuration SMTP incomplete."

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{cfg['from_name']} <{cfg['from_addr']}>"
    msg['To'] = to_addr
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    try:
        port = int(cfg['port'] or 587)
        if cfg['security'] == 'ssl':
            server = smtplib.SMTP_SSL(cfg['host'], port, timeout=15)
        else:
            server = smtplib.SMTP(cfg['host'], port, timeout=15)
            if cfg['security'] == 'tls':
                server.starttls()

        if cfg['user'] and cfg['password']:
            server.login(cfg['user'], cfg['password'])

        server.sendmail(cfg['from_addr'], [to_addr], msg.as_string())
        server.quit()
        return True, None
    except Exception:
        logging.getLogger(__name__).exception("Echec envoi email a %s", to_addr)
        return False, "Erreur lors de l'envoi de l'email. Verifiez la configuration SMTP."


def save_smtp_settings(form_data):
    smtp_keys = {
        'smtp_host': form_data.get('smtp_host', '').strip(),
        'smtp_port': form_data.get('smtp_port', '587').strip(),
        'smtp_security': form_data.get('smtp_security', 'tls').strip(),
        'smtp_user': form_data.get('smtp_user', '').strip(),
        'smtp_from': form_data.get('smtp_from', '').strip(),
        'smtp_from_name': form_data.get('smtp_from_name', 'Derby des Groins').strip(),
        'smtp_enabled': '1' if 'smtp_enabled' in form_data else '0',
    }
    new_password = form_data.get('smtp_password', '').strip()
    if new_password:
        smtp_keys['smtp_password'] = new_password

    for key, value in smtp_keys.items():
        set_config(key, value)

    return "📧 Configuration SMTP sauvegardee !"


def send_test_smtp_email(to_addr):
    to_addr = (to_addr or '').strip()
    if not to_addr:
        raise ValidationError("Adresse email requise.")

    html = """
    <h2>🐷 Derby des Groins — Test SMTP</h2>
    <p>Si tu lis ce message, la configuration SMTP fonctionne correctement !</p>
    <p style="color:#888;font-size:12px;">Envoye depuis le panneau d'administration.</p>
    """
    ok, err = send_email(to_addr, 'Test SMTP — Derby des Groins', html)
    if ok:
        return f"✅ Email de test envoye a {to_addr} !", "success"
    return f"❌ Echec : {err}", "error"
