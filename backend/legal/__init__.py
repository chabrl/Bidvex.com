"""BidVex legal-text registry — append-only versioned modules.

Every legal document we expose to users (Terms, Privacy, Contractor
Agreement, Refund Policy, etc.) lives here as a separate versioned
Python module. Once shipped, a module is NEVER mutated — a new version
file is created instead. The text-hash of the served version is what
the legal-acceptance audit records persist so we can prove what the
user actually saw.
"""
