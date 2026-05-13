"""
iter211 Step 1 — Universal Business Documentation terminology.

Verifies that the Quebec-specific "NEQ Proof Document" / "Numéro d'entreprise
du Québec" copy has been replaced with the universal Canadian terms across
the user-facing surface.

Scope: locale files + key user-facing JS components. Internal references to
the `partner_neq` DB field are PRESERVED (it remains a valid identifier for
QC-incorporated partners).
"""


def test_en_locale_partner_form_uses_universal_term():
    with open("/app/frontend/src/locales/en.json", "r") as f:
        body = f.read()
    assert '"formNeqFileLabel": "Federal or Provincial Business Registration Document"' in body
    assert '"formNeqLabel": "Business Registration Number (Federal or Provincial)"' in body
    assert "NEQ Proof Document" not in body, "EN locale still references the old Quebec-only label"
    assert "GST/QST or HST applied" in body, \
        "EN locale fee summary must mention HST for non-QC provinces (iter211 Step 2)"


def test_fr_locale_partner_form_uses_universal_term():
    with open("/app/frontend/src/locales/fr.json", "r") as f:
        body = f.read()
    assert "Document d'enregistrement d'entreprise fédéral ou provincial" in body
    assert "Document de preuve NEQ" not in body, \
        "FR locale still references the old Quebec-only label"
    # FR partner fee summary should mention HST too
    assert "TVH" in body, "FR locale must mention TVH (HST) for non-QC provinces"


def test_legal_page_universal_partner_verification():
    with open("/app/frontend/src/pages/LegalPage.js", "r") as f:
        body = f.read()
    assert "federal or provincial business registration" in body
    assert "business registration (NEQ)" not in body, \
        "LegalPage still references Quebec-only verification text"


def test_auth_page_partner_note_universal():
    with open("/app/frontend/src/pages/AuthPage.js", "r") as f:
        body = f.read()
    assert "federal or provincial business registration" in body
    assert "manual NEQ" not in body


def test_resubmit_panel_universal_label():
    with open("/app/frontend/src/components/ResubmitApplicationPanel.jsx", "r") as f:
        body = f.read()
    # English label
    assert "Business Registration Document" in body
    # French label
    assert "Document d'enregistrement" in body


def test_backend_partner_email_uses_universal_term():
    with open("/app/backend/routes/partners.py", "r") as f:
        body = f.read()
    assert "business registration document" in body or "Business Registration Document" in body
    assert "NEQ Proof</a>" not in body, "Backend partner email still says 'NEQ Proof'"
