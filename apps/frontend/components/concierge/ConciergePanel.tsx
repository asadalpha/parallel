"use client";

import Link from "next/link";
import type { Route } from "next";
import {
  ArrowUpRight,
  AudioLines,
  Compass,
  Footprints,
  LocateFixed,
  MapPin,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";

import { ApiError, requestAnotherAngle, requestRecommendation } from "@/lib/api";
import type { ConciergeRequest, RecommendationRead } from "@/lib/api";

type Center = { latitude: number; longitude: number };

const MOODS: Array<{ value: ConciergeRequest["mood"]; label: string }> = [
  { value: "cozy", label: "Cozy" },
  { value: "curious", label: "Curious" },
  { value: "spooky", label: "Eerie" },
  { value: "reflective", label: "Reflective" },
  { value: "surprise", label: "Surprise me" },
];

const TIMES = [15, 30, 60, 120];
const TRAVEL: Array<{ value: ConciergeRequest["travel_preference"]; label: string }> = [
  { value: "walking_nearby", label: "On foot" },
  { value: "a_little_farther", label: "A little farther" },
  { value: "any_distance", label: "Anywhere here" },
];

export function ConciergePanel({
  center,
  placeLabel,
  onRequestLocation,
  onChoosePlace,
  onClose,
}: {
  center: Center | null;
  placeLabel: string | null;
  onRequestLocation: () => void;
  onChoosePlace: () => void;
  onClose: () => void;
}) {
  const [mood, setMood] = useState<ConciergeRequest["mood"]>("curious");
  const [time, setTime] = useState(30);
  const [travel, setTravel] = useState<ConciergeRequest["travel_preference"]>("walking_nearby");
  const [recommendation, setRecommendation] = useState<RecommendationRead | null>(null);
  const [pending, setPending] = useState(false);
  const [anotherPending, setAnotherPending] = useState(false);
  const [error, setError] = useState("");

  async function recommend() {
    if (!center) {
      setError("Choose a place or use your location first.");
      return;
    }
    setError("");
    setPending(true);
    try {
      const result = await requestRecommendation({
        mood,
        time_available_minutes: time,
        travel_preference: travel,
        latitude: center.latitude,
        longitude: center.longitude,
      });
      setRecommendation(result);
    } catch (requestError) {
      setRecommendation(null);
      const apiError = requestError as ApiError;
      setError(
        apiError.status === 404
          ? "No published stories fit this search yet. Try another place or mood."
          : apiError.message,
      );
    } finally {
      setPending(false);
    }
  }

  async function anotherAngle() {
    if (!recommendation || recommendation.other_chapter_count === 0) return;
    setAnotherPending(true);
    setError("");
    try {
      setRecommendation(
        await requestAnotherAngle(
          recommendation.story.location_id,
          recommendation.story.id,
        ),
      );
    } catch (requestError) {
      setError((requestError as ApiError).message);
    } finally {
      setAnotherPending(false);
    }
  }

  return (
    <div className="concierge-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="concierge-panel" role="dialog" aria-modal="true" aria-labelledby="concierge-title">
        <button className="concierge-close icon-button" onClick={onClose} aria-label="Close Story Concierge">
          <X size={17} aria-hidden="true" />
        </button>
        <div className="concierge-heading">
          <span className="concierge-mark"><Sparkles size={17} strokeWidth={1.6} aria-hidden="true" /></span>
          <span className="section-kicker">THE STORY CONCIERGE</span>
        </div>
        <h2 id="concierge-title">Take me<br /><em>somewhere.</em></h2>
        <p className="concierge-description">
          One real story, tied to a real place. Chosen for the kind of moment you’re in.
        </p>
        <p className="concierge-place">
          <Compass size={14} aria-hidden="true" />
          {placeLabel || (center ? "Near your location" : "Choose a place on the map first")}
        </p>

        {!center && (
          <div className="concierge-origin-picker">
            <p>Choose a starting place. We won’t guess where you are.</p>
            <div>
              <button onClick={onRequestLocation}>
                <LocateFixed size={14} aria-hidden="true" /> Use my location
              </button>
              <button onClick={onChoosePlace}>
                <MapPin size={14} aria-hidden="true" /> Search a place
              </button>
            </div>
          </div>
        )}

        <fieldset className="concierge-fieldset">
          <legend className="section-kicker">WHAT ARE YOU IN THE MOOD FOR?</legend>
          <div className="concierge-options">
            {MOODS.map((option) => (
              <button
                key={option.value}
                className={`concierge-option ${mood === option.value ? "is-selected" : ""}`}
                aria-pressed={mood === option.value}
                onClick={() => setMood(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="concierge-fieldset">
          <legend className="section-kicker">HOW MUCH TIME DO YOU HAVE?</legend>
          <div className="concierge-options concierge-options--tight">
            {TIMES.map((minutes) => (
              <button
                key={minutes}
                className={`concierge-option ${time === minutes ? "is-selected" : ""}`}
                aria-pressed={time === minutes}
                onClick={() => setTime(minutes)}
              >
                {minutes === 120 ? "Longer" : `${minutes} min`}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset className="concierge-fieldset">
          <legend className="section-kicker">HOW FAR?</legend>
          <div className="concierge-options concierge-options--tight">
            {TRAVEL.map((option) => (
              <button
                key={option.value}
                className={`concierge-option ${travel === option.value ? "is-selected" : ""}`}
                aria-pressed={travel === option.value}
                onClick={() => setTravel(option.value)}
              >
                {option.value === "walking_nearby" && <Footprints size={13} aria-hidden="true" />}
                {option.label}
              </button>
            ))}
          </div>
        </fieldset>

        {error && <p className="concierge-error" role="status">{error}</p>}

        <button
          className="concierge-submit"
          onClick={() => void recommend()}
          disabled={pending || !center}
        >
          {pending ? "Finding a story…" : "Find me a story"}
          {!pending && <ArrowUpRight size={16} aria-hidden="true" />}
        </button>

        {recommendation && (
          <article className="recommendation-card" aria-live="polite">
            <span className="section-kicker">A PLACE TO BEGIN</span>
            <h3>{recommendation.story.title}</h3>
            <p>{recommendation.explanation}</p>
            <div className="recommendation-meta">
              <span>{recommendation.story.location.name}</span>
              <span>·</span>
              <span>{recommendation.story.read_minutes} min</span>
              {recommendation.audio_available && <AudioLines size={13} aria-label="Audio available" />}
            </div>
            <div className="recommendation-actions">
              <Link href={`/stories/${recommendation.story.id}` as Route} onClick={onClose}>
                Open story <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
              {recommendation.other_chapter_count > 0 && (
                <button onClick={() => void anotherAngle()} disabled={anotherPending}>
                  {anotherPending ? "Finding…" : "Another angle"}
                </button>
              )}
            </div>
            {recommendation.fallback_used && (
              <small className="recommendation-note">Grounded in published stories. No AI-generated story text.</small>
            )}
          </article>
        )}
      </section>
    </div>
  );
}
