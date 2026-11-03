"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { hostedDemo } from "@/lib/demo-mode";
import {
  Flag,
  Radar,
  Layers3,
  FileCheck2,
  ArrowUpRight,
  ShieldCheck,
  Github,
  Sparkles,
  Command,
} from "lucide-react";
export function Shell({
  children,
  onScan,
}: {
  children: React.ReactNode;
  onScan?: () => void;
}) {
  const path = usePathname();
  const query = useSearchParams();
  const view = query.get("view") || "radar";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <Flag size={22} fill="currentColor" strokeWidth={1.7} />
          </span>
          red flag<span className="brand-dot">.</span>
        </Link>
        <div className="sidebar-label">YOUR EARLY WARNING SYSTEM</div>
        <nav aria-label="Main navigation">
          {[
            { id: "radar", icon: Radar, label: "The radar", href: "/" },
            {
              id: "evidence",
              icon: Layers3,
              label: "Evidence feed",
              href: "/?view=evidence",
            },
            {
              id: "actions",
              icon: FileCheck2,
              label: "Action desk",
              href: "/?view=actions",
            },
          ].map((item) => (
            <Link
              key={item.id}
              href={item.href}
              className={`nav-link ${path === "/" && view === item.id ? "active" : ""}`}
            >
              <item.icon size={18} />
              {item.label}
              {item.id === "radar" && <span className="nav-live" />}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="tiny-eyebrow">
            <Sparkles size={14} /> GOOD TO KNOW
          </span>
          <p>
            Less doomscrolling.
            <br />
            More connecting the dots.
          </p>
          <span>Made for what&apos;s in your cart.</span>
        </div>
        <div className="sidebar-bottom">
          <div className="privacy-mini">
            <ShieldCheck size={17} />
            <div>
              Privacy at the edge<small>Personal details scrubbed</small>
            </div>
            <span className="status-dot" />
          </div>
          <a
            href="https://github.com/adarshmaurya700/RED-FLAG"
            target="_blank"
            rel="noreferrer"
            className="repo-link"
          >
            <Github size={15} /> Built in the open <ArrowUpRight size={14} />
          </a>
          <div className="operator">
            <span className="avatar">rf</span>
            <div>
              Operator workspace<small>India · single operator</small>
            </div>
            <Command size={15} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="country-dot" /> INDIA{" "}
            <span className="topbar-slash">/</span>
            <span className="muted">Product safety intelligence</span>
          </div>
          <div className="topbar-right">
            <span className="local-pill">
              <span className="status-dot" /> SIGNALS, NOT GUESSWORK
            </span>
            {onScan && (
              <button className="button small dark" onClick={onScan}>
                <Radar size={15} /> {hostedDemo ? "Search reports" : "New scan"}
              </button>
            )}
          </div>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <span>
            <Flag size={13} /> red flag. Know before you consume.
          </span>
          <span>Evidence-led triage · Human-reviewed action</span>
        </footer>
      </div>
    </div>
  );
}
