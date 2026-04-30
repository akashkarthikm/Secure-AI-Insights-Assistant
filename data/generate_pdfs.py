"""
PDF generator for the Secure AI Insights Assistant.

Produces five short business documents under data/raw/ that the
retrieval tool will index in phase 2:

  - quarterly_report_q3_2025.pdf
  - campaign_performance_stellar_run.pdf
  - content_roadmap_2026.pdf
  - policy_guidelines.pdf
  - audience_behavior_report.pdf

Run: python data/generate_pdfs.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
)
from reportlab.lib import colors

OUT = Path(__file__).parent / "raw"
OUT.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"], fontSize=20, spaceAfter=18, alignment=TA_LEFT,
))
styles.add(ParagraphStyle(
    name="SectionHeading", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="BodyTextTight", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=8,
))


def build(filename, title, blocks):
    """blocks is a list of ('heading'|'para'|'spacer', content)."""
    doc = SimpleDocTemplate(
        str(OUT / filename), pagesize=LETTER,
        leftMargin=0.9*inch, rightMargin=0.9*inch,
        topMargin=0.9*inch, bottomMargin=0.9*inch,
    )
    flow = [Paragraph(title, styles["DocTitle"])]
    for kind, content in blocks:
        if kind == "heading":
            flow.append(Paragraph(content, styles["SectionHeading"]))
        elif kind == "para":
            flow.append(Paragraph(content, styles["BodyTextTight"]))
        elif kind == "spacer":
            flow.append(Spacer(1, content))
    doc.build(flow)
    print(f"  {filename}")


# ---------- Quarterly executive report ----------

def quarterly_report():
    build("quarterly_report_q3_2025.pdf", "Quarterly Executive Report — Q3 2025", [
        ("heading", "Executive Summary"),
        ("para",
         "Q3 2025 was defined by the breakout performance of Stellar Run, the strongest "
         "single-title quarter in the platform's recent history. Total streaming hours "
         "grew 18% quarter-on-quarter, with new subscriber additions concentrated in "
         "South Asia. Drama and Sci-Fi were the leading genres by completion rate. "
         "Comedy continued its multi-quarter decline and is flagged as a priority "
         "remediation area for Q4."),

        ("heading", "Stellar Run — Drivers of the Trend"),
        ("para",
         "Stellar Run released on June 15 to modest opening-week numbers but began "
         "trending sharply in early August. Three factors drove the surge. First, a "
         "concentrated marketing push across YouTube and Instagram between weeks 28 "
         "and 38 lifted top-of-funnel impressions roughly fourfold versus the baseline. "
         "Second, an unscripted reaction video from a prominent science-fiction creator "
         "went viral in the second week of August, generating an estimated 40 million "
         "organic impressions at near-zero acquisition cost. Third, the title's "
         "completion rate held above 80% throughout the spike window, indicating that "
         "interest converted into actual viewing rather than browsing."),
        ("para",
         "The combined effect was a sustained watch-volume increase that has not yet "
         "decayed as of the end of Q3. Recommendation: extend the campaign through Q4 "
         "with a budget reallocation toward APAC, where engagement-per-impression is "
         "highest."),

        ("heading", "Genre Performance"),
        ("para",
         "Drama and Sci-Fi led on engagement quality, with average completion rates "
         "above 70% and a healthy distribution of viewing across age bands. Action and "
         "Thriller were stable. Comedy underperformed across every measured metric: "
         "completion rate fell below 45%, average rating dropped below 3.0, and repeat "
         "watch rates were the lowest of any genre."),
        ("para",
         "Two factors are believed to drive the Comedy decline. The slate this year "
         "skewed toward regional comedy formats that did not travel well across "
         "language markets, and the marketing investment in Comedy was the lowest of "
         "any genre at roughly 40% of the platform average. The content team is "
         "reviewing the Q4 and 2026 Comedy slate for course correction."),

        ("heading", "Regional Highlights"),
        ("para",
         "Mumbai emerged as the standout city in late Q3, with weekly watch hours "
         "growing 32% month-on-month in November and engagement per viewer well above "
         "the platform average. The growth was concentrated in the 25-34 age band and "
         "skewed toward mobile devices. India overall remains the fastest-growing "
         "country market, with Delhi and Bangalore also above the global average."),
        ("para",
         "North America and Europe were stable. LATAM showed early signs of softening "
         "and is being monitored."),

        ("heading", "Recommendations for Q4"),
        ("para",
         "First, extend Stellar Run promotion through end of Q4 with India-weighted "
         "spend. Second, pause new Comedy commissioning until the slate review "
         "completes. Third, increase content acquisition and production capacity in "
         "regional languages serving the Mumbai growth corridor. Fourth, prepare a "
         "Sci-Fi follow-up release for early Q1 2026 to retain the audience Stellar "
         "Run has acquired."),
    ])


# ---------- Campaign performance ----------

def campaign_summary():
    build("campaign_performance_stellar_run.pdf", "Campaign Performance Summary — Stellar Run", [
        ("heading", "Campaign Overview"),
        ("para",
         "The Stellar Run promotional campaign ran from week 27 through week 39 of "
         "2025, spanning the title's transition from launch window to viral peak. "
         "Total media spend across all channels and regions exceeded the original "
         "budget by approximately 22%, reflecting in-flight reallocations toward "
         "channels that were converting at above-plan rates."),

        ("heading", "Channel Mix"),
        ("para",
         "YouTube and Instagram together accounted for roughly 60% of the spend and "
         "delivered the bulk of measurable lift. Search and Display performed in line "
         "with expectations. TV and Print were used in a supporting brand role and are "
         "not credited with direct conversion. The single highest-ROI window was the "
         "two-week period immediately following the viral creator moment in early "
         "August, where organic traffic let paid spend retarget rather than acquire."),

        ("heading", "Regional Allocation"),
        ("para",
         "North America received the largest absolute spend in dollar terms, but India "
         "delivered the highest engagement-per-dollar by a wide margin. APAC overall "
         "outperformed forecast by approximately 35%. Europe was on plan. LATAM "
         "underdelivered against forecast and is recommended for reduced allocation in "
         "any extension."),

        ("heading", "Creative Themes"),
        ("para",
         "Three creative cuts were tested. The character-led 30-second cut was the "
         "strongest performer and drove the majority of click-through. The "
         "atmospheric trailer underperformed in 6-second pre-roll formats. A "
         "behind-the-scenes cut performed best on Instagram Reels and YouTube Shorts. "
         "Future campaigns should default to character-driven creative for paid "
         "placements."),

        ("heading", "Lessons and Carry-Forward"),
        ("para",
         "Concentrate spend in the two-to-four-week window where audience momentum is "
         "highest. Be prepared to reallocate quickly when an organic moment occurs. "
         "Treat India and APAC as primary markets for future Sci-Fi releases."),
    ])


# ---------- Content roadmap ----------

def content_roadmap():
    build("content_roadmap_2026.pdf", "Content Roadmap — 2026", [
        ("heading", "Strategic Priorities"),
        ("para",
         "The 2026 slate is built around three priorities. First, capitalize on the "
         "Sci-Fi audience built by Stellar Run with two scheduled releases in the "
         "first half of the year. Second, rebuild the Comedy slate around regional "
         "formats that have demonstrated cross-market portability. Third, expand "
         "Drama production in regional languages to serve growing demand in South "
         "Asia."),

        ("heading", "Q1 2026 Releases"),
        ("para",
         "Two major releases are scheduled. A Sci-Fi feature targeting the Stellar "
         "Run audience opens the quarter and is positioned as the year's tentpole "
         "title. A drama anthology in three regional languages follows in late "
         "March, designed to deepen engagement in India and Southeast Asia."),

        ("heading", "Q2 2026 Releases"),
        ("para",
         "A second Sci-Fi title arrives in Q2 with a smaller budget but a strong "
         "creator pedigree. Two original Comedy specials are planned, both built "
         "around stand-up formats that have shown stronger international appeal "
         "than scripted comedy in our recent measurement."),

        ("heading", "H2 2026"),
        ("para",
         "The second half remains in planning. Current direction is to maintain "
         "Drama and Sci-Fi cadence while testing two new Thriller formats. "
         "Documentary investment is increasing modestly based on improving "
         "engagement metrics in Q3 2025."),

        ("heading", "Investment Priorities"),
        ("para",
         "Marketing spend is being rebalanced toward digital channels, with a "
         "structural increase in YouTube and short-form video allocation. Production "
         "capacity in Mumbai is increasing by approximately 40% to support the "
         "regional language Drama strategy. Comedy production capacity is being held "
         "flat pending the slate review."),
    ])


# ---------- Policy guidelines ----------

def policy_guidelines():
    build("policy_guidelines.pdf", "Internal Policy Guidelines", [
        ("heading", "Data Handling"),
        ("para",
         "Viewer-level data is classified as confidential and may not be exported "
         "outside approved analytics environments. Aggregated metrics at the city or "
         "country level may be shared with partners under standard contractual "
         "confidentiality. Raw watch-activity records may not be queried directly by "
         "any system that does not enforce row-level access controls."),
        ("para",
         "Personally identifiable information is not stored. Viewer identifiers are "
         "synthetic and cannot be reversed to real individuals. Reviews and "
         "engagement data are pseudonymous."),

        ("heading", "Content Rating and Regional Restrictions"),
        ("para",
         "All titles carry a content rating assigned at acquisition or production "
         "time. Regional availability is determined by licensing terms and local "
         "regulatory requirements. Titles flagged for restricted regions are filtered "
         "at the recommendation layer and are not shown in catalog browsing for "
         "viewers in those regions."),

        ("heading", "Advertising and Marketing Standards"),
        ("para",
         "All marketing creative requires approval before placement. Targeting "
         "criteria for paid acquisition exclude age bands under 18 for any title not "
         "rated for minors. Spend allocation by region is reviewed quarterly and "
         "must remain within approved governance limits."),

        ("heading", "Acceptable Use of Internal Analytics"),
        ("para",
         "Internal analytics tools and AI assistants are intended for legitimate "
         "business use. Queries must not attempt to identify individual viewers, "
         "extract bulk personal data, or circumvent regional access controls. All "
         "queries are logged for audit purposes."),
    ])


# ---------- Audience behavior ----------

def audience_behavior():
    build("audience_behavior_report.pdf", "Audience Behavior Report", [
        ("heading", "Overview"),
        ("para",
         "This report summarizes engagement patterns observed across age bands, "
         "devices, and dayparts. It is intended as an input to programming, "
         "marketing, and product decisions. All findings are based on aggregated "
         "behavior over the trailing twelve months."),

        ("heading", "Age Bands"),
        ("para",
         "The 25-34 age band is the largest and most engaged segment, accounting "
         "for the highest share of total minutes watched and the highest completion "
         "rates across most genres. The 18-24 band shows shorter average sessions "
         "but the highest social engagement and the strongest response to viral "
         "moments. The 35-44 band concentrates around Drama and Documentary. The "
         "45+ bands favor Drama and Thriller."),

        ("heading", "Devices"),
        ("para",
         "Mobile is the dominant device across India and Southeast Asia. TV is the "
         "dominant device in North America and most of Europe. Tablet is a "
         "significant secondary device in the 35-44 band. Web traffic is small but "
         "concentrated in business hours and likely reflects partial-session "
         "viewing."),

        ("heading", "Dayparts"),
        ("para",
         "Engagement peaks between 8pm and 11pm local time across all regions, with "
         "a secondary peak in the 12pm-2pm window driven by mobile sessions. "
         "Weekends show longer average session lengths and higher completion rates. "
         "Friday and Saturday nights are the strongest single windows for new title "
         "discovery."),

        ("heading", "Implications"),
        ("para",
         "Marketing should weight digital and short-form spend toward the 18-24 and "
         "25-34 bands during launch windows, reserving longer-form creative for "
         "in-session retargeting. Programming should consider regional language "
         "Drama as a primary growth lever in mobile-first markets. Product should "
         "prioritize mobile session quality in markets where mobile share exceeds "
         "70%."),
    ])


def main():
    print(f"Generating PDFs into {OUT}/")
    quarterly_report()
    campaign_summary()
    content_roadmap()
    policy_guidelines()
    audience_behavior()
    print("done.")


if __name__ == "__main__":
    main()