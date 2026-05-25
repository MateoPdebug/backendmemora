import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "lucasmateoperezechenique@gmail.com"           
SMTP_PASSWORD = "cjjs uwwr zscn otvy"        
SMTP_FROM_NAME = "Memora"


def _send(to: str, subject: str, html: str, text_fallback: str) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        # Modo dev: log a consola.
        print("=" * 60)
        print(f"[MAIL MOCK] To: {to}")
        print(f"[MAIL MOCK] Subject: {subject}")
        print(f"[MAIL MOCK] Body:\n{text_fallback}")
        print("=" * 60)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to
    msg.attach(MIMEText(text_fallback, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, [to], msg.as_string())


def send_reset_code(to: str, nombre: str, codigo: str) -> None:
    subject = "Tu código para recuperar la contraseña — Memora"
    text = (
        f"Hola {nombre},\n\n"
        f"Tu código de recuperación es: {codigo}\n\n"
        f"Vence en 15 minutos. Si no pediste esto, ignorá este mail.\n\n"
        f"— Memora"
    )
    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#0A0F1F;color:#fff;padding:32px;border-radius:16px;max-width:480px;margin:0 auto;">
      <h2 style="margin:0 0 16px;">Recuperar contraseña</h2>
      <p>Hola {nombre},</p>
      <p>Tu código de recuperación es:</p>
      <div style="font-size:32px;font-weight:bold;letter-spacing:8px;background:#7F5AF0;color:#fff;padding:18px;border-radius:12px;text-align:center;margin:20px 0;">
        {codigo}
      </div>
      <p style="color:#bbb;font-size:13px;">Vence en 15 minutos. Si no pediste esto, ignorá este mensaje.</p>
      <p style="color:#888;font-size:12px;margin-top:24px;">— Memora</p>
    </div>
    """
    _send(to, subject, html, text)
