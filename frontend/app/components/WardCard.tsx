"use client";

import { useEffect, useState } from "react";
import {
  Ward,
  categoryColor,
  formatContextTime,
  formatNumber,
  isUsableCurrentWard,
} from "./sentinelTypes";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type ActionItem = {
  lever?: string;
  label?: string;
  evidence?: string | null;
  reason?: string | null;
  actions?: string[];
  priority?: number | null;
  intervention_potential?: number | null;
  intervention_potential_pct?: number | null;
  why?: string[];
};

type EnforcementPlan = {
  ward?: string;
  recommended?: ActionItem[];
  not_recommended?: ActionItem[];
  current_aqi_context?: number | null;
  base_aqi?: number | null;
  aqi_context_source?: string;
  aqi_context_reading_time?: string | null;
  aqi_context_method?: string;
};

type Advisory = {
  ward?: string;
  aqi?: number | null;
  category?: { en?: string; mr?: string };
  advisory?: { en?: string; mr?: string };
  sensitive_groups?: { en?: string; mr?: string };
  aqi_context_source?: string;
  aqi_context_reading_time?: string | null;
  aqi_context_method?: string;
};

type Props = {
  selectedWard: Ward | null;
  onClose: () => void;
};

function potential(action: ActionItem): string | null {
  const raw = action.intervention_potential_pct ?? action.intervention_potential;
  if (raw == null || !Number.isFinite(raw)) return null;
  const value = raw <= 1 ? raw * 100 : raw;
  return `${value.toFixed(1)}%`;
}

export default function WardCard({ selectedWard, onClose }: Props) {
  const [plan, setPlan] = useState<EnforcementPlan | null>(null);
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [loading, setLoading] = useState(false);
  const [partialError, setPartialError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedWard) {
      setPlan(null);
      setAdvisory(null);
      setPartialError(null);
      return;
    }

    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setPlan(null);
      setAdvisory(null);
      setPartialError(null);

      const encoded = encodeURIComponent(selectedWard!.name);

      try {
        const results = await Promise.allSettled([
          fetch(`${BACKEND}/api/enforce/${encoded}`, {
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(`${BACKEND}/api/advisory/${encoded}`, {
            cache: "no-store",
            signal: controller.signal,
          }),
        ]);

        if (controller.signal.aborted) return;

        let failures = 0;

        const enforcement = results[0];
        if (enforcement.status === "fulfilled" && enforcement.value.ok) {
          setPlan(await enforcement.value.json());
        } else {
          failures += 1;
        }

        const health = results[1];
        if (health.status === "fulfilled" && health.value.ok) {
          setAdvisory(await health.value.json());
        } else {
          failures += 1;
        }

        if (failures === 2) {
          setPartialError("Decision-intelligence endpoints are temporarily unavailable. Current AQI context is still shown below.");
        } else if (failures === 1) {
          setPartialError("One supporting intelligence service is temporarily unavailable. Available results are shown.");
        }
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setPartialError("Supporting decision intelligence could not be refreshed.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    load();
    return () => controller.abort();
  }, [selectedWard]);

  if (!selectedWard) return null;

  const ward = selectedWard;
  const usable = isUsableCurrentWard(ward);
  const color = categoryColor(usable ? ward.category : undefined);
  const recommended = plan?.recommended ?? [];
  const base = ward.base_modeled_aqi;
  const factor = ward.historical_spatial_factor;
  const adjusted = ward.historical_factor_applied_to_current_aqi === true;

  return (
    <aside className="sentinel-ward-card sentinel-panel">
      <div className="sentinel-card-header">
        <div>
          <div className="sentinel-eyebrow">WARD INTELLIGENCE</div>
          <h2>{ward.name}</h2>
          <p>Current air-quality context and explainable decision support</p>
        </div>
        <button className="sentinel-close" type="button" onClick={onClose} aria-label="Close ward panel">×</button>
      </div>

      <section className="sentinel-aqi-hero" style={{ borderColor: `${color}45` }}>
        <div className="sentinel-aqi-number" style={{ background: color }}>
          <span>AQI</span>
          <strong>{usable ? formatNumber(ward.aqi, 0) : "—"}</strong>
        </div>
        <div className="sentinel-aqi-copy">
          <div className="sentinel-aqi-category" style={{ color }}>
            {usable ? ward.category : "Current context unavailable"}
          </div>
          <p>
            {usable
              ? "Historically adjusted modeled CPCB-method AQI estimate"
              : ward.error || "The latest modeled context is stale, incomplete, or unavailable."}
          </p>
          <div className="sentinel-chip-row">
            <span className={`sentinel-chip ${ward.data_fresh ? "ok" : "warn"}`}>
              {ward.data_fresh ? "Fresh" : "Not fresh"}
            </span>
            <span className={`sentinel-chip ${ward.data_usable ? "ok" : "warn"}`}>
              {ward.data_usable ? "Usable" : "Not usable"}
            </span>
            <span className="sentinel-chip neutral">Modeled · not observed</span>
          </div>
        </div>
      </section>

      <div className="sentinel-metric-grid">
        <div><span>Base modeled AQI</span><strong>{formatNumber(base, 0)}</strong></div>
        <div><span>Spatial factor</span><strong>{adjusted ? formatNumber(factor, 3) : "Not applied"}</strong></div>
        <div><span>Dominant pollutant</span><strong>{ward.dominant || "—"}</strong></div>
        <div><span>Data age</span><strong>{ward.data_age_hours != null ? `${formatNumber(ward.data_age_hours, 1)} h` : "—"}</strong></div>
      </div>

      <section className="sentinel-section">
        <div className="sentinel-section-title">Pollutant context</div>
        <div className="sentinel-pollutants">
          {[
            ["PM2.5", ward.pm25, "µg/m³"],
            ["PM10", ward.pm10, "µg/m³"],
            ["NO₂", ward.no2, "µg/m³"],
            ["SO₂", ward.so2, "µg/m³"],
            ["O₃", ward.ozone, "µg/m³"],
            ["CO", ward.co, "mg/m³"],
          ].map(([label, value, unit]) => (
            <div key={String(label)}>
              <span>{label}</span>
              <strong>{formatNumber(value as number | null | undefined, value === ward.co ? 4 : 2)}</strong>
              <small>{unit}</small>
            </div>
          ))}
        </div>
      </section>

      {partialError && <div className="sentinel-inline-warning">{partialError}</div>}
      {loading && <div className="sentinel-loading-line">Loading advisory and enforcement intelligence…</div>}

      {advisory && !loading && (
        <section className="sentinel-section sentinel-advisory">
          <div className="sentinel-section-title">Citizen health advisory</div>
          <p className="sentinel-section-primary">{advisory.advisory?.en || "Advisory unavailable."}</p>
          {advisory.sensitive_groups?.en && <p className="sentinel-section-secondary">{advisory.sensitive_groups.en}</p>}
          {advisory.advisory?.mr && (
            <details>
              <summary>मराठी सल्ला</summary>
              <p>{advisory.advisory.mr}</p>
              {advisory.sensitive_groups?.mr && <p className="sentinel-section-secondary">{advisory.sensitive_groups.mr}</p>}
            </details>
          )}
        </section>
      )}

      {plan && !loading && (
        <section className="sentinel-section">
          <div className="sentinel-section-heading-row">
            <div className="sentinel-section-title">Enforcement priorities</div>
            <span className="sentinel-decision-badge">Decision support</span>
          </div>

          {recommended.length === 0 ? (
            <p className="sentinel-section-secondary">No ranked enforcement actions returned.</p>
          ) : (
            <div className="sentinel-action-list">
              {recommended.slice(0, 4).map((action, index) => (
                <article className="sentinel-action" key={`${action.lever || action.label || "action"}-${index}`}>
                  <div className="sentinel-action-rank">{index + 1}</div>
                  <div>
                    <div className="sentinel-action-title-row">
                      <strong>{action.label || action.lever || "Recommended action"}</strong>
                      {potential(action) && <span>{potential(action)} potential</span>}
                    </div>
                    {(action.reason || action.evidence) && <p>{action.reason || action.evidence}</p>}
                    {action.actions && action.actions.length > 0 && (
                      <ul>
                        {action.actions.slice(0, 3).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      <footer className="sentinel-provenance">
        <div>
          <span>Context time</span>
          <strong>{formatContextTime(ward.aqi_context_time || ward.reading_time)}</strong>
        </div>
        <p>
          Derived from CAMS Global modeled concentrations using CPCB-method breakpoint logic.
          {adjusted ? " A historical composite-AQI spatial factor is applied only to the final localized AQI estimate." : ""}
          {" "}Pollutant concentrations and sub-indices remain unadjusted. This is not an official CPCB monitoring-station observation.
        </p>
      </footer>
    </aside>
  );
}
