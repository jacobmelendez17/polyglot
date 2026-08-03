// Feature-unlock client.
import { request } from "./http";

export interface FeatureState {
  feature: string;
  unlock_level: number;
  unlocked: boolean;
  levels_remaining: number;
}

export interface FeaturesResult {
  completed_levels: number;
  features: FeatureState[];
}

export const features = {
  list: () => request<FeaturesResult>("/api/v1/features"),
};

// Friendly labels for the roadmap (keys come from the server schedule).
export const FEATURE_LABELS: Record<string, string> = {
  reviews: "reviews",
  reading: "reading",
  listening: "listening practice",
  writing: "writing & journal",
  testing_app: "app tests",
  sentence_structure: "sentence structure",
  speaking: "speaking practice",
  testing_life: "life tests",
  testing_cefr: "cefr tests",
  verb_conjugation: "verb conjugation",
  immersion: "immersion mode",
};

export function featureLabel(key: string): string {
  return FEATURE_LABELS[key] ?? key.replace(/_/g, " ");
}
