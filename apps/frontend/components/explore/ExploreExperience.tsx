"use client";

import Image from "next/image";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowDown,
  ArrowUpRight,
  AudioLines,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Compass,
  LocateFixed,
  MapPin,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { ApiError, fetchLocations, fetchStories, fetchStory } from "@/lib/api";
import type { LocationRead, StorySummary, StoryType } from "@/lib/api";

import { ContributeGate } from "@/components/contribute/ContributeGate";
import { ConciergePanel } from "@/components/concierge/ConciergePanel";
import { MapBounds, StoryMap } from "./StoryMap";

const STORY_TYPES: Array<{ value: StoryType | "all"; label: string }> = [
  { value: "all", label: "All stories" },
  { value: "history", label: "History" },
  { value: "personal_memory", label: "Memories" },
  { value: "legend", label: "Legends" },
  { value: "fiction", label: "Fiction" },
];

const STORY_TYPE_LABELS: Record<StoryType, string> = {
  history: "History",
  personal_memory: "Personal memory",
  legend: "Local legend",
  fiction: "Fiction",
  editorial: "Editorial",
};

type Center = { latitude: number; longitude: number };

export function ExploreExperience() {
  const [searchText, setSearchText] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [selectedLocation, setSelectedLocation] = useState<LocationRead | null>(null);
  const [center, setCenter] = useState<Center | null>(null);
  const [userOrigin, setUserOrigin] = useState<Center | null>(null);
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [storyType, setStoryType] = useState<StoryType | "all">("all");
  const [audioOnly, setAudioOnly] = useState(false);
  const [multipleChaptersOnly, setMultipleChaptersOnly] = useState(false);
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  const [sheetExpanded, setSheetExpanded] = useState(false);
  const [authGateOpen, setAuthGateOpen] = useState(false);
  const [conciergeOpen, setConciergeOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchText.trim()), 240);
    return () => window.clearTimeout(timer);
  }, [searchText]);

  const locationQuery = useQuery({
    queryKey: ["locations", debouncedSearch],
    queryFn: ({ signal }) => fetchLocations(debouncedSearch, signal),
    enabled: searchOpen && debouncedSearch.length >= 2,
    retry: false,
  });

  const storyFilters = useMemo(() => {
    if (!center) return null;
    return {
      ...(bounds ? { bounds } : { origin: { ...center, radius_meters: 5_000 } }),
      ...(storyType === "all" ? {} : { storyType }),
      ...(audioOnly ? { hasAudio: true } : {}),
      ...(multipleChaptersOnly ? { multipleChaptersOnly: true } : {}),
    };
  }, [audioOnly, bounds, center, storyType, multipleChaptersOnly]);

  const storyQuery = useQuery({
    queryKey: ["stories", storyFilters, multipleChaptersOnly],
    queryFn: ({ signal }) => fetchStories(storyFilters!, signal),
    enabled: storyFilters !== null,
    retry: false,
  });

  const visibleStories = storyQuery.data?.items ?? [];

  const selectedStoryQuery = useQuery({
    queryKey: ["story", selectedStoryId],
    queryFn: ({ signal }) => fetchStory(selectedStoryId!, signal),
    enabled: selectedStoryId !== null,
    retry: false,
  });

  const selectStory = useCallback((storyId: string) => setSelectedStoryId(storyId), []);

  function chooseLocation(location: LocationRead) {
    setSelectedLocation(location);
    setCenter({ latitude: location.latitude, longitude: location.longitude });
    setUserOrigin(null);
    setBounds(null);
    setSearchText(location.name);
    setSearchOpen(false);
    setSelectedStoryId(null);
    setNotice(null);
  }

  function locateMe() {
    if (!navigator.geolocation) {
      setNotice("Location isn’t available here. Search for a place instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const current = { latitude: coords.latitude, longitude: coords.longitude };
        setCenter(current);
        setUserOrigin(current);
        setSelectedLocation(null);
        setBounds(null);
        setSearchText("");
        setNotice(null);
      },
      () => setNotice("We couldn’t use your location. You can still search by place name."),
      { enableHighAccuracy: false, timeout: 8_000, maximumAge: 60_000 },
    );
  }

  const searchResults = locationQuery.data?.items ?? [];
  const connectionError = (storyQuery.error ?? locationQuery.error) as ApiError | null;
  const locationLabel = selectedLocation?.name ?? (userOrigin ? "Around you" : null);
  const selectedStory = selectedStoryQuery.data;

  return (
    <main className="explore-shell">
      <header className="explore-topbar">
        <Link className="wordmark" href="/" aria-label="Parallel home">
          <span className="wordmark-glyph" aria-hidden="true">∥</span>
          <span>parallel</span>
        </Link>
        <span className="topbar-caption"><span className="caption-rule" /> A living atlas of stories</span>
        <button className="contribute-button" onClick={() => setAuthGateOpen(true)}>
          <span>Add a story</span>
          <ArrowUpRight size={15} strokeWidth={1.7} aria-hidden="true" />
        </button>
      </header>

      <section className="explore-stage" aria-label="Explore stories by place">
        <StoryMap
          stories={visibleStories}
          center={center}
          selectedStoryId={selectedStoryId}
          onSelectStory={selectStory}
          onBoundsChange={setBounds}
        />

        <div className="map-top-overlay">
          <div className={`place-search ${searchOpen ? "is-open" : ""}`}>
            <Search size={17} strokeWidth={1.7} aria-hidden="true" />
            <input
              value={searchText}
              aria-label="Search a city or place"
              role="combobox"
              aria-autocomplete="list"
              aria-controls="place-search-results"
              aria-expanded={searchOpen && debouncedSearch.length >= 2}
              placeholder="Find a place or city"
              onFocus={() => setSearchOpen(true)}
              onChange={(event) => {
                setSearchText(event.target.value);
                setSearchOpen(true);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setSearchOpen(false);
                if (event.key === "Enter" && searchResults[0]) chooseLocation(searchResults[0]);
              }}
            />
            {searchText && (
              <button
                className="icon-button search-clear"
                aria-label="Clear search"
                onClick={() => {
                  setSearchText("");
                  setDebouncedSearch("");
                  setSearchOpen(true);
                }}
              >
                <X size={15} aria-hidden="true" />
              </button>
            )}

            {searchOpen && debouncedSearch.length >= 2 && (
              <div id="place-search-results" className="search-popover" role="listbox" aria-label="Matching places">
                {locationQuery.isFetching && <p className="popover-message">Looking for places…</p>}
                {!locationQuery.isFetching && searchResults.length === 0 && (
                  <div className="popover-empty">
                    <span>No mapped stories found for that place yet.</span>
                    <button onClick={() => setAuthGateOpen(true)}>Have a story to add?</button>
                  </div>
                )}
                {searchResults.map((location) => (
                  <button
                    key={location.id}
                    role="option"
                    aria-selected={selectedLocation?.id === location.id}
                    className="search-result"
                    onClick={() => chooseLocation(location)}
                  >
                    <span className="search-result__pin"><MapPin size={15} aria-hidden="true" /></span>
                    <span className="search-result__copy">
                      <strong>{location.name}</strong>
                      <small>{[location.city, location.country].filter(Boolean).join(", ")}</small>
                    </span>
                    {selectedLocation?.id === location.id && <Check size={15} aria-hidden="true" />}
                  </button>
                ))}
                {locationQuery.error && (
                  <p className="popover-message popover-message--error">{locationQuery.error.message}</p>
                )}
              </div>
            )}
          </div>

          <button className="map-control" onClick={locateMe} aria-label="Use my current location">
            <LocateFixed size={17} strokeWidth={1.7} aria-hidden="true" />
          </button>
        </div>

        <button className="concierge-trigger" onClick={() => setConciergeOpen(true)}>
          <Sparkles size={14} strokeWidth={1.7} aria-hidden="true" />
          <span>Take me somewhere</span>
        </button>

        <div className="map-location-caption" aria-live="polite">
          <span className="caption-pin"><MapPin size={12} aria-hidden="true" /></span>
          <span>{locationLabel ?? "Choose a place to begin"}</span>
          {locationLabel && <span className="caption-separator">·</span>}
          <span>{storyQuery.data?.total ?? 0} stories</span>
        </div>

        {selectedStoryId && (
          <div className="story-peek-wrap">
            {selectedStoryQuery.isPending ? (
              <div className="story-peek story-peek--loading" aria-label="Loading selected story" />
            ) : selectedStory ? (
              <article className="story-peek">
                <button
                  className="icon-button story-peek__close"
                  aria-label="Close story preview"
                  onClick={() => setSelectedStoryId(null)}
                >
                  <X size={16} aria-hidden="true" />
                </button>
                <p className="story-eyebrow">{STORY_TYPE_LABELS[selectedStory.story_type]}</p>
                <h2>{selectedStory.title}</h2>
                <p className="story-peek__place">
                  {selectedStory.location.name} · {selectedStory.read_minutes} min read
                </p>
                <Link className="text-link" href={`/stories/${selectedStory.id}` as Route}>
                  Open story <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              </article>
            ) : null}
          </div>
        )}

        {notice && (
          <div className="map-notice" role="status">
            <CircleHelp size={15} aria-hidden="true" />
            <span>{notice}</span>
            <button aria-label="Dismiss notice" onClick={() => setNotice(null)}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        )}

        {!center && (
          <div className="map-invitation" aria-live="polite">
            <span className="invitation-kicker"><Sparkles size={13} /> PLACE-LED DISCOVERY</span>
            <p>Somewhere can mean<br /><em>something.</em></p>
            <span className="invitation-hint">Search for a place to find its stories.</span>
          </div>
        )}

        <div className="filter-rail" aria-label="Filter stories by type">
          {STORY_TYPES.map((type) => (
            <button
              key={type.value}
              className={`filter-chip ${storyType === type.value ? "is-active" : ""}`}
              aria-pressed={storyType === type.value}
              onClick={() => setStoryType(type.value)}
            >
              {type.label}
            </button>
          ))}
          <button
            className={`filter-chip filter-chip--icon ${audioOnly ? "is-active" : ""}`}
            aria-pressed={audioOnly}
            onClick={() => setAudioOnly((value) => !value)}
          >
            <AudioLines size={14} aria-hidden="true" /> Audio
          </button>
          <button
            className={`filter-chip filter-chip--icon ${multipleChaptersOnly ? "is-active" : ""}`}
            aria-pressed={multipleChaptersOnly}
            onClick={() => setMultipleChaptersOnly((value) => !value)}
          >
            <BookOpen size={14} aria-hidden="true" /> Chapters
          </button>
        </div>
      </section>

      <section
        className={`nearby-sheet ${sheetExpanded ? "is-expanded" : ""}`}
        aria-label="Stories near this place"
      >
        <button
          className="sheet-heading"
          aria-expanded={sheetExpanded}
          onClick={() => setSheetExpanded((expanded) => !expanded)}
        >
          <span className="sheet-grab" aria-hidden="true" />
          <span className="sheet-title-group">
            <span className="section-kicker">THE NEARBY INDEX</span>
            <span className="sheet-title">
              {locationLabel ? "Stories around here" : "Stories, by place"}
              <span className="sheet-count">{storyQuery.data?.total ?? 0}</span>
            </span>
          </span>
          <span className="sheet-toggle" aria-hidden="true">
            {sheetExpanded ? <ChevronDown size={16} /> : <ArrowDown size={16} />}
          </span>
        </button>

        {connectionError && center && (
          <div className="inline-error" role="status">
            <span>{connectionError.message}</span>
            <button onClick={() => void storyQuery.refetch()}>Try again</button>
          </div>
        )}

        {storyQuery.isPending && center && (
          <div className="story-row story-row--skeleton" aria-label="Loading stories">
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </div>
        )}

        {!storyQuery.isPending && center && visibleStories.length === 0 && !connectionError && (
          <div className="empty-stories">
            <span className="empty-stories__ornament">∿</span>
            <div>
              <strong>No stories in this view yet.</strong>
              <p>Every place is still becoming. Add a perspective when you’re ready.</p>
            </div>
            <button className="empty-stories__action" onClick={() => setAuthGateOpen(true)}>
              Add a story <ArrowUpRight size={14} aria-hidden="true" />
            </button>
          </div>
        )}

        {!center && (
          <div className="empty-stories empty-stories--start">
            <span className="empty-stories__ornament">∿</span>
            <div>
              <strong>A collection without a feed.</strong>
              <p>Choose a place and see what lives there.</p>
            </div>
            <button className="empty-stories__action" onClick={() => setSearchOpen(true)}>
              Find a place <Search size={14} aria-hidden="true" />
            </button>
          </div>
        )}

        {visibleStories.length > 0 && (
          <div className="story-row">
            {visibleStories.map((story, index) => (
              <StoryCard key={story.id} story={story} index={index} onPreview={selectStory} />
            ))}
          </div>
        )}
      </section>

      <footer className="explore-footer">
        <span>Places connect us. Stories bring them closer.</span>
        <span className="footer-coordinate">PARALLEL · EVERYWHERE, IN TIME</span>
      </footer>

      {authGateOpen && <ContributeGate onClose={() => setAuthGateOpen(false)} />}
      {conciergeOpen && (
        <ConciergePanel
          center={center}
          placeLabel={selectedLocation?.name ?? (userOrigin ? "Near your location" : null)}
          onClose={() => setConciergeOpen(false)}
        />
      )}
    </main>
  );
}

function StoryCard({
  story,
  index,
  onPreview,
}: {
  story: StorySummary;
  index: number;
  onPreview: (storyId: string) => void;
}) {
  return (
    <article className="story-card" style={{ "--card-index": index } as CSSProperties}>
      <button className="story-card__main" onClick={() => onPreview(story.id)}>
        <span className={`story-card__art art-${story.story_type}`}>
          {story.cover_image_url ? (
            <Image
              src={story.cover_image_url}
              alt=""
              width={420}
              height={260}
              unoptimized
              className="story-card__image"
            />
          ) : (
            <span className="story-card__art-mark" aria-hidden="true">
              {story.story_type === "history" ? "Ⅱ" : story.story_type === "fiction" ? "✳" : "∿"}
            </span>
          )}
          {story.audio_available && (
            <span className="story-card__audio" aria-label="Audio available">
              <AudioLines size={13} aria-hidden="true" />
            </span>
          )}
        </span>
        <span className="story-card__text">
          <span className="story-eyebrow">
            {story.is_curated ? "PARALLEL EDITION" : STORY_TYPE_LABELS[story.story_type]}
          </span>
          <strong>{story.title}</strong>
          <span className="story-card__meta">
            {story.location.name} <i>·</i> {story.read_minutes} min
            {story.other_chapter_count > 0 && <><i>·</i> {story.other_chapter_count + 1} chapters</>}
          </span>
        </span>
      </button>
      <Link className="story-card__open" href={`/stories/${story.id}` as Route} aria-label={`Read ${story.title}`}>
        <ArrowUpRight size={16} aria-hidden="true" />
      </Link>
    </article>
  );
}
