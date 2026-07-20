# Cyber Security Evidence Binder
**Entity Name:** MAYAI MARKET INTELLIGENCE  
**Operating Structure:** Sole Proprietorship  
**Last Assessment Date:** July 16, 2026  
**Primary Contact:** Edgar Murira  

This document logs the active security settings, verification parameters, and configuration properties of the primary workstation and cloud infrastructure, demonstrating compliance with the Canadian Program for Cyber Security Certification (CPCSC) Level 1.

---

## Active Security Configurations Log

### Control 1: Incident Response Plan
*   **Verification:** A written Incident Response Plan has been established.
*   **Location:** [incident_response_plan.md](file:///c:/dev/canadian-grant-intelligence/docs/cybersecurity/incident_response_plan.md)

### Control 2: Automatically Patch Operating Systems & Applications
*   **Verification:** The Windows Update service (`wuauserv`) is active and running.
*   **Driver Service Status:** `Running`
*   **Configuration:** Auto-download and auto-installation of security definitions and operating system cumulative updates are enabled. Third-party applications (browsers and office software) are configured to auto-update on launch.

### Control 3: Secure Configurations
*   **Verification:** Guest accounts are disabled. WiFi router default administrative credentials have been modified to a secure, password-manager-generated string. Auto-connect to public/unsecured WiFi networks is disabled.

### Control 4: Configure Firewalls and Gateways
*   **Verification:** Windows Defender Firewall profiles are fully active.
*   **Profile Status:**
    *   **Domain Profile:** `Enabled`
    *   **Private Profile:** `Enabled`
    *   **Public Profile:** `Enabled`
*   **Router Gateway:** SPI (Stateful Packet Inspection) Firewall is active on the local network router.

### Control 5: Enable Security Software (Anti-malware)
*   **Verification:** The Microsoft Defender Antivirus Service (`Windefend`) is active and running.
*   **Driver Service Status:** `Running`
*   **Configuration:** Real-time protection, cloud-delivered protection, and automatic definition updates are active. Daily quick scans are scheduled.

### Control 6: Use Strong User Authentication (Passwords & MFA)
*   **Verification:**
    *   **MFA Status:** Enforced across all core accounts (CRA My Business Account, SAP Ariba Network, GitHub, and primary email) utilizing the Microsoft/Google Authenticator app.
    *   **Credentials:** Passwords are generated and stored securely using an encrypted password manager.

### Control 7: Provide Employee Awareness Training
*   **Verification:** Since the business operates as a sole-person consultancy, the owner is the sole operator. Safe browsing practices, phishing verification protocols, and key security practices have been reviewed.

### Control 8: Backup and Encrypt Data
*   **Verification:**
    *   **Local Encryption:** Windows Device Encryption is enabled on the C: drive (fully supported by TPM 2.0 and Modern Standby S0 Low Power Idle).
    *   **Backup Setup:** Core source code repositories and databases are synchronized automatically with an encrypted, MFA-secured cloud storage account (OneDrive), with a monthly offline backup drive stored securely.

### Control 9: Secure Portable Media
*   **Verification:** All USB flash drives and external hard drives containing business data are encrypted using **BitLocker To Go** or encrypted VeraCrypt volumes.

### Control 10: Secure Mobile Devices
*   **Verification:** Smartphone lock screen security is enforced with biometrics (Face ID/Fingerprint) and a strong PIN. Remote wipe ("Find My Device") is active to wipe the device in case of theft.

### Control 11: Establish Access Control (Least Privilege)
*   **Verification:** A dedicated, standard user account (non-administrative) has been established on the workstation for daily B2B consulting, development, and administrative work to prevent unauthorized software installation.

### Control 12: Ensure Website Security
*   **Verification:** The project dashboard is hosted on GitHub Pages (`https://4mayAi.github.io/canadian-grant-intelligence/`). SSL/TLS (HTTPS) is fully managed and automated out-of-the-box by GitHub, enforcing a valid, modern encryption channel for all traffic.

### Control 13: Limit Access to IT Assets (Physical Security)
*   **Verification:** Hardware is operated from a secure, locked home office. Screen lock shortcut (`Win + L`) is invoked every time the workstation is unattended.
