"""
DOM Selectors for Indeed Automation
Covers all known button text variations across Indeed's UI.
"""

# ── Job Search Page (left card list + right detail pane) ──────────────
CARD_SELECTORS = {
    # Each job result card wrapper
    "job_card":       "div.job_seen_beacon",
    # Title link/text inside a card (Indeed uses <a> inside <h2>, or <span>)
    "job_title":      "[class*='jobTitle']",
    # Company name inside a card
    "company_name":   "[data-testid='company-name']",
    # Location text
    "location":       "[data-testid='text-location']",
    # "Easily apply" badge on the card itself (quick filter)
    "easily_apply_badge": ".indeed-apply-badge, [class*='ialbl'], .iaLabel",
}

# ── Right-pane / Detail-pane Apply button ─────────────────────────────
# Indeed uses <button> or <a> with various text.  We match broadly.
APPLY_BUTTON_TEXTS = [
    "Apply with Indeed",
    "Apply now",
    "Easily apply",
    "Apply on company site",      # external – captured but not clicked through
]

# ── Application Form Buttons (inside the new-tab application flow) ────
# POSITIVE buttons – the bot SHOULD click these (in priority order)
POSITIVE_BUTTONS = [
    "Submit your application",    # final submit
    "Submit application",         # variant
    "Submit",                     # short variant
    "Continue applying",          # profile-mismatch: user wants to continue
    "Apply anyway",               # profile-mismatch: user wants to continue
    "Continue",                   # standard next step
    "Next",                       # standard next step
    "Review your application",    # go to review page
    "Review",                     # short variant
]

# NEGATIVE buttons – the bot must NEVER click these
NEGATIVE_BUTTONS = [
    "Return to job search",       # profile-mismatch: go back (skip job)
    "Discard",                    # abandon application
    "Cancel",                     # cancel application
]

# IGNORABLE buttons – present in the UI but should not be clicked
IGNORABLE_BUTTONS = [
    "Add",                        # add cover letter on review page
    "Edit",                       # edit a section on review page
    "Save",                       # save job
]

# ── Success / completion indicators ──────────────────────────────────
SUCCESS_TEXTS = [
    "Your application has been submitted",
    "applied to this job",
    "Application submitted",
    "your application was sent",
]
