# Local Referral Workspace Design

Branch: `codex/local-referral-workspace`

## Goal

Make saved/high-fit jobs more actionable by showing user-managed local referral contacts for the company.

## Problem

The product can discover roles, review fit, improve the resume, and prepare an application packet. It still does not answer the practical local question: who do I already know at this company?

## V1 Scope

- Add local `contacts` records owned by the user.
- Add company-scoped `referral_contacts` links.
- Add an admin/local form to add a contact for a company.
- Show matching contacts on job detail.
- Keep contact data local and manually entered.

## Safety Boundary

- No LinkedIn scraping, contact discovery, email, messaging, or outreach automation.
- No contact import from external accounts in V1.
- Contact notes are local and should not be exported in saved-job CSV.
- Do not store cookies, tokens, browser profiles, or hidden-session data.

## Acceptance Criteria

- Schema includes contacts and company contact links.
- User can add a contact for a company through a local form.
- Job detail shows local contacts for the job company.
- Contacts for other companies do not render.
- Private resume text and LLM internals do not render in referral sections.
- Full tests pass.

## Later Scope

- CSV contact import.
- Referral status on application packets.
- User-written outreach drafts with explicit consent.
- Live network discovery only if authorized and policy-compliant.
