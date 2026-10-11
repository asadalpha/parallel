"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { apiBase } from "@/lib/api";

const STORY_TYPES = ["history", "personal_memory", "legend", "fiction", "editorial"] as const;
const MAX_IMAGE_BYTES = 10_000_000;

type SeedLocation = { id: string; name: string; city: string | null };
type SeededStory = { id: string; title: string; publication_status: string };
type LocationMode = "existing" | "new";
type InputMode = "form" | "json";

const JSON_TEMPLATE = `{
  "title": "The gate that never opened",
  "body": "Two paragraphs\\n\\nseparated by a blank line.",
  "category": "architecture",
  "story_type": "history",
  "existing_location_id": null,
  "name": "Somewhere",
  "description": "Optional place description",
  "latitude": 28.6315,
  "longitude": 77.2167,
  "city": "New Delhi",
  "country": "India",
  "place_kind": "landmark",
  "indoor_outdoor": "outdoor",
  "vibe_tags": ["cozy", "quiet"],
  "historical_sources": [{ "title": "Source name", "url": "https://example.com" }],
  "author_id": "curator:seed",
  "is_featured": false,
  "image_caption": "Optional caption for the uploaded image",
  "image_alt_text": "Alt text for the uploaded image"
}`;

const label = "block font-[8px] uppercase tracking-[.15em] text-[var(--muted)]";
const field =
  "mt-1.5 w-full rounded-[3px] border border-[var(--line)] bg-[var(--paper-bright)] px-3 py-2 text-[13px] text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--moss)] focus:outline-none";
const panel = "rounded-[5px] border border-[var(--line)] bg-[var(--paper-bright)] p-5";

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

export default function SeedPage() {
  if (process.env.NODE_ENV === "production") {
    return (
      <main className="mx-auto max-w-[640px] px-6 py-24">
        <p className={label}>Seeding</p>
        <h1 className="mt-3 font-[var(--serif)] text-[28px] tracking-[-.03em]">
          Disabled in production
        </h1>
        <p className="mt-3 max-w-[46ch] text-[13px] leading-[1.7] text-[var(--ink-soft)]">
          This form writes stories straight into the database without the draft and moderation
          flow. The API refuses to serve it when the environment is production.
        </p>
      </main>
    );
  }

  return <SeedForm />;
}

function SeedForm() {
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);

  const [locationMode, setLocationMode] = useState<LocationMode>("new");
  const [inputMode, setInputMode] = useState<InputMode>("form");
  const [image, setImage] = useState<File | null>(null);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [jsonPayload, setJsonPayload] = useState("");
  const [isFeatured, setIsFeatured] = useState(false);

  const locations = useQuery({
    queryKey: ["seed-locations"],
    queryFn: async ({ signal }: { signal: AbortSignal }) => {
      const response = await fetch(`${apiBase}/seed/locations`, {
        headers: { Accept: "application/json" },
        signal,
      });
      if (!response.ok) throw new Error(await readDetail(response));
      return (await response.json()) as SeedLocation[];
    },
    retry: false,
  });

  const create = useMutation({
    mutationFn: async ({ form, endpoint }: { form: FormData; endpoint: string }) => {
      const response = await fetch(`${apiBase}${endpoint}`, { method: "POST", body: form });
      if (!response.ok) throw new Error(await readDetail(response));
      return (await response.json()) as SeededStory;
    },
    onSuccess: async () => {
      formRef.current?.reset();
      setImage(null);
      setSourcesError(null);
      setJsonPayload("");
      setIsFeatured(false);
      setLocationMode("new");
      await queryClient.invalidateQueries({ queryKey: ["stories"] });
      await queryClient.invalidateQueries({ queryKey: ["locations"] });
    },
  });

  const imageTooLarge = image !== null && image.size > MAX_IMAGE_BYTES;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSourcesError(null);
    setJsonError(null);

    const data = new FormData(event.currentTarget);

    if (inputMode === "json") {
      if (jsonPayload.trim()) {
        try {
          JSON.parse(jsonPayload) as unknown;
        } catch {
          setJsonError("The seed payload must be valid JSON.");
          return;
        }
        if (image) data.set("image", image);
        data.set("payload", jsonPayload);
        create.mutate({ form: data, endpoint: "/seed/story-json" });
        return;
      }
      setJsonError("Paste the complete story JSON first.");
      return;
    }

    if (locationMode === "existing") {
      const chosen = String(data.get("existing_location_id") || "");
      if (!chosen) {
        create.reset();
        return;
      }
    }
    data.delete("existing_location_id");

    const rawSources = String(data.get("historical_sources") || "");
    if (rawSources.trim()) {
      try {
        const parsed: unknown = JSON.parse(rawSources);
        if (!Array.isArray(parsed)) throw new Error("not an array");
      } catch {
        setSourcesError("Historical sources must be a JSON array, for example [{ \"title\": \"…\", \"url\": \"…\" }].");
        return;
      }
    }

    data.set("is_featured", String(isFeatured));
    if (image) data.set("image", image);

    create.mutate({ form: data, endpoint: "/seed/story" });
  }

  const created = create.data;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-14">
      <p className={label}>Development only</p>
      <h1 className="mt-3 font-[var(--serif)] text-[30px] tracking-[-.035em]">Seed a story</h1>
      <p className="mt-2 max-w-[58ch] text-[13px] leading-[1.7] text-[var(--ink-soft)]">
        Writes a published, curated story directly. The API is only mounted when the environment is
        not production.
      </p>

      {created && (
        <div
          role="status"
          className="mt-6 rounded-[5px] border border-[var(--moss)] bg-[var(--paper-bright)] p-4"
        >
          <p className="flex items-center gap-2 font-[var(--sans)] text-[13px] text-[var(--moss-deep)]">
            <Check size={15} aria-hidden="true" /> Created “{created.title}” as{" "}
            {created.publication_status}.
          </p>
          <p className="mt-2 font-[var(--mono)] text-[10px] break-all text-[var(--muted)]">
            {created.id}
          </p>
          <Link
            href={`/stories/${created.id}`}
            className="mt-3 inline-block border-b border-[var(--moss)] pb-0.5 font-[var(--serif)] text-[13px] text-[var(--moss-deep)] hover:text-[var(--clay)]"
          >
            Open the story
          </Link>
        </div>
      )}

      {create.isError && (
        <p
          role="alert"
          className="mt-6 rounded-[5px] border border-[var(--clay)] bg-[var(--paper-bright)] p-4 text-[13px] text-[var(--clay)]"
        >
          {create.error.message}
        </p>
      )}

      <form ref={formRef} onSubmit={handleSubmit} className="mt-8 space-y-6">
        <section className={panel}>
          <h2 className="font-[var(--serif)] text-[17px] tracking-[-.02em]">Input</h2>
          <div className="mt-3 flex gap-5 text-[12px]">
            {(["form", "json"] as const).map((mode) => (
              <label key={mode} className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="input_mode"
                  value={mode}
                  checked={inputMode === mode}
                  onChange={() => {
                    setInputMode(mode);
                    setJsonError(null);
                    setJsonPayload(mode === "json" ? JSON_TEMPLATE : "");
                  }}
                  className="accent-[var(--moss)]"
                />
                {mode === "form" ? "Fill the form" : "Paste full JSON"}
              </label>
            ))}
          </div>
          {inputMode === "json" && (
            <p className="mt-3 text-[12px] leading-[1.6] text-[var(--ink-soft)]">
              Everything except the cover image goes into one JSON object. The image below is still
              attached as a file.
            </p>
          )}
        </section>

        {inputMode === "json" ? (
          <section className={panel}>
            <h2 className="font-[var(--serif)] text-[17px] tracking-[-.02em]">Story JSON</h2>
            <div className="mt-4">
              <label className={label} htmlFor="payload">
                Full seed payload
              </label>
              <textarea
                id="payload"
                name="payload"
                rows={24}
                spellCheck={false}
                value={jsonPayload}
                onChange={(event) => {
                  setJsonPayload(event.target.value);
                  setJsonError(null);
                }}
                placeholder={JSON_TEMPLATE}
                className={`${field} font-[var(--mono)] text-[11px] leading-[1.6]`}
                aria-invalid={jsonError !== null}
              />
              {jsonError && (
                <p role="alert" className="mt-2 text-[12px] text-[var(--clay)]">
                  {jsonError}
                </p>
              )}
            </div>
          </section>
        ) : (
          <section className={panel}>
            <h2 className="font-[var(--serif)] text-[17px] tracking-[-.02em]">Location</h2>

          <div className="mt-3 flex gap-5 text-[12px]">
            {(["new", "existing"] as const).map((mode) => (
              <label key={mode} className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="location_mode"
                  value={mode}
                  checked={locationMode === mode}
                  onChange={() => setLocationMode(mode)}
                  className="accent-[var(--moss)]"
                />
                {mode === "new" ? "Create a new location" : "Use an existing location"}
              </label>
            ))}
          </div>

          {locationMode === "existing" ? (
            <div className="mt-4">
              <label className={label} htmlFor="existing_location_id">
                Existing location
              </label>
              <select
                id="existing_location_id"
                name="existing_location_id"
                required
                defaultValue=""
                className={field}
              >
                <option value="" disabled>
                  {locations.isPending ? "Loading locations…" : "Choose a location"}
                </option>
                {(locations.data ?? []).map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                    {location.city ? ` — ${location.city}` : ""}
                  </option>
                ))}
              </select>
              {locations.isError && (
                <p className="mt-2 text-[12px] text-[var(--clay)]">
                  Could not load locations: {locations.error.message}
                </p>
              )}
            </div>
          ) : (
            <div className="mt-4 grid gap-4">
              <div>
                <label className={label} htmlFor="name">
                  Place name *
                </label>
                <input id="name" name="name" required maxLength={200} className={field} />
              </div>
              <div>
                <label className={label} htmlFor="description">
                  Description
                </label>
                <textarea id="description" name="description" rows={2} className={field} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={label} htmlFor="latitude">
                    Latitude *
                  </label>
                  <input
                    id="latitude"
                    name="latitude"
                    type="number"
                    step="any"
                    required
                    className={field}
                  />
                </div>
                <div>
                  <label className={label} htmlFor="longitude">
                    Longitude *
                  </label>
                  <input
                    id="longitude"
                    name="longitude"
                    type="number"
                    step="any"
                    required
                    className={field}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={label} htmlFor="city">
                    City
                  </label>
                  <input id="city" name="city" maxLength={120} className={field} />
                </div>
                <div>
                  <label className={label} htmlFor="country">
                    Country
                  </label>
                  <input id="country" name="country" maxLength={120} className={field} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={label} htmlFor="place_kind">
                    Place kind
                  </label>
                  <input
                    id="place_kind"
                    name="place_kind"
                    maxLength={80}
                    placeholder="landmark, street, building…"
                    className={field}
                  />
                </div>
                <div>
                  <label className={label} htmlFor="indoor_outdoor">
                    Indoor or outdoor
                  </label>
                  <input
                    id="indoor_outdoor"
                    name="indoor_outdoor"
                    maxLength={24}
                    placeholder="outdoor"
                    className={field}
                  />
                </div>
              </div>
            </div>
          )}
        </section>
        )}

        {(inputMode === "form" || inputMode === "json") && (
          <section className={panel}>
            <h2 className="font-[var(--serif)] text-[17px] tracking-[-.02em]">Image</h2>
            <div className="mt-4 grid gap-4">
              <div>
                <label className={label} htmlFor="image">
                  Cover image — JPEG, PNG or WebP, max 10 MB
                </label>
                <input
                  id="image"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => setImage(event.target.files?.[0] ?? null)}
                  className="mt-1.5 w-full text-[12px] text-[var(--ink-soft)] file:mr-3 file:rounded-[3px] file:border-0 file:bg-[var(--paper-deep)] file:px-3 file:py-1.5 file:text-[12px] file:text-[var(--ink)]"
                />
                {image && (
                  <p className="mt-2 font-[var(--mono)] text-[10px] text-[var(--muted)]">
                    {image.name} — {(image.size / 1024).toFixed(0)} KB
                  </p>
                )}
                {imageTooLarge && (
                  <p role="alert" className="mt-2 text-[12px] text-[var(--clay)]">
                    Over 10 MB. The API will reject it.
                  </p>
                )}
              </div>
              {inputMode === "form" && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={label} htmlFor="image_caption">
                      Caption
                    </label>
                    <input
                      id="image_caption"
                      name="image_caption"
                      maxLength={500}
                      className={field}
                    />
                  </div>
                  <div>
                    <label className={label} htmlFor="image_alt_text">
                      Alt text
                    </label>
                    <input
                      id="image_alt_text"
                      name="image_alt_text"
                      maxLength={500}
                      placeholder="Describe the image for screen readers"
                      className={field}
                    />
                  </div>
                </div>
              )}
              {inputMode === "json" && (
                <p className="text-[12px] leading-[1.6] text-[var(--muted)]">
                  Caption and alt text are read from the JSON payload (
                  {`image_caption`} / {`image_alt_text`}).
                </p>
              )}
            </div>
          </section>
        )}

        {inputMode === "form" && (
          <section className={panel}>
            <h2 className="font-[var(--serif)] text-[17px] tracking-[-.02em]">Story</h2>
            <div className="mt-4 grid gap-4">
            <div>
              <label className={label} htmlFor="title">
                Title *
              </label>
              <input id="title" name="title" required maxLength={240} className={field} />
            </div>
            <div>
              <label className={label} htmlFor="body">
                Body *
              </label>
              <textarea
                id="body"
                name="body"
                required
                rows={14}
                maxLength={100_000}
                className={`${field} font-[var(--serif)] leading-[1.75]`}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={label} htmlFor="category">
                  Category *
                </label>
                <input
                  id="category"
                  name="category"
                  required
                  maxLength={80}
                  placeholder="architecture, folklore…"
                  className={field}
                />
              </div>
              <div>
                <label className={label} htmlFor="story_type">
                  Story type *
                </label>
                <select id="story_type" name="story_type" required className={field}>
                  {STORY_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className={label} htmlFor="vibe_tags">
                Vibe tags — comma separated, max 12
              </label>
              <input
                id="vibe_tags"
                name="vibe_tags"
                placeholder="circular, imperial, bazaar"
                className={field}
              />
            </div>
            <div>
              <label className={label} htmlFor="historical_sources">
                Historical sources — JSON array
              </label>
              <textarea
                id="historical_sources"
                name="historical_sources"
                rows={4}
                spellCheck={false}
                placeholder='[{"title": "Source name", "url": "https://example.com"}]'
                className={`${field} font-[var(--mono)] text-[11px]`}
                aria-invalid={sourcesError !== null}
              />
              {sourcesError && (
                <p role="alert" className="mt-2 text-[12px] text-[var(--clay)]">
                  {sourcesError}
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={label} htmlFor="author_id">
                  Author id
                </label>
                <input
                  id="author_id"
                  name="author_id"
                  defaultValue="curator:seed"
                  maxLength={255}
                  className={field}
                />
              </div>
              <label className="mt-5 flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  checked={isFeatured}
                  onChange={(event) => setIsFeatured(event.target.checked)}
                  className="accent-[var(--moss)]"
                />
                Featured
              </label>
            </div>
            </div>
          </section>
        )}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={create.isPending}
            className="inline-flex items-center gap-2 rounded-[3px] border border-[var(--moss)] bg-[var(--moss)] px-4 py-2 text-[13px] text-[var(--paper-bright)] transition-colors hover:bg-[var(--moss-deep)] disabled:opacity-50"
          >
            {create.isPending ? (
              <>
                <Loader2 size={14} className="animate-spin" aria-hidden="true" /> Seeding…
              </>
            ) : (
              "Seed story"
            )}
          </button>
          {created && (
            <button
              type="button"
              onClick={() => create.reset()}
              className="inline-flex items-center gap-1.5 text-[12px] text-[var(--muted)] hover:text-[var(--ink)]"
            >
              <RotateCcw size={13} aria-hidden="true" /> Clear confirmation
            </button>
          )}
        </div>
      </form>
    </main>
  );
}