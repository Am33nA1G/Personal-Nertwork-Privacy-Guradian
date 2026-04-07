# 🎯 Quick Demo Reference Card

## 🚀 Setup (Before Demo)

```bash
# 1. Apply schema (if needed)
python tools/migrate_now.py

# 2. Generate demo threats
python tools/demo_threats.py --with-alerts

# 3. Start backend (Terminal 1)
python -m pnpg.main

# 4. Start frontend (Terminal 2)
cd frontend && npm run dev

# 5. Open browser
http://localhost:3000
```

---

## 🎬 5-Minute Demo Flow

### 1. Live Connections (30 seconds)
**Show:** Real-time network feed, country flags, company names
**Say:** "See every connection your computer makes in real-time"

### 2. Kill a Threat (60 seconds)
**Navigate:** Threats tab → Find "Cryptominer" threat
**Action:** Click "⚔️ Kill" → Confirm
**Say:** "One click to terminate malicious processes"

### 3. Block an IP (60 seconds)
**Navigate:** Same tab → Find "Malware Connection"
**Action:** Click "🚫 Block IP" → Confirm
**Say:** "Block malicious servers at the firewall level"

### 4. Suppress Alert (30 seconds)
**Navigate:** Alerts tab → Find "Zoom" alert
**Action:** Click "Suppress"
**Say:** "Smart false positive handling"

### 5. Allowlist (60 seconds)
**Navigate:** Click "Allowlist" button
**Action:** Add rule for Chrome + Google
**Say:** "Trust legitimate connections permanently"

### 6. Charts (30 seconds)
**Show:** Bottom panels
**Say:** "Visual analytics for network activity"

---

## 📊 Demo Threats Available

| Process | Type | Severity | Best For |
|---------|------|----------|----------|
| `svchost32.exe` | Cryptominer | CRITICAL | **Kill demo** ⚔️ |
| `suspicious.exe` | Malware C2 | CRITICAL | **Block IP demo** 🚫 |
| `backdoor.exe` | Data Exfiltration | HIGH | Volume detection |
| `chrome.exe` | Phishing | HIGH | Browser threats |

---

## 🧹 Cleanup

```bash
python tools/demo_threats.py --clear
```

---

## 💬 Key Talking Points

✅ **Privacy-first:** All data stays local  
✅ **Real-time:** See connections as they happen  
✅ **Actionable:** Kill/block threats instantly  
✅ **Smart:** Suppress false positives easily  
✅ **Visual:** Charts and geographic data  

---

## 🎓 Answer Common Questions

**Q: Does it replace antivirus?**  
A: No, it complements AV. Focus is network visibility & control.

**Q: Can it decrypt HTTPS?**  
A: No, sees connection metadata (IP/port), not content.

**Q: Works on Mac/Linux?**  
A: Windows primary (Npcap), Linux via libpcap, Mac limited.

**Q: Cloud-based?**  
A: No, 100% local. PostgreSQL runs on your machine.

---

## 🔧 Troubleshooting

**No threats showing?**
```bash
python tools/demo_threats.py --show
```

**Need to regenerate?**
```bash
python tools/demo_threats.py --clear
python tools/demo_threats.py --with-alerts
```

**Backend not running?**
```bash
python -m pnpg.main
```

---

## ✨ You're Ready!

Print this card for quick reference during your presentation.
