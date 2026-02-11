# DRI Panel Member Change Log

This file tracks all changes to the DRI panel composition, including additions, removals, and replacements.

---

## 2026-02-10: Initial Panel Configuration

**Event:** Panel established for DRI MVP launch

**Panel Members:**
1. **Duquesne Family Office** (CIK 0001536411) - Tactical, 30d halflife
   - AUM: ~$4B
   - Rationale: Stanley Druckenmiller's family office, legendary macro trader

2. **Pershing Square Capital** (CIK 0001336528) - Structural, 60d halflife
   - AUM: ~$14B
   - Rationale: Bill Ackman's concentrated activism, willing to hold cash

3. **Bridgewater Advisors** (CIK 0001600319) - Structural, 60d halflife
   - AUM: ~$1.5B
   - Rationale: Ray Dalio's discretionary book, macro-driven flexible positioning

4. **Third Point** (CIK 0001040273) - Structural, 60d halflife
   - AUM: ~$9B
   - Rationale: Dan Loeb's activist fund, event-driven with flexible cash positioning

---

## 2026-02-10: ValueAct Replacement

**Removed:** ValueAct Capital (CIK 0001351069)
**Reason:** Historical 13F filings (2006-2007) incompatible with modern XML parser. SEC returned 503 errors and timeouts on old format files.

**Added:** Third Point (CIK 0001040273)
**Rationale:** Activist/event-driven with flexible positioning, excellent filing history (115 quarters), modern XML format compatible with parser.

**Investigation:**
- Attempted to fetch ValueAct data for 20 quarters
- Encountered filing format changes in 2006-2007 era
- XML structure different from modern 13F-HR format (infotable.xml vs legacy formats)
- SEC server 503 errors on historical files
- Decision: Replace rather than add legacy format parsing support

**Data Quality:**
- Third Point: All filings have 1000x unit errors (corrected automatically by sensor.py outlier detection)
- Verified with `dri sensor fetch 0001040273 --quarters 8`
- Successfully computed exposure history with corrections applied

---

## Future Rotation Candidates

**Vetted for potential rotation:**
- Elliott Management (CIK 0001567228) - Paul Singer, activist/macro
- Appaloosa Management (CIK 0001029160) - David Tepper, tactical macro
- Baupost Group (CIK 0001061768) - Seth Klarman, value/macro
- Viking Global (CIK 0001103804) - Andreas Halvorsen, long/short
- Soros Fund Management (CIK 0001029330) - Soros family office, macro

---

## Notes

- All panel changes should be documented here with rationale
- Include investigation details for future reference
- Track data quality issues discovered during evaluation
- Maintain list of vetted candidates for quick rotation if needed

---

## 2026-02-11: Guy Spier Added ✅

**Added:** Aquamarine Zurich (CIK 0001953324)

**Action Taken:** Updated panel configuration and validated pipeline run with 5 panel members.
