# Cyber Security Incident Response Plan
**Entity Name:** MAYAI MARKET INTELLIGENCE  
**Operating Structure:** Sole Proprietorship  
**Effective Date:** July 16, 2026  
**Primary Contact:** Edgar Murira  

This document serves as the official, actionable playbook for responding to cybersecurity incidents, satisfying CPCSC Level 1 / CyberSecure Canada Control 1 (Incident Response Plan).

---

## 1. Incident Identification (How to Detect a Breach)
An incident is defined as any unauthorized access, data compromise, or service disruption on business devices or cloud accounts.
*   **Key Indicators:**
    *   Unusual or unauthorized login alerts on Microsoft 365, Azure, CRA My Business Account, or SAP Ariba.
    *   Antivirus/Anti-malware alerts from Windows Security indicating active threat detections.
    *   System files renamed or locked with ransomware extensions.
    *   Suspicious emails sent from business accounts that were not authored by the owner.

---

## 2. Containment and Isolation (First Responders Action)
If a breach or compromise is detected, containment must occur immediately to prevent lateral spread:
1.  **Network Disconnection:** Disconnect the laptop from the local network immediately. Turn OFF Wi-Fi (via Windows Quick Settings) and unplug any physical ethernet cables.
2.  **Device Isolation:** Do not shut down the computer if ransomware is actively encrypting (shutting down can lock keys in RAM or prevent diagnostic recovery); instead, disconnect it from all external storage media (USBs, external drives).
3.  **Account Lockdowns:** If cloud credentials (Microsoft/Google/CRA) are compromised, log in from a separate secure device (e.g., mobile phone on cellular network) and trigger a session sign-out / password change.

---

## 3. Eradication and Remediation
Once isolated, the threat must be neutralized:
1.  **Malware Removal:** Run a full offline scan using Microsoft Defender:
    *   *Path:* Windows Security $\rightarrow$ Virus & threat protection $\rightarrow$ Scan options $\rightarrow$ Microsoft Defender Offline scan.
2.  **Credential Reset:** Reset passwords for all core business and tax portals using the password manager. Enforce new, randomly generated 20+ character passwords.
3.  **Audit Logs:** Check access logs in Azure and Microsoft 365 for unauthorized configurations (such as newly added mail forwarding rules or API keys).

---

## 4. Recovery and Verification
Restoring the business to a secure, operating state:
1.  **Data Restore:** Re-image the device if root access was compromised, then restore database files and workspace source code from the latest secure cloud backup (OneDrive) or encrypted offline backup.
2.  **Integrity Checks:** Verify that Windows Defender Firewall is active and that Device Encryption remains enabled.
3.  **System Patches:** Run Windows Update to ensure all outstanding security patches are applied before reconnecting to the internet.

---

## 5. Escalation & Notification Contact List
In the event of a significant breach (particularly involving client or tax data), contact the following entities immediately:

| Contact Entity | Reason | Contact Method |
| :--- | :--- | :--- |
| **Canada Revenue Agency (CRA)** | Freeze BN/Tax Accounts to prevent tax fraud | Business Enquiries: **1-800-959-5525** |
| **Primary Financial Institution** | Freeze business credit cards & bank accounts | RBC/TD/Scotiabank/BMO customer service line |
| **Public Services & Procurement Canada** | Notify of potential compromise to Ariba profile | CanadaBuys Service Desk |
| **Affected Clients / Co-Bidders** | Inform partners of potential data compromise | Direct phone / encrypted email |
