"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { Incident, IncidentStatus, Severity } from "@/lib/api";
import { formatCompactDate } from "@/lib/presentation";

interface IncidentSidebarProps {
  incidents: Incident[];
  loading: boolean;
  publicDemoMode: boolean;
  selectedId: string | null;
  onCreate: () => void;
  onSelect: (incidentId: string) => void;
}

type StatusFilter = "all" | IncidentStatus;
type SeverityFilter = "all" | Severity;

export function IncidentSidebar({
  incidents,
  loading,
  publicDemoMode,
  selectedId,
  onCreate,
  onSelect,
}: IncidentSidebarProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const incidentListRef = useRef<HTMLElement>(null);

  const filteredIncidents = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return incidents.filter((incident) => {
      const matchesQuery =
        !normalizedQuery ||
        incident.title.toLocaleLowerCase().includes(normalizedQuery) ||
        incident.repository_full_name?.toLocaleLowerCase().includes(normalizedQuery);
      return (
        matchesQuery &&
        (status === "all" || incident.status === status) &&
        (severity === "all" || incident.severity === severity)
      );
    });
  }, [incidents, query, severity, status]);

  useEffect(() => {
    const selectedRow = incidentListRef.current?.querySelector<HTMLElement>(
      '[aria-current="page"]',
    );
    selectedRow?.scrollIntoView({ block: "nearest" });
  }, [filteredIncidents, selectedId]);

  return (
    <aside className="incident-sidebar" aria-label="Incident navigator">
      <div className="sidebar-heading">
        <div>
          <p className="section-kicker">Workspace</p>
          <div className="heading-with-count">
            <h1>Incidents</h1>
            <span>{incidents.length}</span>
          </div>
        </div>
        {!publicDemoMode && (
          <button className="new-incident-button" type="button" onClick={onCreate}>
            <Icon name="plus" size={16} />
            <span>New</span>
          </button>
        )}
      </div>

      <div className="incident-controls">
        <label className="search-control">
          <span className="sr-only">Search incidents</span>
          <Icon name="search" size={17} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search incidents or repositories"
          />
        </label>
        <div className="filter-row">
          <label>
            <span className="sr-only">Filter by status</span>
            <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>
              <option value="all">All statuses</option>
              <option value="open">Open</option>
              <option value="investigating">Investigating</option>
              <option value="resolved">Resolved</option>
            </select>
          </label>
          <label>
            <span className="sr-only">Filter by severity</span>
            <select
              value={severity}
              onChange={(event) => setSeverity(event.target.value as SeverityFilter)}
            >
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
        </div>
      </div>

      <div className="incident-list-scroll" aria-live="polite">
        {loading ? (
          <div className="incident-skeleton-list" aria-label="Loading incidents">
            {Array.from({ length: 6 }, (_, index) => (
              <div className="incident-skeleton" key={index}>
                <span />
                <span />
              </div>
            ))}
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="sidebar-empty">
            <Icon name="search" size={22} />
            <strong>No matching incidents</strong>
            <p>Try a different search or filter.</p>
          </div>
        ) : (
          <nav className="incident-list" aria-label="Recorded incidents" ref={incidentListRef}>
            {filteredIncidents.map((incident) => {
              const isSelected = incident.id === selectedId;
              return (
                <button
                  aria-current={isSelected ? "page" : undefined}
                  className={`incident-row ${isSelected ? "is-selected" : ""}`}
                  key={incident.id}
                  type="button"
                  onClick={() => onSelect(incident.id)}
                >
                  <span className={`severity-marker severity-marker-${incident.severity}`} />
                  <span className="incident-row-copy">
                    <strong>{incident.title}</strong>
                    <span className="incident-row-meta">
                      <span className={`status-dot status-dot-${incident.status}`} />
                      {incident.status}
                      <span aria-hidden="true">·</span>
                      {formatCompactDate(incident.created_at)}
                    </span>
                    {incident.repository_full_name && (
                      <span className="incident-repository">
                        <Icon name="repository" size={13} />
                        {incident.repository_full_name}
                      </span>
                    )}
                  </span>
                  <Icon className="row-chevron" name="chevron-right" size={17} />
                </button>
              );
            })}
          </nav>
        )}
      </div>

      <footer className="sidebar-footer">
        <span>Search and filter incidents</span>
        <span>{filteredIncidents.length} shown</span>
      </footer>
    </aside>
  );
}
