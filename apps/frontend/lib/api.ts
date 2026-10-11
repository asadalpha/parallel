export type StoryType = "history" | "personal_memory" | "legend" | "fiction" | "editorial";

export type LocationRead = {
  id: string;
  name: string;
  description: string | null;
  latitude: number;
  longitude: number;
  city: string | null;
  country: string | null;
  place_kind: string | null;
  accessibility_status: string | null;
  indoor_outdoor: string | null;
};

export type StorySummary = {
  id: string;
  location_id: string;
  title: string;
  category: string;
  story_type: StoryType;
  cover_image_url: string | null;
  vibe_tags: string[];
  read_minutes: number;
  is_curated: boolean;
  is_featured: boolean;
  location: LocationRead;
  distance_meters: number | null;
  audio_available: boolean;
  other_chapter_count: number;
};

export type StoryDetail = StorySummary & {
  author_id: string | null;
  body: string;
  publication_status: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  historical_sources: Array<Record<string, string>>;
  media: Array<{
    id: string;
    media_type: string;
    media_url: string;
    caption: string | null;
    alt_text: string | null;
    sort_order: number;
  }>;
  audio: Array<{
    id: string;
    audio_url: string;
    voice_identifier: string;
    duration_seconds: number | null;
    is_synthetic: boolean;
    created_at: string;
  }>;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type ConciergeRequest = {
  mood: "cozy" | "curious" | "spooky" | "reflective" | "surprise";
  time_available_minutes: number;
  travel_preference: "walking_nearby" | "a_little_farther" | "any_distance";
  latitude: number;
  longitude: number;
};

export type RecommendationRead = {
  story: StorySummary;
  explanation: string;
  audio_available: boolean;
  other_chapter_count: number;
  fallback_used: boolean;
};

export type StoryFilters = {
  locationId?: string;
  bounds?: { min_lat: number; min_lon: number; max_lat: number; max_lon: number };
  origin?: { latitude: number; longitude: number; radius_meters?: number };
  storyType?: StoryType;
  hasAudio?: boolean;
  multipleChaptersOnly?: boolean;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1").replace(
  /\/$/,
  "",
);

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  } catch {
    throw new ApiError("The story service could not be reached.", 0);
  }

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // The response may be empty or non-JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("The story service could not be reached.", 0);
  }
  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // The response may be empty or non-JSON.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export function fetchLocations(query: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ query, page_size: "12" });
  return getJson<Page<LocationRead>>(`/locations?${params}`, signal);
}

export function fetchStories(filters: StoryFilters, signal?: AbortSignal) {
  const params = new URLSearchParams({ page_size: "100" });
  if (filters.locationId) params.set("location_id", filters.locationId);
  if (filters.storyType) params.set("story_type", filters.storyType);
  if (filters.hasAudio !== undefined) params.set("has_audio", String(filters.hasAudio));
  if (filters.multipleChaptersOnly) params.set("multiple_chapters", "true");
  if (filters.bounds) {
    for (const [key, value] of Object.entries(filters.bounds)) params.set(key, String(value));
  } else if (filters.origin) {
    params.set("latitude", String(filters.origin.latitude));
    params.set("longitude", String(filters.origin.longitude));
    if (filters.origin.radius_meters) {
      params.set("radius_meters", String(filters.origin.radius_meters));
    }
  }
  return getJson<Page<StorySummary>>(`/stories?${params}`, signal);
}

export function fetchStory(storyId: string, signal?: AbortSignal) {
  return getJson<StoryDetail>(`/stories/${encodeURIComponent(storyId)}`, signal);
}

export function requestRecommendation(payload: ConciergeRequest) {
  return postJson<RecommendationRead>("/concierge/recommend", payload);
}

export function requestAnotherAngle(locationId: string, excludeStoryId: string) {
  return postJson<RecommendationRead>("/concierge/another-angle", {
    location_id: locationId,
    exclude_story_id: excludeStoryId,
  });
}
