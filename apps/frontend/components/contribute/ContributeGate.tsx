"use client";

import { ArrowUpRight, X } from "lucide-react";
import { useEffect, useState } from "react";

export function ContributeGate({ onClose }: { onClose: () => void }) {
  const [authNotice, setAuthNotice] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="gate-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="contribute-gate" role="dialog" aria-modal="true" aria-labelledby="gate-title">
        <button className="gate-close icon-button" onClick={onClose} aria-label="Close sign-in prompt">
          <X size={17} aria-hidden="true" />
        </button>
        <span className="gate-mark" aria-hidden="true">∥</span>
        <p className="section-kicker">A STORY OF YOUR OWN</p>
        <h2 id="gate-title">Your perspective<br /><em>belongs here.</em></h2>
        <p className="gate-copy">
          Reading and exploring are open to everyone. Sign in only when you’re ready to save a draft
          or send a story to the curators.
        </p>
        <button className="gate-primary" onClick={() => setAuthNotice(true)}>
          Continue to sign in <ArrowUpRight size={16} aria-hidden="true" />
        </button>
        {authNotice && (
          <p className="gate-note" role="status">
            Account sign-in is being connected. Your stories won’t be submitted without your consent.
          </p>
        )}
        <button className="gate-dismiss" onClick={onClose}>Keep exploring</button>
      </section>
    </div>
  );
}
