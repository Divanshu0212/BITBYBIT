// reducer.js — Root reducer for BITBYBIT
import { ACTIONS } from './actions';

function loadUser() {
  try {
    const u = localStorage.getItem('bitbybit_user');
    return u ? JSON.parse(u) : null;
  } catch { return null; }
}

export const initialState = {
  // Auth
  user: loadUser(),
  token: localStorage.getItem('bitbybit_token') || null,

  // Navigation
  activeView: 'projects',   // 'projects' | 'analytics' | 'pfi' | 'leaderboard'

  // Projects
  projects: [],
  currentProject: null,    // full project with milestones

  // Escrow / Ledger
  escrow: null,
  ledger: [],

  // AQA results (milestoneId → result)
  aqaResults: {},

  // Freelancer list (for employer assignment)
  freelancers: [],

  // Loading / Errors
  loading: {},
  errors: {},

  // PFI
  pfiScore: null,
  pfiHistory: [],
  leaderboard: [],

  // Employer extras
  analytics: null,
  hitlItems: [],
  assignScores: [],
};

export function reducer(state, action) {
  switch (action.type) {
    // Auth
    case ACTIONS.SET_USER:
      return { ...state, user: action.payload };
    case ACTIONS.SET_TOKEN:
      return { ...state, token: action.payload };
    case ACTIONS.LOGOUT:
      return { ...initialState, user: null, token: null };

    // Navigation
    case ACTIONS.SET_VIEW:
      return { ...state, activeView: action.payload };

    // Projects
    case ACTIONS.SET_PROJECTS:
      return { ...state, projects: action.payload };
    case ACTIONS.SET_CURRENT_PROJECT:
      return { ...state, currentProject: action.payload };

    // Escrow / Ledger (server-driven)
    case ACTIONS.SET_ESCROW:
      return { ...state, escrow: action.payload };
    case ACTIONS.SET_LEDGER:
      return { ...state, ledger: action.payload };

    // AQA
    case ACTIONS.SET_AQA_RESULT:
      return {
        ...state,
        aqaResults: { ...state.aqaResults, [action.payload.milestoneId]: action.payload.result },
      };

    // Freelancers
    case ACTIONS.SET_FREELANCERS:
      return { ...state, freelancers: action.payload };

    // Loading / Errors
    case ACTIONS.SET_LOADING:
      return { ...state, loading: { ...state.loading, ...action.payload } };
    case ACTIONS.SET_ERROR:
      return { ...state, errors: { ...state.errors, ...action.payload } };

    // PFI
    case ACTIONS.SET_PFI_SCORE:
      return { ...state, pfiScore: action.payload };
    case ACTIONS.SET_PFI_HISTORY:
      return { ...state, pfiHistory: action.payload };
    case ACTIONS.SET_LEADERBOARD:
      return { ...state, leaderboard: action.payload };

    // Employer extras
    case ACTIONS.SET_ANALYTICS:
      return { ...state, analytics: action.payload };
    case ACTIONS.SET_HITL_ITEMS:
      return { ...state, hitlItems: action.payload };
    case ACTIONS.SET_ASSIGN_SCORES:
      return { ...state, assignScores: action.payload };

    // Reset
    case ACTIONS.RESET_STATE:
      return { ...initialState, user: state.user, token: state.token };

    default:
      return state;
  }
}
