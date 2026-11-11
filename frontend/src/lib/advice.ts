/**
 * Deterministic, level-based citizen advice (TS mirror of the backend's rule table).
 * Used in demo mode where /api/risk/point is simulated in the browser.
 */
import type { Advice, RiskLevel } from '../api/schema';

export const ADVICE: Record<RiskLevel, Advice> = {
  green: {
    now: ['No flood action needed right now.', 'Keep following IMD / SDMA weather updates.'],
    prepare: [
      'Save emergency numbers: 112, 1078 (NDMA) and 108 (ambulance).',
      'Keep an emergency kit: torch, power bank, medicines, ID documents in a waterproof bag.',
      'Know the route to your nearest shelter on higher ground.',
    ],
    avoid: ['Do not dump waste into drains or nullahs — it causes waterlogging.'],
  },
  yellow: {
    now: [
      'Stay alert — heavy rain is possible in the next 72 hours.',
      'Charge your phone and keep the emergency kit ready.',
    ],
    prepare: [
      'Move documents, medicines and valuables to a higher shelf.',
      'Check on elderly neighbours and people with disabilities.',
      'Note the nearest shelter and the safest route to reach it.',
    ],
    avoid: ['Avoid parking vehicles in low-lying areas or underpasses.', 'Do not spread unverified forwards.'],
  },
  orange: {
    now: [
      'Be ready to leave at short notice — keep your go-bag at the door.',
      'Switch off the main electricity supply if water starts entering your home.',
      'Follow instructions from the district administration and SDMA.',
    ],
    prepare: [
      'Move family members who need help (elderly, children, ill) to a safer place early.',
      'Store drinking water and 3 days of dry food.',
      'Plan how to reach your nearest shelter before roads flood.',
    ],
    avoid: [
      'Do not walk or drive through flood water — 15 cm of moving water can knock you down.',
      'Stay away from river banks, drains and electric poles.',
    ],
  },
  red: {
    now: [
      'Move to the nearest shelter or higher ground NOW if you are in a low-lying area.',
      'Call 112 if you are trapped or someone needs rescue.',
      'Take your go-bag, medicines and ID documents.',
    ],
    prepare: [
      'If you cannot leave, go to the highest floor or roof and signal for help.',
      'Keep your phone charged and save battery — use SMS instead of calls.',
    ],
    avoid: [
      'Do not enter flood water — it may hide open drains and live wires.',
      'Do not return home until authorities say it is safe.',
      'Avoid touching electrical equipment if you are wet.',
    ],
  },
};
