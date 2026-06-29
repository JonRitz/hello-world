import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _signal_color(signal: str) -> str:
    colors = {
        "undervalued": "#16a34a",
        "overvalued": "#dc2626",
        "fairly_valued": "#d97706",
        "bullish": "#16a34a",
        "strong_bullish": "#15803d",
        "bearish": "#dc2626",
        "strong_bearish": "#b91c1c",
        "neutral": "#6b7280",
        "strong_uptrend": "#15803d",
        "uptrend": "#16a34a",
        "sideways": "#6b7280",
        "downtrend": "#dc2626",
        "strong_downtrend": "#b91c1c",
        "high": "#16a34a",
        "moderate": "#d97706",
        "low": "#6b7280",
        "none": "#9ca3af",
        "unknown": "#9ca3af",
    }
    return colors.get(signal, "#6b7280")


def _trend_arrow(trend: str) -> str:
    return {
        "strong_uptrend": "↑↑",
        "uptrend": "↑",
        "sideways": "→",
        "downtrend": "↓",
        "strong_downtrend": "↓↓",
    }.get(trend, "→")


def build_html_email(report_text: str | None, ranked: list) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    top10 = ranked[:10]

    rows_html = ""
    for i, (ticker, score, data) in enumerate(top10):
        val = data["valuation"]
        tech = data["technical"]
        opts = data["options"]

        price = f"${tech['current_price']:.2f}" if tech.get("current_price") else "—"
        pe = f"{val['pe_ratio']:.1f}x" if val.get("pe_ratio") else "—"
        div = f"{val['dividend_yield']:.1f}%" if val.get("dividend_yield") else "—"
        rsi = f"{tech.get('rsi', 50):.0f}"
        trend = tech.get("trend", "sideways")
        val_sig = val.get("valuation_signal", "unknown")
        opts_sig = opts.get("options_signal", "neutral")
        smart = " ★" if opts.get("smart_money_alert") else ""
        name = (val.get("name") or "")[:28]
        sector = val.get("sector", "")
        bg = "#f9fafb" if i % 2 == 0 else "#ffffff"

        rows_html += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 12px;font-weight:700;color:#1e40af;font-size:15px;">{ticker}</td>
          <td style="padding:10px 12px;color:#374151;font-size:13px;">{name}</td>
          <td style="padding:10px 12px;font-weight:600;color:#111827;">{price}</td>
          <td style="padding:10px 12px;color:{_signal_color(val_sig)};font-weight:600;font-size:13px;">{val_sig.replace('_',' ').title()}</td>
          <td style="padding:10px 12px;color:#374151;">{pe}</td>
          <td style="padding:10px 12px;color:#16a34a;font-weight:600;">{div}</td>
          <td style="padding:10px 12px;color:#374151;">{rsi}</td>
          <td style="padding:10px 12px;color:{_signal_color(trend)};font-weight:600;">{_trend_arrow(trend)} {trend.replace('_',' ').title()}</td>
          <td style="padding:10px 12px;color:{_signal_color(opts_sig)};font-size:13px;">{opts_sig.replace('_',' ').title()}{smart}</td>
          <td style="padding:10px 12px;color:#6b7280;font-size:12px;">{sector}</td>
        </tr>"""

    ai_section = ""
    if report_text:
        # Convert plain text report to simple HTML paragraphs
        escaped = report_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines = escaped.split("\n")
        html_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                html_lines.append("<br>")
            elif stripped.startswith("===") or stripped.startswith("---"):
                html_lines.append('<hr style="border:none;border-top:1px solid #e5e7eb;margin:8px 0;">')
            elif stripped.isupper() and len(stripped) > 3 and len(stripped) < 60:
                html_lines.append(f'<p style="font-weight:700;color:#1e3a8a;font-size:14px;margin:16px 0 4px;">{stripped}</p>')
            elif stripped.startswith("#"):
                text = stripped.lstrip("#").strip()
                html_lines.append(f'<p style="font-weight:700;color:#1e3a8a;font-size:15px;margin:16px 0 4px;">{text}</p>')
            else:
                html_lines.append(f'<p style="margin:4px 0;color:#374151;line-height:1.6;">{line}</p>')

        ai_section = f"""
        <div style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:20px 24px;margin:24px 0;border-radius:0 8px 8px 0;">
          <p style="font-weight:700;color:#1e3a8a;font-size:16px;margin:0 0 12px;">Hedge Fund Morning Note</p>
          <div style="font-family:Georgia,serif;font-size:14px;">
            {''.join(html_lines)}
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
  <div style="max-width:900px;margin:24px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,0.07);">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 100%);padding:28px 32px;">
      <p style="margin:0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Daily Scan</p>
      <h1 style="margin:4px 0 0;color:#ffffff;font-size:26px;font-weight:700;">Market Scanner</h1>
      <p style="margin:6px 0 0;color:#bfdbfe;font-size:14px;">{today}</p>
    </div>

    <div style="padding:28px 32px;">

      {ai_section}

      <!-- Rankings table -->
      <h2 style="color:#111827;font-size:18px;margin:0 0 16px;">Top 10 Candidates — Quantitative Rankings</h2>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead>
            <tr style="background:#1e3a8a;color:#ffffff;">
              <th style="padding:10px 12px;text-align:left;">Ticker</th>
              <th style="padding:10px 12px;text-align:left;">Name</th>
              <th style="padding:10px 12px;text-align:left;">Price</th>
              <th style="padding:10px 12px;text-align:left;">Valuation</th>
              <th style="padding:10px 12px;text-align:left;">P/E</th>
              <th style="padding:10px 12px;text-align:left;">Div%</th>
              <th style="padding:10px 12px;text-align:left;">RSI</th>
              <th style="padding:10px 12px;text-align:left;">Trend</th>
              <th style="padding:10px 12px;text-align:left;">Options</th>
              <th style="padding:10px 12px;text-align:left;">Sector</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>

      <p style="color:#9ca3af;font-size:11px;margin:20px 0 0;">
        ★ = smart money options alert &nbsp;|&nbsp;
        Data via Yahoo Finance &nbsp;|&nbsp;
        Analysis via Claude AI &nbsp;|&nbsp;
        Not financial advice
      </p>
    </div>

    <!-- Footer -->
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;">
      <p style="margin:0;color:#6b7280;font-size:12px;">
        Market Scanner &nbsp;·&nbsp; Sent to jritter@fanaticsinc.com &nbsp;·&nbsp;
        <a href="https://github.com/JonRitz/hello-world" style="color:#3b82f6;">View on GitHub</a>
      </p>
    </div>
  </div>
</body>
</html>"""


def send_email(html_body: str, subject: str | None = None) -> bool:
    """Send via Gmail SMTP. Requires GMAIL_USER and GMAIL_APP_PASSWORD env vars."""
    smtp_user = os.environ.get("GMAIL_USER", "")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    recipient = os.environ.get("REPORT_EMAIL", "jritter@fanaticsinc.com")

    if not smtp_user or not smtp_pass:
        print("[emailer] GMAIL_USER or GMAIL_APP_PASSWORD not set — skipping email")
        return False

    today = date.today().strftime("%B %d, %Y")
    if not subject:
        subject = f"Market Scanner — {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Market Scanner <{smtp_user}>"
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipient, msg.as_string())
        print(f"[emailer] Report sent to {recipient}")
        return True
    except Exception as e:
        print(f"[emailer] Failed to send email: {e}")
        return False
