// EscrowContract.js — Simulated Smart Contract State Machine
// States: CREATED → FUNDED → MILESTONE_ACTIVE → WORK_SUBMITTED → AQA_REVIEW →
//         PAID_PARTIAL | PAID_FULL | REFUND_INITIATED → COMPLETED

export class EscrowContract {
  constructor({ projectId, totalFunds, milestones, employerId, freelancerId }) {
    this.projectId = projectId;
    this.totalFunds = totalFunds;
    this.lockedFunds = 0;
    this.releasedFunds = 0;
    this.refundedFunds = 0;
    this.milestones = milestones.map((m, i) => ({
      ...m,
      index: i,
      status: 'PENDING',
      submission: null,
      aqaResult: null,
      paymentAmount: 0,
      paymentReleased: 0,
    }));
    this.employerId = employerId;
    this.freelancerId = freelancerId;
    this.state = 'CREATED';
    this.ledger = [];
    this.createdAt = new Date().toISOString();
    this._log('CONTRACT_CREATED', null, 'STATE_CHANGE',
      `Contract created for project ${projectId} with ${milestones.length} milestones`);
  }

  _log(event, amount, type, details) {
    this.ledger.push({
      timestamp: new Date().toISOString(),
      event,
      amount,
      type,
      details: details || event,
      contractState: this.state,
    });
  }

  _allocateMilestoneBudgets() {
    const totalComplexity = this.milestones.reduce((s, m) => s + (m.complexityScore || 5), 0);
    this.milestones.forEach(m => {
      m.paymentAmount = Math.round(
        (this.totalFunds * ((m.complexityScore || 5) / totalComplexity)) * 100
      ) / 100;
    });
  }

  depositFunds(amount) {
    if (this.state !== 'CREATED') {
      throw new Error(`Cannot deposit: contract is in state ${this.state}`);
    }
    if (amount <= 0) throw new Error('Deposit amount must be positive');
    this.lockedFunds = amount;
    this.totalFunds = amount;
    this.state = 'FUNDED';
    this._allocateMilestoneBudgets();
    this._log('FUNDS_DEPOSITED', amount, 'DEPOSIT',
      `$${amount.toLocaleString()} locked in escrow`);
    return this.getState();
  }

  activateMilestone(index) {
    if (this.state !== 'FUNDED' && this.state !== 'MILESTONE_ACTIVE') {
      // Also allow from PAID_PARTIAL or PAID_FULL states for next milestones
      if (!['PAID_PARTIAL', 'PAID_FULL'].includes(this.state)) {
        throw new Error(`Cannot activate milestone: contract is in state ${this.state}`);
      }
    }
    const ms = this.milestones[index];
    if (!ms) throw new Error(`Milestone ${index} does not exist`);
    if (ms.status !== 'PENDING') throw new Error(`Milestone ${index} is already ${ms.status}`);
    ms.status = 'IN_PROGRESS';
    this.state = 'MILESTONE_ACTIVE';
    this._log('MILESTONE_ACTIVATED', null, 'STATE_CHANGE',
      `Milestone ${index + 1}: "${ms.title}" activated`);
    return this.getState();
  }

  submitWork(milestoneIndex, submissionText) {
    const ms = this.milestones[milestoneIndex];
    if (!ms) throw new Error(`Milestone ${milestoneIndex} does not exist`);
    if (ms.status !== 'IN_PROGRESS') {
      throw new Error(`Milestone ${milestoneIndex} must be IN_PROGRESS to submit work`);
    }
    ms.submission = submissionText;
    ms.status = 'WORK_SUBMITTED';
    this.state = 'WORK_SUBMITTED';
    this._log('WORK_SUBMITTED', null, 'STATE_CHANGE',
      `Work submitted for milestone ${milestoneIndex + 1}: "${ms.title}"`);
    return this.getState();
  }

  setAqaReview(milestoneIndex) {
    const ms = this.milestones[milestoneIndex];
    if (!ms) throw new Error(`Milestone ${milestoneIndex} does not exist`);
    ms.status = 'AQA_REVIEW';
    this.state = 'AQA_REVIEW';
    this._log('AQA_REVIEW_STARTED', null, 'STATE_CHANGE',
      `AQA review started for milestone ${milestoneIndex + 1}: "${ms.title}"`);
    return this.getState();
  }

  releasePayment(milestoneIndex, percentComplete) {
    const ms = this.milestones[milestoneIndex];
    if (!ms) throw new Error(`Milestone ${milestoneIndex} does not exist`);
    const payoutRatio = Math.min(percentComplete, 100) / 100;
    const payout = Math.round(ms.paymentAmount * payoutRatio * 100) / 100;
    ms.paymentReleased = payout;
    ms.status = percentComplete >= 100 ? 'PAID_FULL' : 'PAID_PARTIAL';
    this.releasedFunds += payout;
    this.lockedFunds -= payout;
    this.state = ms.status;
    this._log(ms.status === 'PAID_FULL' ? 'FULL_PAYMENT_RELEASED' : 'PARTIAL_PAYMENT_RELEASED',
      payout, 'PAYMENT',
      `$${payout.toLocaleString()} released for milestone ${milestoneIndex + 1} (${percentComplete}% complete)`);
    this._checkCompletion();
    return this.getState();
  }

  initiateRefund(milestoneIndex, reason) {
    const ms = this.milestones[milestoneIndex];
    if (!ms) throw new Error(`Milestone ${milestoneIndex} does not exist`);
    const refundAmount = ms.paymentAmount - ms.paymentReleased;
    ms.status = 'REFUND_INITIATED';
    this.refundedFunds += refundAmount;
    this.lockedFunds -= refundAmount;
    this.state = 'REFUND_INITIATED';
    this._log('REFUND_INITIATED', refundAmount, 'REFUND',
      `$${refundAmount.toLocaleString()} refunded for milestone ${milestoneIndex + 1}: ${reason}`);
    this._checkCompletion();
    return this.getState();
  }

  _checkCompletion() {
    const allDone = this.milestones.every(m =>
      ['PAID_FULL', 'PAID_PARTIAL', 'REFUND_INITIATED'].includes(m.status)
    );
    if (allDone) {
      this.state = 'COMPLETED';
      this._log('CONTRACT_COMPLETED', null, 'STATE_CHANGE',
        `All milestones resolved. Total paid: $${this.releasedFunds.toLocaleString()}, refunded: $${this.refundedFunds.toLocaleString()}`);
    }
  }

  getState() {
    return {
      projectId: this.projectId,
      totalFunds: this.totalFunds,
      lockedFunds: this.lockedFunds,
      releasedFunds: this.releasedFunds,
      refundedFunds: this.refundedFunds,
      milestones: this.milestones.map(m => ({ ...m })),
      employerId: this.employerId,
      freelancerId: this.freelancerId,
      state: this.state,
      ledger: [...this.ledger],
      createdAt: this.createdAt,
    };
  }

  // Serialize for localStorage
  serialize() {
    return JSON.stringify(this.getState());
  }

  // Rehydrate from localStorage
  static fromJSON(json) {
    const data = typeof json === 'string' ? JSON.parse(json) : json;
    const contract = Object.create(EscrowContract.prototype);
    Object.assign(contract, data);
    return contract;
  }
}
