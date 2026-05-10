import { vectorAssets } from './assets';
import { extractKeywords, normalizeToken } from './scriptParser';
import type { AnimationPreset, AssetMatch, PlacedAsset, Scene, VectorAsset } from './types';

const synonyms: Record<string, string[]> = {
  dance: ['dances','dancing','lively','party','move','happy'],
  happy: ['happily','joy','smile','fun','lively'],
  elephant: ['elephants','trunk','safari'],
  learn: ['learning','lesson','study','education','school'],
  business: ['startup','sales','revenue','profit','work'],
  growth: ['grow','rises','increase','trend','success'],
  rocket: ['launch','fast','space','startup'],
  idea: ['innovation','creative','solution','lightbulb'],
  app: ['software','mobile','technology','apk'],
  explain: ['explainer','present','teach','speaker'],
};

const categoryHints: Record<string, string> = {
  school: 'education', lesson: 'education', learn: 'education', study: 'education', science: 'science', lab: 'science', data: 'business', revenue: 'business', startup: 'business', phone: 'objects', app: 'objects', people: 'people', team: 'people', animal: 'animals', elephant: 'animals', happy: 'emojis', arrow: 'arrows', chart: 'business'
};

function expanded(tokens: string[]) {
  const out = new Set(tokens);
  for (const token of tokens) {
    for (const [root, variants] of Object.entries(synonyms)) {
      if (token === root || variants.includes(token)) {
        out.add(root);
        variants.forEach((variant) => out.add(normalizeToken(variant)));
      }
    }
  }
  return out;
}

function bestPreset(asset: VectorAsset, tokens: Set<string>): AnimationPreset {
  if ([...tokens].some((token) => ['dance','dancing','happy','lively','fun'].includes(token)) && asset.animationPresets.includes('dance')) return 'dance';
  if ([...tokens].some((token) => ['growth','grow','rise','increase'].includes(token)) && asset.animationPresets.includes('grow')) return 'grow';
  if ([...tokens].some((token) => ['rocket','launch','fast'].includes(token)) && asset.animationPresets.includes('rocket')) return 'rocket';
  if ([...tokens].some((token) => ['happy','smile','wow'].includes(token)) && asset.animationPresets.includes('pop')) return 'pop';
  return asset.animationPresets[0] ?? 'draw';
}

export function matchAssetsForText(text: string, limit = 4): AssetMatch[] {
  const keywords = extractKeywords(text);
  const tokens = expanded(keywords.concat(text.split(/\s+/).map(normalizeToken).filter(Boolean)));
  const matches = vectorAssets.map((asset) => {
    let score = 0;
    const reasons: string[] = [];
    const assetTokens = new Set([asset.name, asset.id, asset.category, ...asset.keywords].map(normalizeToken));
    for (const token of tokens) {
      if (asset.id === token || normalizeToken(asset.name) === token) { score += 12; reasons.push(`exact ${token}`); }
      if (asset.keywords.map(normalizeToken).includes(token)) { score += 7; reasons.push(`keyword ${token}`); }
      if (assetTokens.has(token)) score += 2;
      if (categoryHints[token] === asset.category) { score += 3; reasons.push(`category ${asset.category}`); }
    }
    return { asset, score, reasons: [...new Set(reasons)].slice(0, 4), preset: bestPreset(asset, tokens) } satisfies AssetMatch;
  });
  return matches.filter((match) => match.score > 0).sort((a, b) => b.score - a.score).slice(0, limit);
}

export function autoPlaceAssets(scene: Scene): PlacedAsset[] {
  return matchAssetsForText(scene.text, 4).map((match, index) => {
    const positions = [{ x: 62, y: 54, scale: 1.12 }, { x: 30, y: 67, scale: .72 }, { x: 78, y: 70, scale: .68 }, { x: 50, y: 82, scale: .46 }];
    const position = positions[index] ?? positions[0];
    return { assetId: match.asset.id, x: position.x, y: position.y, scale: position.scale, rotation: index % 2 ? -3 : 3, animation: match.preset };
  });
}

export function enrichScenesWithAssets(scenes: Scene[]) {
  return scenes.map((scene) => ({ ...scene, assets: scene.assets.length ? scene.assets : autoPlaceAssets(scene) }));
}
