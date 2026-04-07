# 🎭 PNPG Demonstration Guide

## Preparing for Your Presentation

### Step 1: Apply Schema (if not done yet)
```bash
python tools/migrate_now.py
```

### Step 2: Generate Demo Threats
```bash
# Generate sample threats for demonstration
python tools/demo_threats.py

# Or generate threats + alerts
python tools/demo_threats.py --with-alerts
```

You'll see output like:
```
============================================================
PNPG Demo Data Generator
============================================================

📝 Inserting 4 demo threats...
  ✓ Threat 1: suspicious.exe (PID 8432) - Malware Connection
  ✓ Threat 2: backdoor.exe (PID 7721) - Data Exfiltration
  ✓ Threat 3: svchost32.exe (PID 9156) - Cryptominer
  ✓ Threat 4: chrome.exe (PID 4832) - Phishing Callback

✅ Inserted 4 threats successfully!

📊 Current Data:
  • 4 active threats
  • 0 active alerts
```

### Step 3: Start the Application
**Terminal 1 - Backend:**
```bash
python -m pnpg.main
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Step 4: Open Dashboard
```
http://localhost:3000
```

---

## 🎬 Demonstration Script

### Demo 1: Kill a Malicious Process

**Scenario:** "A cryptominer has been detected on the system"

1. **Navigate to Threats Tab**
   - Open dashboard
   - Click **"Threats"** tab in the left panel
   - You'll see 4 demo threats listed

2. **Show Threat Details**
   - Point out the **CRITICAL** severity badge (red)
   - Read the threat type: "Cryptominer"
   - Show process name: `svchost32.exe` (suspicious - mimicking system service)
   - Show destination: `mining-pool.suspicious.net`
   - Show confidence: **92%**

3. **Kill the Process**
   - Click the **"⚔️ Kill"** button
   - A confirmation modal appears:
     ```
     ⚔️ Kill Process
     
     Are you sure? This will immediately terminate the process:
     
     svchost32.exe (PID: 9156)
     
     This action cannot be undone.
     ```
   - Click **"⚔️ Kill Process"** to confirm

4. **Show Result**
   - Button changes to **"✓ Killed"** (disabled)
   - Status shows the process was terminated
   - Threat remains in list but marked as remediated

**Talking Points:**
- "PNPG detected a fake system service trying to mine cryptocurrency"
- "One click to terminate the malicious process"
- "Confirmation dialog prevents accidents"
- "Action is logged in the database for audit trail"

---

### Demo 2: Block a Malicious IP

**Scenario:** "A process is attempting to connect to a known malware server"

1. **Select Different Threat**
   - Look at the first threat: "Malware Connection"
   - Severity: **CRITICAL**
   - Process: `suspicious.exe`
   - Destination IP: `185.220.101.45` (known C2 server)

2. **Block the IP**
   - Click the **"🚫 Block IP"** button
   - Confirmation modal appears:
     ```
     🚫 Block IP Address
     
     Are you sure? This will block all traffic to:
     
     185.220.101.45
     
     A Windows Firewall rule will be created and persisted.
     ```
   - Click **"🚫 Block IP"** to confirm

3. **Show Result**
   - Button changes to **"✓ Blocked"** (disabled)
   - IP is now blocked at the firewall level
   - All future traffic to that IP is prevented

**Talking Points:**
- "PNPG can block malicious IPs at the Windows Firewall level"
- "Creates a persistent firewall rule"
- "Prevents any process from reaching that C2 server"
- "Useful when the process keeps respawning"

---

### Demo 3: Suppress a False Positive Alert

**Scenario:** "Zoom is making lots of connections - but it's legitimate"

1. **Switch to Alerts Tab**
   - Click **"Active Alerts"** tab
   - See alert: "connection_rate_exceeded"
   - Process: `zoom.exe`
   - Reason: "Made 127 connections in 60 seconds"

2. **Suppress the Alert**
   - Click **"Suppress"** button
   - Alert immediately disappears from active view
   - Creates a suppression rule

3. **Explain the Result**
   - Alert won't appear again for similar Zoom activity
   - Suppression can be removed later if needed
   - Alternative: Add Zoom to allowlist

**Talking Points:**
- "Sometimes legitimate apps trigger alerts"
- "Suppress removes false positives"
- "One click to clean up the alerts panel"
- "Suppressions are reversible"

---

### Demo 4: Add to Allowlist

**Scenario:** "Chrome always connects to Google - we trust that"

1. **Navigate to Allowlist**
   - Click **"Allowlist"** button in navbar
   - Shows current allowlist rules (empty initially)

2. **Add a Rule**
   - Click **"+ Add Rule"** button
   - Fill in form:
     - Process name: `chrome.exe`
     - Destination hostname: `google.com`
     - Reason: `Google services are trusted`
   - Click **"Add Rule"**

3. **Show Result**
   - New rule appears in table
   - Shows all details (process, domain, reason)
   - Has a "Delete" button for removal

4. **Explain the Impact**
   - Future Chrome → Google connections won't trigger alerts
   - Other Chrome traffic is still monitored
   - Can set expiration dates for temporary rules

**Talking Points:**
- "Allowlist for permanently trusted connections"
- "Flexible: filter by process, IP, or hostname"
- "Optional expiration dates"
- "Full audit trail of what's been allowlisted"

---

### Demo 5: Live Connection Feed

**Scenario:** "See real-time network activity"

1. **Show Live Connections Table**
   - Main panel on the right
   - Real-time scrolling feed
   - Shows: Time, Process, Destination, Country, ASN, IP, Port

2. **Point Out Key Features**
   - **Country flags:** 🇺🇸 🇬🇧 🇩🇪 (visual scanning)
   - **ASN column:** Shows companies (Google, Amazon, Microsoft)
   - **Red rows:** Blocklisted IPs (if any)
   - **Real-time updates:** WebSocket streaming

3. **Pause/Resume**
   - Click **"⏸ Pause"** button
   - Feed freezes (events buffer)
   - Shows buffered count
   - Click **"▶ Resume"** to catch up

**Talking Points:**
- "Every outgoing connection in real-time"
- "See which apps are talking to the internet"
- "Geographic intelligence built-in"
- "Pause feature for investigation"

---

### Demo 6: Analytics Charts

**Scenario:** "Which apps are most active?"

1. **Connections Per App Chart**
   - Bottom left panel
   - Bar chart showing top 10 processes
   - Shows connection counts

2. **Connections Per Second Chart**
   - Bottom right panel
   - Line graph of last 60 seconds
   - Real-time updates

**Talking Points:**
- "Quick visual summary of network activity"
- "Spot unusual patterns at a glance"
- "Useful for capacity planning and troubleshooting"

---

## 🧹 Cleanup After Demo

### Clear Demo Data
```bash
python tools/demo_threats.py --clear
```

This removes all demo threats and alerts, leaving a clean slate.

---

## 🎯 Demo Threat Details Reference

### Threat 1: Malware Connection
- **Severity:** CRITICAL
- **Process:** suspicious.exe (PID 8432)
- **Type:** Malware Connection
- **Destination:** 185.220.101.45 (malicious-c2.example.com)
- **Confidence:** 95%
- **Use for:** Demonstrating IP blocking

### Threat 2: Data Exfiltration
- **Severity:** HIGH
- **Process:** backdoor.exe (PID 7721)
- **Type:** Data Exfiltration
- **Destination:** 103.224.182.245
- **Confidence:** 87%
- **Use for:** Showing high-volume data transfer detection

### Threat 3: Cryptominer
- **Severity:** CRITICAL
- **Process:** svchost32.exe (PID 9156)
- **Type:** Cryptominer
- **Destination:** mining-pool.suspicious.net
- **Confidence:** 92%
- **Use for:** Demonstrating process killing

### Threat 4: Phishing Callback
- **Severity:** HIGH
- **Process:** chrome.exe (PID 4832)
- **Type:** Phishing Callback
- **Destination:** tracking-phish-kit.example
- **Confidence:** 79%
- **Use for:** Showing browser-based threats

---

## 📋 Quick Demo Commands

```bash
# Setup (first time)
python tools/migrate_now.py
python tools/demo_threats.py --with-alerts

# Start app
python -m pnpg.main
cd frontend && npm run dev

# Cleanup
python tools/demo_threats.py --clear

# Show current data
python tools/demo_threats.py --show

# Add just 2 threats
python tools/demo_threats.py --threats-only 2

# Add just alerts
python tools/demo_threats.py --alerts-only 3
```

---

## 💡 Presentation Tips

1. **Before you start:**
   - Run the demo threat generator
   - Open dashboard in browser
   - Test that threats appear in the UI

2. **During presentation:**
   - Start with live connections (show real-time updates)
   - Move to threats tab (dramatic impact)
   - Show kill/block actions
   - Demonstrate allowlist for false positives

3. **Key message:**
   - "See the invisible network activity"
   - "One-click threat response"
   - "Smart false positive handling"
   - "Everything stays local and private"

4. **Common questions:**
   - **Q:** "Does it work on Mac/Linux?"
     - **A:** Windows is primary (Npcap), Linux supported with libpcap
   - **Q:** "Can it block encrypted traffic?"
     - **A:** It sees connections (IPs/ports), not content. Uses metadata for detection.
   - **Q:** "Where does the data go?"
     - **A:** Local PostgreSQL database only. No cloud sync.

---

## ✨ Success!

You're now ready to deliver a compelling PNPG demonstration. The demo threats are realistic, the UI is responsive, and all features work end-to-end.

**Remember:** After the demo, run `python tools/demo_threats.py --clear` to remove demo data!
