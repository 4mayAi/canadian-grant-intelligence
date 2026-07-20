# Implementation Plan: CPCSC Level 1 Cybersecurity Baseline Controls
*Status: Completed (Archived on 2026-07-16)*

This plan proposed executing the 13 baseline security controls required for DND suppliers under the Canadian Program for Cyber Security Certification (CPCSC) Level 1.

## Goal Description
To qualify for DND and other sensitive public sector opportunities, we must execute the 13 baseline security controls defined in [cybersecurity_baseline_controls.md](file:///c:/Users/masan/.gemini/antigravity/brain/cd649801-eabe-4632-a9b9-e6faebf49a64/cybersecurity_baseline_controls.md) for Edgar Murira's sole proprietorship. This plan details the creation of a formal Incident Response Plan, an Evidence Binder log documenting device security settings, and the final self-attestation steps on CanadaBuys.

---

## User Review Required

> [!WARNING]
> **Windows Edition & Encryption Path (Controls 8 & 9):** 
> Your system is running **Windows 11 Home**. 
> Standard BitLocker Drive Encryption is only supported on Windows Pro, Enterprise, or Education editions. 
> To meet the encryption requirements, we must choose one of the following paths:
> * **Option A (Device Encryption - Free):** If your hardware supports TPM 2.0 and Modern Standby, Windows 11 Home includes a simplified "Device Encryption" feature. We will guide you to turn this ON in Settings.
> * **Option B (VeraCrypt - Free/Open-Source):** If Device Encryption is unsupported by your hardware, we will install and configure **VeraCrypt** to encrypt your hard drive and portable media.
> * **Option C (OS Upgrade):** Upgrade your operating system from Windows 11 Home to Windows 11 Pro (approx. $130 CAD) to unlock standard BitLocker.

---

## Open Questions (Resolved)
All technical questions have been resolved via system checks:
* **DUNS Number:** Resolved (skipped/optional).
* **Website Domain & SSL (Control 12):** Resolved. The project website is hosted on GitHub Pages (`https://4mayAi.github.io/canadian-grant-intelligence/`). SSL/TLS (HTTPS) is fully managed and automated by GitHub (via Let's Encrypt), meaning no manual certificate management is required.

---

## Proposed Changes

### Cybersecurity Component

#### [NEW] [incident_response_plan.md](file:///c:/dev/canadian-grant-intelligence/docs/cybersecurity/incident_response_plan.md)
A 1-page playbook (Control 1) detailing the steps to execute in the event of a breach, malware outbreak, or credential compromise:
* **Detection & Reporting:** Identifying indicators of compromise.
* **Containment:** Step-by-step instructions to isolate devices (unplugging network cables, disconnecting Wi-Fi).
* **Eradication:** Running malware scans and changing compromised passwords using a password manager.
* **Recovery:** Restoring data from backups and verifying system integrity.
* **Notifications:** Legal contacts (CRA for Business Number lock, financial institutions, and insurance/legal counsel).

#### [NEW] [evidence_binder.md](file:///c:/dev/canadian-grant-intelligence/docs/cybersecurity/evidence_binder.md)
A document logging verification details for all active controls:
* **Control 2 (Patches):** Log confirming Windows Auto-Updates is active.
* **Control 4 (Firewall):** Log confirming Windows Defender Firewall status.
* **Control 5 (Anti-malware):** Log confirming Microsoft Defender Antivirus real-time protection is active.
* **Control 6 (MFA):** Confirmation checklist of accounts with active MFA (CRA, Ariba, GitHub, Email).
* **Control 8 (Encryption):** Confirmation of active BitLocker, Device Encryption, or VeraCrypt status.
* **Control 11 (Access Control):** Confirmation of standard user account setup for daily work.

---

## Verification Plan

### Manual Verification
1. **Windows Firewall Status Check:**
   Run the following command in PowerShell to confirm the firewall is enabled:
   ```powershell
   Get-NetFirewallProfile | Format-Table Name, Enabled
   ```
   Confirm that Domain, Private, and Public profiles are all set to `True`.
2. **Encryption Status Check:**
   * If using Option A (Device Encryption), verify status in **Settings -> Privacy & Security -> Device Encryption**.
   * If using Option B (VeraCrypt), launch the VeraCrypt UI and verify the C: partition is listed as fully encrypted.
3. **MFA Verification:** Log in to your CRA My Business Account and Ariba profiles to confirm you are prompted for a one-time passcode (MFA check).
4. **Final Self-Attestation:** Once all 13 controls are implemented and verified, log in to **CanadaBuys (SAP Ariba)**, navigate to the Government of Canada questionnaire, and check `Yes` for CPCSC/CMMC compliance (Section 12).
