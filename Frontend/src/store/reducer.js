// reducer.js — Single root reducer
import { ACTIONS } from './actions';
import { PFI_CONFIG } from '../pfiCalculator';

export const initialState = {
  apiKey: null,
  activeView: 'employer',   // 'employer' | 'freelancer' | 'pfi' | 'analytics'
  projects: [],
  escrow: null,              // serialised EscrowContract state
  ledger: [],                // [{ timestamp, event, amount, type, details }]
  milestones: [],
  decomposition: null,       // full decomposition result from Groq
  dag: [],
  aqaResults: {},            // milestoneIndex → AQA JSON
  freelancers: [],
  loading: {},               // { decompose: bool, aqa: bool, pfi: bool, demo: bool }
  errors: {},                // { decompose: string|null, aqa: string|null, ... }

  // PFI / Advanced
  pfiScores: {},             // freelancerId → { score, rating, RD, volatility, history[] }
  assignScores: [],          // [{ freelancerId, score, domainMatch }]
  hitlQueue: [],             // AQA results pending human review
  pfiConfig: { ...PFI_CONFIG },
};

export function reducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_API_KEY:
      return { ...state, apiKey: action.payload };

    case ACTIONS.SET_VIEW:
      return { ...state, activeView: action.payload };

    case ACTIONS.SET_MILESTONES:
      return { ...state, milestones: action.payload };

    case ACTIONS.SET_DECOMPOSITION:
      return { ...state, decomposition: action.payload };

    case ACTIONS.SET_DAG:
      return { ...state, dag: action.payload };

    case ACTIONS.SET_PROJECT:
      return {
        ...state,
        projects: action.payload.replace
          ? [action.payload.project]
          : [...state.projects, action.payload.project],
      };

    case ACTIONS.SET_ESCROW:
      return { ...state, escrow: action.payload };

    case ACTIONS.APPEND_LEDGER:
      return { ...state, ledger: [...state.ledger, ...action.payload] };

    case ACTIONS.SET_AQA_RESULT:
      return {
        ...state,
        aqaResults: { ...state.aqaResults, [action.payload.index]: action.payload.result },
      };

    case ACTIONS.SET_FREELANCERS:
      return { ...state, freelancers: action.payload };

    case ACTIONS.SET_LOADING:
      return { ...state, loading: { ...state.loading, ...action.payload } };

    case ACTIONS.SET_ERROR:
      return { ...state, errors: { ...state.errors, ...action.payload } };

    case ACTIONS.SET_PFI_SCORE:
      return {
        ...state,
        pfiScores: { ...state.pfiScores, [action.payload.id]: action.payload.data },
      };

    case ACTIONS.SET_ASSIGN_SCORES:
      return { ...state, assignScores: action.payload };

    case ACTIONS.PUSH_HITL:
      return { ...state, hitlQueue: [...state.hitlQueue, action.payload] };

    case ACTIONS.RESOLVE_HITL:
      return {
        ...state,
        hitlQueue: state.hitlQueue.filter((_, i) => i !== action.payload),
      };

    case ACTIONS.UPDATE_PFI_CONFIG:
      return { ...state, pfiConfig: { ...state.pfiConfig, ...action.payload } };

    case ACTIONS.RESET_STATE:
      return { ...initialState, apiKey: state.apiKey };

    default:
      return state;
  }
}
