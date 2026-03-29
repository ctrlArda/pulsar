import { useState } from 'react';
import type { TelemetrySnapshot, TurkishSatelliteAssessment } from '../types/helioguard';

function riskColor(value: number): string {
  if (value >= 70) return 'var(--danger)';
  if (value >= 45) return 'var(--warning)';
  return 'var(--text)';
}

function riskTrack(value: number): string {
  if (value >= 70) return 'rgba(255,59,48,0.2)';
  if (value >= 45) return 'rgba(255,149,0,0.2)';
  return 'rgba(255,255,255,0.1)';
}

function formatCoord(value: number | null, positive: string, negative: string): string {
  if (value === null || Number.isNaN(value)) return '--';
  const hemisphere = value >= 0 ? positive : negative;
  return `${Math.abs(value).toFixed(1)}° ${hemisphere}`;
}

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="ios-sat-risk-bar-row">
      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: 4 }}>
        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ color: riskColor(value), fontFamily: 'var(--font-mono)' }}>{value.toFixed(0)}%</span>
      </div>
      <div style={{ width: '100%', height: 4, borderRadius: 2, background: 'var(--border-light)', overflow: 'hidden' }}>
        <div
          style={{
            width: `${Math.max(4, value)}%`,
            height: '100%',
            background: riskColor(value),
            transition: 'width 0.35s ease',
          }}
        />
      </div>
    </div>
  );
}

function SatelliteCard({ satellite }: { satellite: TurkishSatelliteAssessment }) {
  const [expanded, setExpanded] = useState(false);
  
  const geometryLabel = satellite.overTurkiye
    ? 'Türkiye üzerinde'
    : satellite.visibleFromTurkiye
      ? 'Görüş penceresinde'
      : 'Türkiye dışı';

  return (
    <article className="ios-sat-card">
      <div className="ios-sat-card-top">
        <div>
          <h4 className="ios-sat-name">{satellite.name}</h4>
          <div className="ios-sat-type">{satellite.missionFamily} • {satellite.orbitClass} • NORAD {satellite.noradId}</div>
        </div>
        <div className="ios-sat-score" style={{ color: riskColor(satellite.overallRiskPercent), borderColor: riskTrack(satellite.overallRiskPercent) }}>
          %{satellite.overallRiskPercent.toFixed(0)}
        </div>
      </div>

      <div className="ios-sat-body">
        <div className="ios-sat-pos-grid">
          <div className="ios-sat-pos-box">
            <div className="ios-sat-pos-lbl">Konum</div>
            <div className="ios-sat-pos-val">
              {formatCoord(satellite.latitude, 'K', 'G')} / {formatCoord(satellite.longitude, 'D', 'B')}
            </div>
            <div className="ios-sat-pos-sub">Alt: {satellite.altitudeKm?.toFixed(0) ?? '--'} km</div>
          </div>
          <div className="ios-sat-pos-box">
            <div className="ios-sat-pos-lbl">Görünürlük</div>
            <div className="ios-sat-pos-val">{geometryLabel}</div>
            <div className="ios-sat-pos-sub">El: {satellite.elevationDeg?.toFixed(1) ?? '--'}°</div>
          </div>
        </div>

        <div className="ios-sat-risk-bars">
          <MetricBar label="Sürtünme (Drag)" value={satellite.dragRiskPercent} />
          <MetricBar label="Yüklenme (Charging)" value={satellite.chargingRiskPercent} />
          <MetricBar label="Radyasyon" value={satellite.radiationRiskPercent} />
          <MetricBar label="Servis" value={satellite.serviceRiskPercent} />
        </div>
        
        <div className="ios-sat-alert">
          <strong>Baskın Faktör: {satellite.dominantDriver}</strong>
          {satellite.summary}
        </div>
      </div>

      {expanded && (
        <div className="ios-sat-details-pane">
          <div className="ios-sat-alert">
            <strong>Gözlem</strong><br/>
            {satellite.observationSummary}
          </div>
          <div className="ios-sat-alert">
            <strong>Neden & Bilimsel Not</strong><br/>
            {satellite.riskReason} {satellite.scientificNote}
          </div>
          <div className="ios-sat-alert" style={{ background: 'var(--surface)' }}>
            <strong>Aksiyon</strong><br/>
            {satellite.recommendedAction}
          </div>
        </div>
      )}

      <button className="ios-sat-details-toggle" onClick={() => setExpanded(!expanded)}>
        {expanded ? '▲ Detayları Gizle' : '▼ Analiz Detayları'}
      </button>
    </article>
  );
}

export function TurkishSatellitePanel({ telemetry }: { telemetry: TelemetrySnapshot }) {
  const satellites = telemetry.turkishSatellites ?? [];
  const topSatellite = satellites[0] ?? null;

  return (
    <section className="ios-satellite-panel">
      <div className="ios-satellite-header">
        <div>
          <h2 className="ios-satellite-title">Türk Uydu Filosu Uzay Havası Etki Analizi</h2>
          <p className="ios-satellite-desc">
            N2YO yörünge çözümleri, NOAA L1 telemetrisi ve HELIOGUARD fizik motoru üzerinden Türk uydularının risk analizleri.
          </p>
        </div>

        <div className="ios-satellite-kpis">
          <div className="ios-kpi">
            <div className="ios-kpi-label">Filo Riski</div>
            <div className="ios-kpi-val" style={{ color: riskColor(telemetry.turkishSatelliteRiskPercent) }}>
              %{telemetry.turkishSatelliteRiskPercent.toFixed(0)}
            </div>
            <div className="ios-kpi-sub">{telemetry.turkishSatelliteHeadline ?? 'İzleniyor'}</div>
          </div>
          <div className="ios-kpi">
            <div className="ios-kpi-label">Aktif Varlık</div>
            <div className="ios-kpi-val">{telemetry.turkishSatelliteCount}</div>
            <div className="ios-kpi-sub">Telemetri ulaşıyor</div>
          </div>
          <div className="ios-kpi">
            <div className="ios-kpi-label">En Kritik</div>
            <div className="ios-kpi-val" style={{ fontSize: '1.2rem', lineHeight: '1.5' }}>
              {topSatellite?.name ?? '--'}
            </div>
            <div className="ios-kpi-sub">
              {topSatellite ? `${topSatellite.dominantDriver}` : 'Bekleniyor'}
            </div>
          </div>
        </div>
      </div>

      {!satellites.length ? (
        <div style={{ padding: 24, color: 'var(--text-muted)' }}>
          Türk uydu verisi henüz yüklenmedi veya güncelleniyor.
        </div>
      ) : (
        <div className="ios-satellite-grid">
          {satellites.map((satellite) => (
            <SatelliteCard key={`${satellite.noradId}-${satellite.name}`} satellite={satellite} />
          ))}
        </div>
      )}
    </section>
  );
}
