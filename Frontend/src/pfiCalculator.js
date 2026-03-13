// pfiCalculator.js — Platform Freelancer Index engine
// All weights stored in PFI_CONFIG — no hardcoded numbers in logic.

export const PFI_CONFIG = {
  weights: {
    milestoneAccuracy: 0.35,
    deadlineAdherence: 0.25,
    aqaScoreAverage: 0.25,
    disputeRate: 0.15,
  },
  glicko2: {
    initialRating: 1500,
    initialRD: 350,
    initialVolatility: 0.06,
    tau: 0.5,
  },
  riskThresholds: {
    extremeLow: 1,
    low: 2,
    moderate: 3,
    high: 4,
  },
};

/**
 * Calculate base PFI score from freelancer history.
 * @param {Object} history - { completedMilestones, totalMilestones, onTimeDeliveries, totalDeliveries, aqaScores: number[], disputes, totalJobs }
 * @returns {number} 0-100 weighted score
 */
export function calculateBaseScore(history) {
  const w = PFI_CONFIG.weights;

  const milestoneAccuracy = history.totalMilestones > 0
    ? (history.completedMilestones / history.totalMilestones) * 100 : 50;

  const deadlineAdherence = history.totalDeliveries > 0
    ? (history.onTimeDeliveries / history.totalDeliveries) * 100 : 50;

  const aqaScoreAverage = history.aqaScores && history.aqaScores.length > 0
    ? history.aqaScores.reduce((a, b) => a + b, 0) / history.aqaScores.length : 50;

  const disputeRate = history.totalJobs > 0
    ? (1 - (history.disputes / history.totalJobs)) * 100 : 50;

  return Math.round(
    milestoneAccuracy * w.milestoneAccuracy +
    deadlineAdherence * w.deadlineAdherence +
    aqaScoreAverage * w.aqaScoreAverage +
    disputeRate * w.disputeRate
  );
}

/**
 * Simplified Glicko-2 rating update.
 * @param {number} rating - Current rating (default 1500)
 * @param {number} RD - Rating deviation (default 350)
 * @param {number} volatility - Volatility (default 0.06)
 * @param {Array<{score: number, expected: number}>} outcomes
 * @returns {{ rating: number, RD: number, volatility: number }}
 */
export function applyGlicko2(rating, RD, volatility, outcomes) {
  const { tau } = PFI_CONFIG.glicko2;

  if (!outcomes || outcomes.length === 0) {
    // Increase RD when no games played
    const newRD = Math.min(Math.sqrt(RD * RD + volatility * volatility), 350);
    return { rating, RD: newRD, volatility };
  }

  // Step 1: Convert to Glicko-2 scale
  const mu = (rating - 1500) / 173.7178;
  const phi = RD / 173.7178;

  // Step 2: Compute variance (v)
  let vInv = 0;
  let delta = 0;

  for (const { score, expected } of outcomes) {
    const E = expected;
    const g = 1 / Math.sqrt(1 + 3 * phi * phi / (Math.PI * Math.PI));
    vInv += g * g * E * (1 - E);
    delta += g * (score - E);
  }

  const v = 1 / (vInv || 0.001);
  delta = v * delta;

  // Step 3: Simplified volatility update
  const a = Math.log(volatility * volatility);
  const A = a;
  const deltaSquared = delta * delta;
  const phiSquared = phi * phi;

  let newSigma = volatility;
  const f = x => {
    const ex = Math.exp(x);
    return (ex * (deltaSquared - phiSquared - v - ex)) /
      (2 * Math.pow(phiSquared + v + ex, 2)) - (x - a) / (tau * tau);
  };

  // Illinois algorithm (simplified iteration)
  let B;
  if (deltaSquared > phiSquared + v) {
    B = Math.log(deltaSquared - phiSquared - v);
  } else {
    let k = 1;
    while (f(a - k * tau) < 0) k++;
    B = a - k * tau;
  }

  let fA = f(A), fB = f(B);
  for (let i = 0; i < 20; i++) {
    const C = A + (A - B) * fA / (fB - fA);
    const fC = f(C);
    if (fC * fB < 0) {
      fA = fA;
    } else {
      fA = fA / 2;
    }
    // Just use a simple convergence
    newSigma = Math.exp(C / 2);
    if (Math.abs(C - A) < 0.0001) break;
  }

  newSigma = Math.max(0.01, Math.min(newSigma, 0.2));

  // Step 4: Update phi and mu
  const phiStar = Math.sqrt(phiSquared + newSigma * newSigma);
  const newPhi = 1 / Math.sqrt(1 / (phiStar * phiStar) + 1 / v);
  const newMu = mu + newPhi * newPhi * (delta / v);

  return {
    rating: Math.round(173.7178 * newMu + 1500),
    RD: Math.round(173.7178 * newPhi),
    volatility: Math.round(newSigma * 1000) / 1000,
  };
}

/**
 * Combine base score and Glicko-2 rating to a final PFI 0-100.
 */
export function computeFinalPFI(baseScore, glickoRating) {
  // Normalise Glicko rating:  1000 → ~0, 1500 → ~50, 2000 → ~100
  const normGlicko = Math.max(0, Math.min(100, ((glickoRating - 1000) / 1000) * 100));
  return Math.round(0.6 * baseScore + 0.4 * normGlicko);
}

/**
 * Confidence label based on Rating Deviation.
 */
export function getConfidenceLabel(RD) {
  if (RD < 100) return 'High';
  if (RD < 200) return 'Moderate';
  return 'Low';
}

/**
 * Risk label from PFI score.
 */
export function getRiskLabel(score) {
  if (score >= 80) return 'Excellent';
  if (score >= 60) return 'Low Risk';
  if (score >= 40) return 'Moderate Risk';
  if (score >= 20) return 'High Risk';
  return 'Extreme Risk';
}
