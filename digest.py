#!/usr/bin/env python3
"""
Research Digest Generator
Scans RSS feeds and generates personalized research digest using Gemini AI
"""

import os
import yaml
import feedparser
import google.generativeai as genai
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def load_config():
    """Load configuration from config.yaml"""
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)


def fetch_papers(feeds):
    """Fetch papers from RSS feeds"""
    papers = []
    for feed_info in feeds:
        print(f"Fetching from {feed_info['name']}...")
        feed = feedparser.parse(feed_info['url'])

        for entry in feed.entries[:50]:  # Limit to 50 recent papers per feed
            papers.append({
                'title': entry.get('title', ''),
                'summary': entry.get('summary', ''),
                'link': entry.get('link', ''),
                'source': feed_info['name']
            })

    return papers


def filter_and_rank_papers(papers, research_interests, max_papers):
    """Use Gemini to filter and rank papers by relevance"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    # Build papers list with full information
    papers_list = []
    for i, p in enumerate(papers[:150], 1):  # Increased to 150 papers
        papers_list.append(f"{i}. **{p['title']}** (Source: {p['source']})\n   Abstract: {p['summary'][:400]}\n   Link: {p['link']}")

    prompt = f"""You are an expert research assistant with deep knowledge of academic literature.

RESEARCHER'S PROFILE:
{research_interests}

YOUR TASK:
Carefully review the papers below and select the TOP {max_papers} most valuable papers for this researcher.
Be highly selective - only include papers that would genuinely advance their research.

PAPERS TO REVIEW:
{chr(10).join(papers_list)}

OUTPUT FORMAT:
For each selected paper, provide:

### [Paper Number]. Paper Title

**Source:** [Journal/Working Paper Series]

**Why this matters:** [2-3 sentences explaining the paper's relevance to the researcher's work. Be specific - reference their research questions, methods, or contexts. Explain what they can learn or adapt from this paper.]

**Key findings:** [2-3 sentences on the main empirical results, methodology, or theoretical contribution. Focus on actionable insights.]

**Link:** [Full URL]

---

CRITICAL INSTRUCTIONS:
- Quality over quantity: It's better to return 5 exceptional papers than 15 mediocre ones
- Be ruthless: Only include papers that directly advance their research agenda
- Prioritize papers with strong identification strategies and novel contributions
- Skip papers that are tangentially related or merely descriptive
- For each paper, think: "Would I email this to them if I were their research assistant?"
- Order papers by relevance (most relevant first)
- If fewer than {max_papers} papers meet the high bar, that's okay - only return the truly valuable ones

Begin your response with a brief 1-sentence summary of the overall quality and themes of this week's papers, then list the selected papers.
"""

    response = model.generate_content(prompt)
    return response.text


def generate_html_email(digest_content, config):
    """Generate HTML email from digest content"""
    # Convert markdown-style formatting to HTML
    import re

    # Convert ### headings to h3
    digest_content = re.sub(r'###\s+(.+)', r'<h3>\1</h3>', digest_content)

    # Convert **bold** to <strong>
    digest_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', digest_content)

    # Convert links
    digest_content = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', digest_content)

    # Convert line breaks
    digest_content = digest_content.replace('\n\n', '<br><br>')

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #1a1a1a;
                max-width: 700px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
            }}
            h1 {{
                color: #0060df;
                font-size: 28px;
                margin-bottom: 10px;
                border-bottom: 3px solid #0060df;
                padding-bottom: 10px;
            }}
            h3 {{
                color: #003d99;
                font-size: 18px;
                margin-top: 30px;
                margin-bottom: 12px;
                line-height: 1.4;
            }}
            .meta {{
                color: #666;
                font-size: 14px;
                margin-bottom: 30px;
            }}
            a {{
                color: #0060df;
                text-decoration: none;
                font-weight: 500;
            }}
            a:hover {{
                color: #003d99;
                text-decoration: underline;
            }}
            strong {{
                color: #003d99;
                font-weight: 600;
            }}
            hr {{
                border: none;
                border-top: 1px solid #e0e0e0;
                margin: 40px 0 20px 0;
            }}
            .footer {{
                color: #999;
                font-size: 13px;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #e0e0e0;
            }}
            .summary {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                font-style: italic;
                color: #555;
            }}
        </style>
    </head>
    <body>
        <h1>📚 Research Digest</h1>
        <p class="meta">{datetime.now().strftime('%B %d, %Y')}</p>

        {digest_content}

        <div class="footer">
            <p>Generated by your personal <a href="https://github.com/zytynski/research-digest">Research Digest</a></p>
            <p style="font-size: 12px; color: #bbb;">To modify preferences, edit config.yaml in your repository</p>
        </div>
    </body>
    </html>
    """
    return html


def send_email(html_content, config):
    """Send digest via email using Gmail SMTP"""
    email_method = config.get('email_method', 'print')

    if email_method == 'print':
        # Preview mode - just print the digest
        print("Email generation successful!")
        print(f"Would send to: {config['email']}")
        print("\nPreview:")
        print(html_content[:500])
        return

    elif email_method == 'gmail':
        # Gmail SMTP
        sender_email = os.environ.get('GMAIL_ADDRESS')
        sender_password = os.environ.get('GMAIL_APP_PASSWORD')

        if not sender_email or not sender_password:
            raise ValueError("Gmail credentials not found. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in secrets.")

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Research Digest - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = sender_email
        msg['To'] = config['email']

        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
            print(f"Email sent successfully to {config['email']}")
        except Exception as e:
            print(f"Failed to send email: {e}")
            raise

    else:
        raise ValueError(f"Unknown email method: {email_method}. Use 'print' or 'gmail'")


def main():
    """Main execution"""
    print("Starting Research Digest Generator...")

    # Load configuration
    config = load_config()
    print(f"Configuration loaded for: {config['email']}")

    # Fetch papers
    papers = fetch_papers(config['feeds'])
    print(f"Fetched {len(papers)} papers from {len(config['feeds'])} sources")

    # Filter and rank
    print("Analyzing papers with AI...")
    digest_content = filter_and_rank_papers(
        papers,
        config['research_interests'],
        config['max_papers']
    )

    # Generate email
    html_email = generate_html_email(digest_content, config)

    # Send email
    send_email(html_email, config)

    print("Digest generation complete!")


if __name__ == "__main__":
    main()
