# Slow-network (2G) test

**Question:** does HealthConnect still work for a CHV whose phone only has 2G?

**Answer:** yes for records, risk checks and referrals, even on the slowest 2G (GPRS). Photos work but are slow on GPRS. Video needs at least EDGE, and audio-only mode is the right choice on 2G.

This was a **simulated** test on a laptop, not a test on real Ghanaian phones (see "Limits" at the end).

## How we tested (11 November 2026)

- **The real app**: the production build (the same compressed files CloudFront serves), not the development server.
- **Slow networks**: Chrome's network throttling (the same tool as the DevTools "Network" speed menu), driven by a Playwright script. Each run starts with an empty cache, like a brand-new phone.
- **The user**: a CHV (`chv1`) signs in, opens a patient and adds a photo.

| Network | Download | Upload | Round trip (delay) |
|---|---|---|---|
| Office Wi-Fi (no limit) | fast | fast | ~0 ms |
| 3G (slow) | 400 kbps | 400 kbps | 400 ms |
| 2G EDGE | 240 kbps | 200 kbps | 840 ms |
| 2G GPRS (worst case) | 50 kbps | 20 kbps | 500 ms |

## Results (seconds)

| Step | Wi-Fi | 3G slow | 2G EDGE | 2G GPRS |
|---|---|---|---|---|
| **First visit ever** (download the app, 173 KB) | 0.1 | 4.4 | 7.7 | 29.6 |
| **Sign in** until the patient list shows (8–11 KB) | 0.2 | 1.4 | 2.3 | 4.3 |
| **Open a patient** | 0.05 | 0.5 | 0.9 | 0.6 |
| **Upload a photo**, normal size (1280 px, ~190 KB) | 0.02 | 5.6 | 11.3 | 104.6 |
| **Upload a photo**, 2G size (800 px, ~100–130 KB) | | | 6.5 | 55.9 |
| **Come back later** (app saved on the phone, only data downloaded: 8 KB) | 0.05 | 1.3 | 2.9 | 3.9 |
| **No signal at all**: does the app open? | ✅ | ✅ | ✅ | ✅ |

## What this shows

1. **The app is small.** It is 568 KB as files but 173 KB as sent (compressed). That's under 30 s on GPRS, and only once: after that the service worker (the part of a PWA that saves the app on the phone) loads it from the phone.
2. **Daily work uses very little data.** Signing in and loading the patient list is about 10 KB. Opening a patient takes under a second, even on GPRS.
3. **Offline works.** With no signal the app still opens, and the risk check runs on the phone (see README §4).
4. **Photos were the weak spot.** A normal photo took 105 s to upload on GPRS.

## What we changed because of the test

- **Smaller photos on 2G** ([frontend/src/PhotosPanel.jsx](../frontend/src/PhotosPanel.jsx)). Android phones report their network type (the Network Information API). On 2G the app now shrinks photos to 800 px instead of 1280 px.
  - Checked with Chrome forced to report 2G: a 960 KB camera photo was sent as **130 KB** (800×600), against **236 KB** (1280×960) on a normal network.
  - On GPRS that roughly halves the upload, from 105 s to 56 s.
  - Phones that don't report a network type (iPhones) keep the normal size.
- **Bug found and fixed.** The server's CORS rules (which other websites may call the API from a browser) only allowed GET and POST. So on a laptop set-up, deleting a photo, a vaccine record or a fingerprint was blocked. The live AWS site was not affected, because the website and the API share one CloudFront address there. DELETE is now allowed ([backend/main.py](../backend/main.py)).

## Video calls on 2G (worked out, not measured)

Chrome's throttling does not slow down WebRTC video, so this is a calculation, not a measurement:

| Call type | Data needed | 2G EDGE (~200 kbps up) | 2G GPRS (~20 kbps up) |
|---|---|---|---|
| Video (our cap: 150 kbps, 320×240) | ~150 kbps each way | Borderline: usable when signal is good | ❌ Not possible |
| Audio-only mode | ~30 kbps each way | ✅ | ⚠️ Very poor |

So on 2G a CHV should use **audio-only**. For anything urgent, the referral and SMS work on every network.

## Limits (honest)

- **Simulated, not real.** Real 2G also drops connections and changes speed from minute to minute. The next step is a field test: two Android phones on MTN and Telecel 2G in the Upper East, timing the same steps.
- **Phones report their network type from real measurements.** On a real EDGE link a phone may say "3g" (Chrome only reports "2g" when the round trip is 1.4 s or slower), so the smaller photo size is used mostly on the worst connections.
- **The server was on the same laptop.** The live site adds the trip to AWS Stockholm (eu-north-1), about 150–250 ms more per request from Ghana.
