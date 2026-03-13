# Prompt 2 Implementation Plan — PFI, Agent Scorer, Analytics, HITL

Extends the Prompt 1 codebase. No new scaffold — all files either added to `src/` or extended in-place. State shape, EscrowContract, and geminiApi.js are already built. Prompt 2 fills in the stubbed functions and adds 4 new components.

---

## Files Modified in Prompt 1 Codebase

### `src/geminiApi.js` — Add 2 stubbed functions

**`scoreFreelancerMatch(skills, domain, apiKey)`**
```
You are a talent matching algorithm.
Given a freelancer's skills and a required project domain, return a fit score.

FREELANCER SKILLS: {skills as comma-separated string}
REQUIRED DOMAIN: {domain}

Return ONLY valid JSON: { "score": 0.0-1.0 }
```

**`detectBias(ratingHistory, apiKey)`**
```
You are a bias detection algorithm for a freelancer reputation system.
Analyze this rating history array for patterns of recency bias, feedback loops, or score manipulation.

RATING HISTORY: {JSON.stringify(ratingHistory)}

Return ONLY valid JSON:
{
  "biasDetected": boolean,
  "biasType": "recency_bias" | "feedback_loop" | "score_manipulation" | null,
  "confidence": 0-100,
  "recommendation": string
}
```

---

### `src/store/actions.js` — Add action types

```js
SET_PFI_SCORE:      'SET_PFI_SCORE',
SET_ASSIGN_SCORES:  'SET_ASSIGN_SCORES',
PUSH_HITL:          'PUSH_HITL',
RESOLVE_HITL:       'RESOLVE_HITL',
UPDATE_PFI_CONFIG:  'UPDATE_PFI_CONFIG',
```

---

### `src/store/reducer.js` — Add state fields + handle new actions

Add to `initialState`:
```js
pfiScores:    {},        // freelancerId → { score, RD, volatility, history[] }
assignScores: [],        // [{ freelancerId, score, domainMatch }]
hitlQueue:    [],        // AQA results awaiting human decision
pfiConfig:    PFI_CONFIG // imported from pfiCalculator.js
```

Handle new actions:
- `SET_PFI_SCORE` — merge `{ freelancerId, pfiData }` into `pfiScores`
- `SET_ASSIGN_SCORES` — replace `assignScores` array
- `PUSH_HITL` — append `{ milestoneIndex, aqaResult, timestamp }` to `hitlQueue`
- `RESOLVE_HITL` — remove resolved item from `hitlQueue` by `milestoneIndex`
- `UPDATE_PFI_CONFIG` — deep merge payload into `pfiConfig`

---

### `src/App.jsx` — Add nav items + render new views

Add to left sidebar nav:
- PFI Dashboard → sets `activeView: 'pfi'`
- Analytics → sets `activeView: 'analytics'`

Add to center panel routing:
```jsx
activeView === 'pfi'       → <PFIDashboard state={state} dispatch={dispatch} />
activeView === 'analytics' → <AnalyticsPanel state={state} dispatch={dispatch} />
```

HITL queue badge on sidebar nav showing `state.hitlQueue.length` if > 0.

---

### `src/components/FreelancerDashboard.jsx` — Wire HITL threshold

In the AQA result handler, after `evaluateSubmission()` resolves:
- If `overallScore > 60` → call `escrow.releasePayment(index, result.proRatedPercentage)`, dispatch `SET_ESCROW` + `APPEND_LEDGER`
- If `overallScore < 40` → call `escrow.initiateRefund(index, result.detailedFeedback)`, dispatch `SET_ESCROW` + `APPEND_LEDGER`
- If `overallScore >= 40 && overallScore <= 60` → dispatch `PUSH_HITL` with full AQA result, do NOT touch escrow

After any completed project milestone, recalculate PFI for the assigned freelancer and dispatch `SET_PFI_SCORE`.

---

### `src/components/EmployerDashboard.jsx` — Trigger AgentScorer

After escrow is confirmed and `state.freelancers` is non-empty, render `<AgentScorer />` in the center panel below the DAG.

---

## New Files

### `src/pfiCalculator.js`

```js
export const PFI_CONFIG = {
  weights: {
    milestoneAccuracy:  0.35,
    deadlineAdherence:  0.25,
    aqaScoreAverage:    0.25,
    disputeRate:        0.15
  },
  glicko2: {
    initialRating:     1500,
    initialRD:          350,
    initialVolatility:  0.06,
    tau:                0.5
  },
  riskThresholds: {
    extremeLow: 1,
    low:        2,
    moderate:   3,
    high:       4
  }
}
```

**`calculateBaseScore(freelancerHistory, config)`**

`freelancerHistory` shape:
```js
{
  totalMilestones:     number,
  completedFull:       number,   // FULLY_COMPLETED count
  completedOnTime:     number,
  aqaScores:           number[], // 0-100 per milestone
  disputes:            number    // count of REFUND_INITIATED
}
```

Calculation:
```
milestoneAccuracy = completedFull / totalMilestones
deadlineAdherence = completedOnTime / totalMilestones
aqaScoreAverage   = mean(aqaScores) / 100
disputeRate       = 1 - (disputes / totalMilestones)

baseScore = (milestoneAccuracy × config.weights.milestoneAccuracy
           + deadlineAdherence × config.weights.deadlineAdherence
           + aqaScoreAverage   × config.weights.aqaScoreAverage
           + disputeRate       × config.weights.disputeRate) × 100
```

Returns `number` 0-100.

---

**`applyGlicko2(rating, RD, volatility, outcomes, config)`**

`outcomes` shape: `[{ score: 0-1, expected: 0-1 }]`

Steps (standard Glicko-2 algorithm):
1. Convert rating and RD to Glicko-2 scale: `μ = (rating - 1500) / 173.7178`, `φ = RD / 173.7178`
2. Compute `v` (estimated variance) from outcomes
3. Compute `Δ` (estimated improvement) from outcomes
4. Update volatility `σ'` using Illinois algorithm with `config.glicko2.tau`
5. Update `φ*` = `sqrt(φ² + σ'²)`
6. Update `φ'` = `1 / sqrt(1/φ*² + 1/v)`
7. Update `μ'` = `μ + φ'² × sum of outcome deltas`
8. Convert back: `newRating = 173.7178 × μ' + 1500`, `newRD = 173.7178 × φ'`

Returns `{ rating: number, RD: number, volatility: number }`.

---

**`computeFinalPFI(baseScore, glickoRating, config)`**

```
normalised = (glickoRating - config.glicko2.initialRating) / 400
clipped    = Math.max(-1, Math.min(1, normalised))
adjusted   = baseScore + (clipped × 15)
finalPFI   = Math.max(0, Math.min(100, adjusted))
```

Returns `number` 0-100.

---

**`getConfidenceLabel(RD)`**
- RD < 100 → `"High"`
- RD < 200 → `"Moderate"`
- RD >= 200 → `"Low"`

**`getRiskLabel(score)`**
- score >= 85 → `"Excellent"`
- score >= 70 → `"Low Risk"`
- score >= 50 → `"Moderate Risk"`
- score >= 30 → `"High Risk"`
- score < 30  → `"Extreme Risk"`

---

### `src/components/PFIDashboard.jsx`

Reads `state.freelancers`, `state.pfiScores`, `state.pfiConfig`.

**Per-freelancer card contains:**

1. **Circular SVG gauge** — 200×200 viewBox, two `<circle>` elements:
   - Background ring: full circumference, stroke `#1A1F2E`
   - Score arc: `stroke-dasharray` = `(pfi/100) × circumference`, `stroke-dashoffset` = 0, color: red if < 40, amber if < 70, green if >= 70
   - Center text: PFI value + confidence label

2. **Rating Deviation bar** — horizontal bar, width = `(RD / 350) × 100%`, label: `"RD: {value} — {confidenceLabel}"`

3. **Volatility sparkline** — inline SVG 120×40, plots last 10 `history[]` AQA scores as a polyline, no axes, stroke cyan

4. **Bias detection badge** — calls `detectBias(pfiScores[id].history, state.apiKey)` on mount, shows warning icon + biasType if `biasDetected`, green check if clean

**Leaderboard table** below cards:
- Columns: Rank | Name | PFI Score | Confidence | Risk Label | Bias Status
- Sorted by `pfiScores[id].score` descending
- Rows color-coded: green if score >= 70, amber if >= 50, red if < 50

---

### `src/components/AnalyticsPanel.jsx`

All charts are inline SVG. Reads from `state` only — no props beyond `state` and `dispatch`.

**Summary row — 4 stat cards:**
- Active Projects: `state.projects.filter(p => p.status !== 'COMPLETED').length`
- Total Funds in Escrow: sum of `escrow.totalFunds` across non-completed projects, formatted as `$X,XXX`
- Average AQA Score: mean of all `overallScore` values in `state.aqaResults`
- Milestones Paid: count of `PAYMENT` events in `state.ledger`

**Milestone completion funnel:**
- Stages: Activated → Submitted → AQA Passed → Paid
- Counts derived from `state.milestones[].status` and `state.ledger`
- SVG: horizontal trapezoid bars, each narrower than the last, percentage label on each bar

**PFI histogram:**
- Bins: 0-10, 10-20, … 90-100
- Count of freelancers per bin from `state.pfiScores`
- SVG: vertical bars, 500×200 viewBox, x-axis labels, cyan fill, hover title with count

**Escrow timeline:**
- All `state.ledger` events plotted on a horizontal SVG timeline
- Each event is a circle: cyan for DEPOSIT, green for PAYMENT, red for REFUND, grey for STATE_CHANGE
- Hover/title shows `event` text and `timestamp`
- Sorted by timestamp ascending

All 4 charts recompute on every render — no internal state, no useEffect, pure derivation from `state`.

---

### `src/components/AgentScorer.jsx`

Receives `state` and `dispatch`. Triggered when a project is confirmed.

**On mount:**
1. Identify `projectDomain` from the first milestone's `domain` field
2. For each freelancer in `state.freelancers`:
   - Call `scoreFreelancerMatch(freelancer.skills, projectDomain, state.apiKey)`
   - Retrieve `pfi = state.pfiScores[freelancer.id]?.score ?? 50`
   - Compute `totalScore = (0.6 × domainMatch) + (0.4 × pfi / 100)`
3. Sort by `totalScore` descending
4. Dispatch `SET_ASSIGN_SCORES` with full ranked array

**Render:**
- Ranked list: Rank # | Name | Skills tags | Domain Match % | PFI Score | Total Score bar
- Total score bar: filled width = `totalScore × 100%`, color gradient cyan→green
- Assign button on each row → sets `project.assignedFreelancerId`, dispatches `SET_PROJECT`
- Loading state: spinner + "Scoring freelancers..." while API calls in flight (use `Promise.all`)

---

### `src/components/HITLOverride.jsx`

Renders for each item in `state.hitlQueue`. If queue is empty, renders nothing.

**Per-item card contains:**
1. Header: milestone title, AQA overall score badge (amber), label "Human Review Required"
2. Criterion table: same as AQAReport — criterion | met icon | score | feedback
3. AI recommendation pill: `paymentRecommendation` value from AQA result
4. Detailed feedback paragraph
5. Reason input: `<textarea>` required before any action button activates

**Four action buttons:**
- **Approve AI Decision** → executes whatever `paymentRecommendation` says (calls `releasePayment` or `initiateRefund`)
- **Override: Full Pay** → calls `escrow.releasePayment(milestoneIndex, 100)`
- **Override: Refund** → calls `escrow.initiateRefund(milestoneIndex, reason)`
- **Request Resubmission** → resets milestone status to `IN_PROGRESS`, does not move escrow funds

All actions:
- Dispatch `SET_ESCROW` with updated contract state
- Dispatch `APPEND_LEDGER` with `{ event: 'HUMAN_OVERRIDE', type: override type, reason: textarea value }`
- Dispatch `RESOLVE_HITL` with `milestoneIndex`
- Trigger PFI recalculation for assigned freelancer, dispatch `SET_PFI_SCORE`

---

## PFI Recalculation Trigger Points

PFI must be recalculated and dispatched whenever:
- A milestone transitions to `PAID_FULL` or `PAID_PARTIAL`
- A milestone transitions to `REFUND_INITIATED`
- A HITL override is resolved

Recalculation sequence:
1. Build `freelancerHistory` from `state.milestones` + `state.aqaResults` + `state.ledger` for that freelancer
2. Call `calculateBaseScore(freelancerHistory, state.pfiConfig)`
3. Get current `{ rating, RD, volatility }` from `state.pfiScores[id]` or use `PFI_CONFIG.glicko2` defaults
4. Build `outcomes` array from `state.aqaResults` — `score = overallScore / 100`, `expected = 0.5`
5. Call `applyGlicko2(rating, RD, volatility, outcomes, state.pfiConfig)`
6. Call `computeFinalPFI(baseScore, newRating, state.pfiConfig)`
7. Dispatch `SET_PFI_SCORE` with `{ freelancerId, pfiData: { score, RD: newRD, volatility: newVolatility, history: [...existing, { score, timestamp }] } }`

---

## Export Report

Add "Export Report" button to App.jsx header bar.

On click, construct and download a JSON file:
```js
{
  exportedAt:   new Date().toISOString(),
  projects:     state.projects,
  milestones:   state.milestones,
  aqaResults:   state.aqaResults,
  ledger:       state.ledger,
  pfiScores:    state.pfiScores,
  assignScores: state.assignScores,
  pfiConfig:    state.pfiConfig
}
```

Download via:
```js
const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
const url  = URL.createObjectURL(blob)
const a    = document.createElement('a')
a.href     = url
a.download = `bitbybit-report-${Date.now()}.json`
a.click()
URL.revokeObjectURL(url)
```

---

## Verification Plan

| # | Test | Expected Result |
|---|---|---|
| 1 | Submit work with AQA score > 60 | Escrow auto-releases payment, ledger shows PAYMENT event |
| 2 | Submit work with AQA score < 40 | Escrow auto-initiates refund, ledger shows REFUND event |
| 3 | Submit work with AQA score 40-60 | HITLOverride card appears, no escrow action fires |
| 4 | HITL: enter reason → Override Full Pay | Full payment released, reason in ledger, card removed from queue |
| 5 | HITL: Request Resubmission | Milestone resets to IN_PROGRESS, escrow unchanged |
| 6 | Navigate to PFI tab | Gauges render for all freelancers, RD bars and sparklines visible |
| 7 | Complete a milestone | PFI gauge updates immediately for assigned freelancer |
| 8 | PFI bias detection | Badge shows warning if biasDetected, green check if clean |
| 9 | Navigate to Analytics tab | All 4 charts render with live data |
| 10 | Complete a payment | Funnel and timeline update without page refresh |
| 11 | Assign freelancer via AgentScorer | Project shows assigned freelancer, scores persist in state |
| 12 | Export Report | JSON downloads with all 8 state fields populated |
| 13 | Refresh browser | pfiScores, hitlQueue, assignScores all restored from localStorage |
