"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { IncidentCreate, Severity, severities } from "@/lib/api";
import { currentLocalDatetime, messageFrom } from "@/lib/presentation";

interface NewIncidentDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (input: IncidentCreate) => Promise<void>;
}

export function NewIncidentDialog({ open, onClose, onCreate }: NewIncidentDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [startedAt, setStartedAt] = useState(currentLocalDatetime);
  const [repositoryFullName, setRepositoryFullName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function resetForm() {
    setTitle("");
    setDescription("");
    setSeverity("medium");
    setStartedAt(currentLocalDatetime());
    setRepositoryFullName("");
    setError(null);
  }

  function closeDialog() {
    if (submitting) return;
    resetForm();
    onClose();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsedStartedAt = new Date(startedAt);
    if (!startedAt || Number.isNaN(parsedStartedAt.getTime())) {
      setError("Enter a valid started time.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onCreate({
        title,
        description,
        severity,
        started_at: parsedStartedAt.toISOString(),
        repository_full_name: repositoryFullName.trim() || undefined,
      });
      resetForm();
      onClose();
    } catch (reason: unknown) {
      setError(messageFrom(reason, "Unable to create incident"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <dialog
      aria-labelledby="new-incident-title"
      className="incident-dialog"
      ref={dialogRef}
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClose={() => {
        if (open) onClose();
      }}
    >
      <form method="dialog" className="incident-dialog-form" onSubmit={handleSubmit}>
        <header className="dialog-header">
          <div className="dialog-icon"><Icon name="plus" size={20} /></div>
          <div>
            <p className="section-kicker">New record</p>
            <h2 id="new-incident-title">Create incident</h2>
            <p>Capture the operational facts and relevant repository.</p>
          </div>
          <button
            aria-label="Close create incident dialog"
            className="icon-button"
            disabled={submitting}
            type="button"
            onClick={closeDialog}
          >
            <Icon name="x" size={18} />
          </button>
        </header>

        <div className="dialog-body">
          {error && <div className="form-error" role="alert">{error}</div>}
          <label className="field-label">
            <span>Title</span>
            <input
              autoFocus
              required
              maxLength={200}
              minLength={3}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Checkout errors after deployment"
            />
          </label>
          <label className="field-label">
            <span>Description</span>
            <textarea
              required
              maxLength={10_000}
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Describe what is failing, when it started, and who is affected."
            />
          </label>
          <label className="field-label">
            <span>GitHub repository <small>Optional</small></span>
            <div className="input-with-icon">
              <Icon name="github" size={17} />
              <input
                pattern="[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}"
                value={repositoryFullName}
                onChange={(event) => setRepositoryFullName(event.target.value)}
                placeholder="owner/repository"
              />
            </div>
          </label>
          <div className="dialog-field-row">
            <label className="field-label">
              <span>Severity</span>
              <select
                value={severity}
                onChange={(event) => setSeverity(event.target.value as Severity)}
              >
                {severities.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label className="field-label">
              <span>Started time</span>
              <input
                required
                type="datetime-local"
                value={startedAt}
                onChange={(event) => setStartedAt(event.target.value)}
              />
            </label>
          </div>
        </div>

        <footer className="dialog-actions">
          <button className="secondary-button" disabled={submitting} type="button" onClick={closeDialog}>
            Cancel
          </button>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? <span className="button-spinner" /> : <Icon name="plus" size={16} />}
            {submitting ? "Creating incident…" : "Create incident"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
