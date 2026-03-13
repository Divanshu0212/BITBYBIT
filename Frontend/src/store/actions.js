// actions.js — All action type constants
export const ACTIONS = {
  // Auth
  SET_USER:          'SET_USER',
  SET_TOKEN:         'SET_TOKEN',
  LOGOUT:            'LOGOUT',

  // Navigation
  SET_VIEW:          'SET_VIEW',

  // Projects
  SET_PROJECTS:      'SET_PROJECTS',
  SET_CURRENT_PROJECT: 'SET_CURRENT_PROJECT',

  // Escrow / Ledger
  SET_ESCROW:        'SET_ESCROW',
  SET_LEDGER:        'SET_LEDGER',

  // AQA
  SET_AQA_RESULT:    'SET_AQA_RESULT',

  // Freelancer list (for employer assignment)
  SET_FREELANCERS:   'SET_FREELANCERS',

  // Loading / Errors
  SET_LOADING:       'SET_LOADING',
  SET_ERROR:         'SET_ERROR',

  // PFI
  SET_PFI_SCORE:     'SET_PFI_SCORE',
  SET_PFI_HISTORY:   'SET_PFI_HISTORY',
  SET_LEADERBOARD:   'SET_LEADERBOARD',

  // Employer extras
  SET_ANALYTICS:     'SET_ANALYTICS',
  SET_HITL_ITEMS:    'SET_HITL_ITEMS',
  SET_ASSIGN_SCORES: 'SET_ASSIGN_SCORES',

  RESET_STATE:       'RESET_STATE',
};
