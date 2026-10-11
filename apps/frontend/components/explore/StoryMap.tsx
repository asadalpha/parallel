"use client";

import { Compass, MapPin } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";

import type { StorySummary } from "@/lib/api";

export type MapBounds = {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
};

type Center = { latitude: number; longitude: number };
type ClusterSourceMethods = {
  getClusterExpansionZoom: (clusterId: number) => Promise<number>;
  setData: (data: ReturnType<typeof makeFeatureCollection>) => void;
};

type StoryMapProps = {
  stories: StorySummary[];
  center: Center | null;
  selectedStoryId: string | null;
  onSelectStory: (storyId: string) => void;
  onBoundsChange: (bounds: MapBounds) => void;
};

const styleUrl = process.env.NEXT_PUBLIC_MAP_STYLE_URL;
const WORLD_CENTER: Center = { latitude: 18, longitude: 0 };

function makeFeatureCollection(stories: StorySummary[]) {
  return {
    type: "FeatureCollection" as const,
    features: stories.map((story) => ({
      type: "Feature" as const,
      id: story.id,
      geometry: {
        type: "Point" as const,
        coordinates: [story.location.longitude, story.location.latitude] as [number, number],
      },
      properties: {
        story_id: story.id,
        story_type: story.story_type,
        title: story.title,
        is_curated: story.is_curated,
      },
    })),
  };
}

export function StoryMap({
  stories,
  center,
  selectedStoryId,
  onSelectStory,
  onBoundsChange,
}: StoryMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const initialCenterRef = useRef<Center | null>(center ?? WORLD_CENTER);
  const [mapError, setMapError] = useState(false);

  useEffect(() => {
    if (!containerRef.current || !styleUrl) return;
    let cancelled = false;
    let map: MapLibreMap | null = null;
    const initialCenter = center ?? WORLD_CENTER;

    void import("maplibre-gl").then((maplibregl) => {
      if (cancelled || !containerRef.current) return;
      maplibregl.setWorkerUrl(
        new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString(),
      );

      const instance = new maplibregl.Map({
        container: containerRef.current,
        style: styleUrl,
        center: [initialCenter.longitude, initialCenter.latitude],
        zoom: center ? 12 : 1.4,
        attributionControl: {},
        cooperativeGestures: true,
      });
      map = instance;
      mapRef.current = instance;
      initialCenterRef.current = initialCenter;

      instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

      instance.on("load", () => {
        instance.addSource("parallel-stories", {
          type: "geojson",
          data: makeFeatureCollection(stories),
          cluster: true,
          clusterMaxZoom: 13,
          clusterRadius: 46,
        });

        instance.addLayer({
          id: "parallel-clusters",
          type: "circle",
          source: "parallel-stories",
          filter: ["has", "point_count"],
          paint: {
            "circle-color": "#586d57",
            "circle-radius": ["step", ["get", "point_count"], 16, 8, 21, 24, 27],
            "circle-opacity": 0.92,
            "circle-stroke-color": "#f4f1e9",
            "circle-stroke-width": 2,
          },
        });

        instance.addLayer({
          id: "parallel-cluster-count",
          type: "symbol",
          source: "parallel-stories",
          filter: ["has", "point_count"],
          layout: {
            "text-field": "{point_count_abbreviated}",
            "text-font": ["Open Sans Semibold", "Arial Unicode MS Bold"],
            "text-size": 11,
          },
          paint: { "text-color": "#fffdf7" },
        });

        instance.addLayer({
          id: "parallel-story-points",
          type: "circle",
          source: "parallel-stories",
          filter: ["!", ["has", "point_count"]],
          paint: {
            "circle-color": [
              "match",
              ["get", "story_type"],
              "history",
              "#8d7658",
              "personal_memory",
              "#bc8062",
              "legend",
              "#77708e",
              "fiction",
              "#687e9b",
              "#586d57",
            ],
            "circle-radius": [
              "case",
              ["boolean", ["feature-state", "selected"], false],
              9,
              ["match", ["get", "story_type"], "legend", 6, "personal_memory", 8, 7],
            ],
            "circle-stroke-color": "#fffdf7",
            "circle-stroke-width": ["case", ["get", "is_curated"], 3, 1.5],
          },
        });

        instance.addLayer({
          id: "parallel-story-glyphs",
          type: "symbol",
          source: "parallel-stories",
          filter: ["!", ["has", "point_count"]],
          layout: {
            "text-field": [
              "match",
              ["get", "story_type"],
              "history",
              "H",
              "personal_memory",
              "M",
              "legend",
              "L",
              "fiction",
              "F",
              "E",
            ],
            "text-font": ["Open Sans Semibold", "Arial Unicode MS Bold"],
            "text-size": 8,
            "text-allow-overlap": true,
          },
          paint: { "text-color": "#fffdf7" },
        });

        instance.on("click", "parallel-clusters", async (event) => {
          const feature = instance.queryRenderedFeatures(event.point, {
            layers: ["parallel-clusters"],
          })[0];
          const clusterId = feature?.properties?.cluster_id;
          if (typeof clusterId !== "number" || !feature?.geometry || feature.geometry.type !== "Point") {
            return;
          }
          const source = instance.getSource("parallel-stories") as ClusterSourceMethods | undefined;
          if (!source) return;
          const zoom = await source.getClusterExpansionZoom(clusterId);
          const [longitude, latitude] = feature.geometry.coordinates;
          instance.easeTo({ center: [longitude, latitude], zoom });
        });

        instance.on("click", "parallel-story-points", (event) => {
          const storyId = event.features?.[0]?.properties?.story_id;
          if (typeof storyId === "string") onSelectStory(storyId);
        });

        instance.on("mouseenter", "parallel-clusters", () => {
          instance.getCanvas().style.cursor = "pointer";
        });
        instance.on("mouseleave", "parallel-clusters", () => {
          instance.getCanvas().style.cursor = "";
        });
        instance.on("mouseenter", "parallel-story-points", () => {
          instance.getCanvas().style.cursor = "pointer";
        });
        instance.on("mouseleave", "parallel-story-points", () => {
          instance.getCanvas().style.cursor = "";
        });

        instance.on("moveend", () => {
          const bounds = instance.getBounds();
          onBoundsChange({
            min_lat: bounds.getSouth(),
            min_lon: bounds.getWest(),
            max_lat: bounds.getNorth(),
            max_lon: bounds.getEast(),
          });
        });

        instance.on("error", () => setMapError(true));
        emitBounds(instance, onBoundsChange);
      });
    }).catch(() => setMapError(true));

    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // Map construction is intentionally one-time; center and markers update below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [styleUrl]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !center) return;
    const previous = initialCenterRef.current;
    if (previous?.latitude === center.latitude && previous.longitude === center.longitude) return;
    initialCenterRef.current = center;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const options = { center: [center.longitude, center.latitude] as [number, number], zoom: 13 };
    if (reducedMotion) map.jumpTo(options);
    else map.flyTo({ ...options, duration: 900, essential: false });
  }, [center]);

  useEffect(() => {
    const source = mapRef.current?.getSource("parallel-stories") as ClusterSourceMethods | undefined;
    if (source) source.setData(makeFeatureCollection(stories));
  }, [stories]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getSource("parallel-stories")) return;
    for (const story of stories) {
      map.setFeatureState(
        { source: "parallel-stories", id: story.id },
        { selected: story.id === selectedStoryId },
      );
    }
  }, [selectedStoryId, stories]);

  if (!styleUrl || mapError) {
    return (
      <div className="map-blank" aria-label="Story map">
        <svg className="map-blank__contours" viewBox="0 0 900 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <path d="M-40 120c150-100 265 40 410-4s262-92 565-6M-80 190c177-94 272 44 438 5s281-81 600 2M-50 270c184-85 300 22 466-10s282-56 565 18M-60 360c192-72 307 4 472-19s276-22 571 37M-40 450c193-47 295-19 465-30s288 8 573 50M-30 545c174-19 315-45 500-45s298 37 550 62" />
          <path d="M160-30c60 100-4 164 47 256s6 171 76 245 29 127 65 209M330-20c49 82 4 156 55 231s27 163 83 229 42 140 81 217M530-20c-2 103 80 132 54 236s41 148 27 233 81 124 80 205M720-10c-59 97 11 158-29 252s15 160-26 233 18 125-8 201" />
          <path d="M64 320c78-64 165-56 225-4s61 105 17 167-113 92-192 46-118-131-50-209ZM602 104c78-45 169-28 198 31s-5 126-85 152-156 3-174-66 7-91 61-117Z" />
        </svg>
        <div className="map-blank__grain" aria-hidden="true" />
        <div className="map-blank__note">
          <span className="map-blank__symbol"><Compass size={17} strokeWidth={1.5} /></span>
          <span>{mapError ? "The map is taking a moment" : "A place, when you’re ready"}</span>
        </div>
        {center && !mapError && (
          <div className="map-blank__pin" aria-hidden="true">
            <MapPin size={17} strokeWidth={1.6} />
          </div>
        )}
      </div>
    );
  }

  return <div className="story-map" ref={containerRef} aria-label="Interactive map of published stories" />;
}

function emitBounds(map: MapLibreMap, onBoundsChange: StoryMapProps["onBoundsChange"]) {
  const bounds = map.getBounds();
  onBoundsChange({
    min_lat: bounds.getSouth(),
    min_lon: bounds.getWest(),
    max_lat: bounds.getNorth(),
    max_lon: bounds.getEast(),
  });
}
