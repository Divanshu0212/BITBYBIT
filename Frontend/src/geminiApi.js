// groqApi.js — All Groq API wrappers
// Every function takes apiKey as a parameter — never reads from module scope.
// Responses parsed with try/catch, stripping markdown fences before JSON.parse().

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';

async function callAI(systemPrompt, userPrompt, apiKey) {
  const res = await fetch(GROQ_API_URL, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: 'llama-3.3-70b-versatile',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      temperature: 0.3,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Groq API error (${res.status}): ${err}`);
  }
  const data = await res.json();
  const text = data.choices?.[0]?.message?.content || '';
  return parseJSON(text);
}

function parseJSON(raw) {
  // Strip markdown fences
  let cleaned = raw.replace(/```json\s*/gi, '').replace(/```\s*/g, '').trim();
  try {
    return JSON.parse(cleaned);
  } catch (e) {
    // Try to find JSON object in text
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error('Failed to parse Groq response as JSON: ' + cleaned.substring(0, 200));
  }
}

export async function decomposeProject(description, apiKey) {
  const systemPrompt = `You are an expert project manager AI. Given a vague project description, decompose it into:
1. A list of 3-7 time-bound milestones, each with:
   - title (string)
   - description (string)
   - domain (string, e.g. "Backend Development", "UI/UX Design", "Content Writing")
   - estimatedDays (number)
   - acceptanceCriteria (array of 3-5 specific, testable strings)
   - complexityScore (1-10)
2. dag: array of { from: milestoneIndex, to: milestoneIndex }
3. totalEstimatedDays (number)
4. projectRiskLevel: "Low" | "Medium" | "High"

Return ONLY valid JSON. No markdown, no explanation.`;

  return callAI(systemPrompt, description, apiKey);
}

export async function evaluateSubmission(milestone, submission, apiKey) {
  const systemPrompt = `You are an autonomous quality assurance agent. Evaluate submitted work against milestone acceptance criteria.`;

  const criteriaList = milestone.acceptanceCriteria
    .map((c, i) => `${i + 1}. ${c}`)
    .join('\n');

  const userPrompt = `MILESTONE: ${milestone.title}
DOMAIN: ${milestone.domain}
ACCEPTANCE CRITERIA:
${criteriaList}
SUBMITTED WORK: ${submission}

Evaluate each criterion and return ONLY valid JSON:
{
  "overallScore": 0-100,
  "completionStatus": "FULLY_COMPLETED" | "PARTIALLY_COMPLETED" | "UNMET",
  "percentComplete": 0-100,
  "criteriaEvaluation": [
    { "criterion": "...", "met": true/false, "score": 0-100, "feedback": "..." }
  ],
  "detailedFeedback": "...",
  "paymentRecommendation": "FULL_RELEASE" | "PRO_RATED" | "REFUND",
  "proRatedPercentage": 0-100
}`;

  return callAI(systemPrompt, userPrompt, apiKey);
}

export async function generateDemoProject(apiKey) {
  const systemPrompt = `You are a creative project generator for a freelancing platform demo.`;
  const userPrompt = `Generate a completely unique and realistic freelance project scenario.
Return ONLY valid JSON:
{
  "employer": { "name": "<realistic full name>", "company": "<company name>" },
  "freelancer": { "name": "<realistic full name>", "skills": ["<skill1>", "<skill2>", "<skill3>"] },
  "projectDescription": "<2-4 sentences describing a realistic project requirement, be specific about what needs to be built>"
}`;

  return callAI(systemPrompt, userPrompt, apiKey);
}

export async function scoreFreelancerMatch(skills, domain, apiKey) {
  const systemPrompt = `You are a skill-matching AI for a freelancing platform.`;
  const userPrompt = `Given freelancer skills: ${JSON.stringify(skills)}
Required project domain: ${domain}
Evaluate how well the freelancer's skills match this domain.
Return ONLY valid JSON: { "score": 0.0-1.0, "reasoning": "brief explanation" }`;

  return callAI(systemPrompt, userPrompt, apiKey);
}

export async function detectBias(ratingHistory, apiKey) {
  const systemPrompt = `You are a bias detection algorithm for a freelancer reputation system.`;
  const userPrompt = `Analyze this rating history for patterns of recency bias, feedback loops, or manipulation:
${JSON.stringify(ratingHistory)}

Return ONLY valid JSON:
{ "biasDetected": false, "biasType": null, "confidence": 0-100, "recommendation": "brief recommendation" }`;

  return callAI(systemPrompt, userPrompt, apiKey);
}
