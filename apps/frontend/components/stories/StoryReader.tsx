"use client";

import Image from "next/image";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowLeft,
  ArrowUpRight,
  AudioLines,
  BookOpen,
  Clock3,
  MapPin,
  Share2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ContributeGate } from "@/components/contribute/ContributeGate";
import { fetchStories, fetchStory } from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  history: "History",
  personal_memory: "Personal memory",
  legend: "Local legend",
  fiction: "Fiction",
  editorial: "Editorial",
};

export function StoryReader({ storyId }: { storyId: string }) {
  const [gateOpen, setGateOpen] = useState(false);
  const [shareMessage, setShareMessage] = useState("");
  const storyQuery = useQuery({
    queryKey: ["story", storyId],
    queryFn: ({ signal }) => fetchStory(storyId, signal),
    retry: false,
  });
  const chapterQuery = useQuery({
    queryKey: ["chapters", storyQuery.data?.location_id],
    queryFn: ({ signal }) => fetchStories({ locationId: storyQuery.data!.location_id }, signal),
    enabled: Boolean(storyQuery.data?.location_id),
    retry: false,
  });
  const chapters = useMemo(
    () => chapterQuery.data?.items.filter((chapter) => chapter.id !== storyId) ?? [],
    [chapterQuery.data?.items, storyId],
  );

  async function shareStory() {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: story?.title, url });
      else {
        await navigator.clipboard.writeText(url);
        setShareMessage("Link copied");
        window.setTimeout(() => setShareMessage(""), 2200);
      }
    } catch {
      setShareMessage("This story is ready to share from your browser.");
      window.setTimeout(() => setShareMessage(""), 2200);
    }
  }

  if (storyQuery.isPending) {
    return (
      <main className="reader-state">
        <div className="reader-skeleton" />
        <span>Opening this story…</span>
      </main>
    );
  }

  if (!storyQuery.data || storyQuery.error) {
    return (
      <main className="reader-state reader-state--missing">
        <Link className="reader-back" href="/">
          <ArrowLeft size={16} aria-hidden="true" /> Back to the atlas
        </Link>
        <span className="section-kicker">STORY NOT FOUND</span>
        <h1>This page is quiet.</h1>
        <p>The story may have moved or is no longer published.</p>
        <Link className="reader-home-link" href="/">Explore nearby stories</Link>
      </main>
    );
  }

  const story = storyQuery.data;
  const paragraphs = story.body.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean);
  const sourceEntries = story.historical_sources.flatMap((source) => Object.entries(source));

  return (
    <main className="reader-page">
      <header className="reader-topbar">
        <Link className="reader-back" href="/">
          <ArrowLeft size={16} strokeWidth={1.7} aria-hidden="true" />
          <span>Explore</span>
        </Link>
        <Link className="wordmark reader-wordmark" href="/" aria-label="Parallel home">
          <span className="wordmark-glyph" aria-hidden="true">∥</span><span>parallel</span>
        </Link>
        <button className="reader-share" onClick={() => void shareStory()} aria-label="Share story">
          <Share2 size={16} strokeWidth={1.7} aria-hidden="true" />
          <span>{shareMessage || "Share"}</span>
        </button>
      </header>

      <article className="story-article">
        {story.cover_image_url && (
          <figure className="reader-cover">
            <Image
              src={story.cover_image_url}
              alt={story.media[0]?.alt_text || `Cover image for ${story.title}`}
              width={1440}
              height={880}
              priority
              unoptimized
              className="reader-cover__image"
            />
            <figcaption>{story.location.name}</figcaption>
          </figure>
        )}

        <div className="article-heading">
          <div className="article-kicker-row">
            <span className="story-eyebrow">{story.is_curated ? "PARALLEL EDITION" : TYPE_LABELS[story.story_type]}</span>
            <span className="article-dot" aria-hidden="true">·</span>
            <span className="story-eyebrow">CHAPTER {story.other_chapter_count + 1}</span>
          </div>
          <h1>{story.title}</h1>
          <p className="article-deck">{story.category}</p>
          <div className="article-meta">
            <span><MapPin size={14} aria-hidden="true" /> {story.location.name}{story.location.city ? `, ${story.location.city}` : ""}</span>
            <span><Clock3 size={14} aria-hidden="true" /> {story.read_minutes} min read</span>
            {story.audio_available && <span><AudioLines size={14} aria-hidden="true" /> Audio edition</span>}
          </div>
          {story.audio.length > 0 && (
            <div className="audio-card">
              <div className="audio-card__icon"><AudioLines size={18} aria-hidden="true" /></div>
              <div className="audio-card__body">
                <span className="section-kicker">LISTEN TO THIS STORY</span>
                <audio controls preload="none" src={story.audio[0].audio_url}>
                  Your browser does not support audio playback. The full transcript is below.
                </audio>
              </div>
              <span className="audio-card__label">SYNTHETIC NARRATION</span>
            </div>
          )}
        </div>

        <div className="article-body">
          {paragraphs.map((paragraph, index) => (
            <p key={`${index}-${paragraph.slice(0, 12)}`}>{paragraph}</p>
          ))}
        </div>

        {story.media.length > 0 && (
          <div className="reader-gallery" aria-label="Story photographs">
            {story.media.map((media) => (
              <figure key={media.id}>
                <Image
                  src={media.media_url}
                  alt={media.alt_text || media.caption || "Story photograph"}
                  width={960}
                  height={720}
                  unoptimized
                  className="reader-gallery__image"
                />
                {media.caption && <figcaption>{media.caption}</figcaption>}
              </figure>
            ))}
          </div>
        )}

        {sourceEntries.length > 0 && (
          <section className="source-notes" aria-labelledby="sources-heading">
            <span className="section-kicker" id="sources-heading">SOURCES & NOTES</span>
            <ul>
              {story.historical_sources.map((source, index) => {
                const title = source.title || source.name || source.url || "Source";
                const href = safeExternalUrl(source.url);
                return (
                  <li key={`${index}-${title}`}>
                    {href ? <a href={href} target="_blank" rel="noreferrer">{title}<ArrowUpRight size={12} /></a> : title}
                    {source.note && <span>{source.note}</span>}
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <section className="parallel-chapters" aria-labelledby="chapters-heading">
          <div className="chapters-heading-row">
            <div>
              <span className="section-kicker">THE SAME PLACE, ANOTHER ANGLE</span>
              <h2 id="chapters-heading">More stories at {story.location.name}</h2>
            </div>
            <BookOpen size={20} strokeWidth={1.5} aria-hidden="true" />
          </div>
          {chapterQuery.isPending && <p className="quiet-state">Finding other chapters…</p>}
          {chapters.length > 0 && (
            <div className="chapter-list">
              {chapters.map((chapter) => (
                <Link className="chapter-link" href={`/stories/${chapter.id}` as Route} key={chapter.id}>
                  <span className="chapter-link__number">↳</span>
                  <span className="chapter-link__copy">
                    <span className="story-eyebrow">{TYPE_LABELS[chapter.story_type]}</span>
                    <strong>{chapter.title}</strong>
                    <small>{chapter.read_minutes} min read</small>
                  </span>
                  <ArrowUpRight size={16} aria-hidden="true" />
                </Link>
              ))}
            </div>
          )}
          {!chapterQuery.isPending && chapters.length === 0 && (
            <p className="quiet-state">This place is waiting for another perspective.</p>
          )}
        </section>

        <div className="article-contribute">
          <span className="contribute-flourish" aria-hidden="true">∿</span>
          <p>Know this place another way?</p>
          <button className="text-link" onClick={() => setGateOpen(true)}>
            Add your perspective <ArrowUpRight size={14} aria-hidden="true" />
          </button>
        </div>
      </article>

      <footer className="reader-footer">
        <Link href="/">∥ parallel</Link>
        <span>Every place has more than one story.</span>
      </footer>
      {gateOpen && <ContributeGate onClose={() => setGateOpen(false)} />}
    </main>
  );
}

function safeExternalUrl(value: string | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
