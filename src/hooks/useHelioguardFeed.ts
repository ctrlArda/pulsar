import { startTransition, useEffect, useMemo, useState } from "react";
import { getDashboardState, getTerminalStreamUrl, setOperatingMode } from "../lib/api";
import type {
  CrisisAlert,
  DashboardState,
  OperatingMode,
  TerminalLine,
  TelemetrySnapshot,
} from "../types/helioguard";

const initialState: DashboardState = {
  mode: "live",
  telemetry: null,
  activeAlert: null,
  alerts: [],
  terminal: [],
};

function mergeAlerts(current: CrisisAlert[], incoming: CrisisAlert[]): CrisisAlert[] {
  const map = new Map<string, CrisisAlert>();
  [...incoming, ...current].forEach((alert) => map.set(alert.id, alert));
  return Array.from(map.values())
    .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
    .slice(0, 6);
}

function mergeTerminal(current: TerminalLine[], incoming: TerminalLine): TerminalLine[] {
  return [incoming, ...current].slice(0, 80);
}

function normalizeTelemetry(telemetry: TelemetrySnapshot | null): TelemetrySnapshot | null {
  if (!telemetry) {
    return null;
  }
  return {
    ...telemetry,
    etaWindowStartSeconds: telemetry.etaWindowStartSeconds ?? telemetry.etaSeconds ?? null,
    etaWindowEndSeconds: telemetry.etaWindowEndSeconds ?? telemetry.etaSeconds ?? null,
    bowShockDelaySeconds: telemetry.bowShockDelaySeconds ?? null,
    riskBandLow: telemetry.riskBandLow ?? telemetry.localRiskPercent,
    riskBandHigh: telemetry.riskBandHigh ?? telemetry.localRiskPercent,
    dstIndex: telemetry.dstIndex ?? null,
    protonFluxPfu: telemetry.protonFluxPfu ?? null,
    dynamicPressureNpa: telemetry.dynamicPressureNpa ?? 0,
    localSolarHour: telemetry.localSolarHour ?? 12,
    magnetopauseStandoffRe: telemetry.magnetopauseStandoffRe ?? 10.5,
    magnetopauseShapeAlpha: telemetry.magnetopauseShapeAlpha ?? 0.58,
    geoExposureRiskPercent: telemetry.geoExposureRiskPercent ?? 0,
    geoDirectExposure: telemetry.geoDirectExposure ?? false,
    predictedDbdtNtPerMin: telemetry.predictedDbdtNtPerMin ?? 0,
    tecVerticalTecu: telemetry.tecVerticalTecu ?? 0,
    tecDelayMeters: telemetry.tecDelayMeters ?? 0,
    gnssRiskPercent: telemetry.gnssRiskPercent ?? 0,
    forecastConfidencePercent: telemetry.forecastConfidencePercent ?? 65,
    sourceCoveragePercent: telemetry.sourceCoveragePercent ?? 60,
    dataFreshnessSeconds: telemetry.dataFreshnessSeconds ?? null,
    stormScaleBand: telemetry.stormScaleBand ?? telemetry.officialGeomagneticScale ?? "G0",
    officialGeomagneticScale: telemetry.officialGeomagneticScale ?? null,
    officialRadioBlackoutScale: telemetry.officialRadioBlackoutScale ?? null,
    officialSolarRadiationScale: telemetry.officialSolarRadiationScale ?? null,
    officialWatchHeadline: telemetry.officialWatchHeadline ?? null,
    officialAlertHeadline: telemetry.officialAlertHeadline ?? null,
    officialForecastKpMax: telemetry.officialForecastKpMax ?? null,
    officialForecastScale: telemetry.officialForecastScale ?? null,
    precursorRiskPercent: telemetry.precursorRiskPercent ?? null,
    precursorRiskBandLow: telemetry.precursorRiskBandLow ?? telemetry.precursorRiskPercent ?? null,
    precursorRiskBandHigh: telemetry.precursorRiskBandHigh ?? telemetry.precursorRiskPercent ?? null,
    precursorHorizonHours: telemetry.precursorHorizonHours ?? null,
    precursorConfidencePercent: telemetry.precursorConfidencePercent ?? null,
    precursorHeadline: telemetry.precursorHeadline ?? null,
    precursorCmeSpeedKms: telemetry.precursorCmeSpeedKms ?? null,
    precursorArrivalAt: telemetry.precursorArrivalAt ?? null,
    precursorIsEarthDirected: telemetry.precursorIsEarthDirected ?? false,
    mlRiskBandLow: telemetry.mlRiskBandLow ?? telemetry.mlRiskPercent ?? null,
    mlRiskBandHigh: telemetry.mlRiskBandHigh ?? telemetry.mlRiskPercent ?? null,
    mlPredictedDstIndex: telemetry.mlPredictedDstIndex ?? null,
    mlPredictedDstBandLow: telemetry.mlPredictedDstBandLow ?? null,
    mlPredictedDstBandHigh: telemetry.mlPredictedDstBandHigh ?? null,
    mlBaselineDstIndex: telemetry.mlBaselineDstIndex ?? null,
    mlTargetName: telemetry.mlTargetName ?? null,
    mlTargetUnit: telemetry.mlTargetUnit ?? null,
    mlFeatureContributions: telemetry.mlFeatureContributions ?? [],
    validationMae: telemetry.validationMae ?? null,
    validationBandCoverage: telemetry.validationBandCoverage ?? null,
    validationRows: telemetry.validationRows ?? null,
    validationHorizonMinutes: telemetry.validationHorizonMinutes ?? telemetry.mlLeadTimeMinutes ?? null,
    turkishSatelliteCount: telemetry.turkishSatelliteCount ?? 0,
    turkishSatelliteRiskPercent: telemetry.turkishSatelliteRiskPercent ?? 0,
    turkishSatelliteHeadline: telemetry.turkishSatelliteHeadline ?? null,
    turkishSatellites: telemetry.turkishSatellites ?? [],
    decisionCommentary: telemetry.decisionCommentary ?? [],
    sourceStatuses: telemetry.sourceStatuses ?? [],
  };
}

function normalizeState(state: DashboardState): DashboardState {
  return {
    ...state,
    telemetry: normalizeTelemetry(state.telemetry),
  };
}

export function useHelioguardFeed() {
  const [state, setState] = useState<DashboardState>(initialState);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSwitching, setIsSwitching] = useState(false);

  useEffect(() => {
    let mounted = true;

    const syncState = async () => {
      try {
        const nextState = normalizeState(await getDashboardState());
        if (!mounted) {
          return;
        }
        startTransition(() => {
          setState(nextState);
          setError(null);
          setLoading(false);
        });
      } catch (caught) {
        if (!mounted) {
          return;
        }
        setError(caught instanceof Error ? caught.message : "Panel verisi alinamadi.");
        setLoading(false);
      }
    };

    void syncState();
    const timer = window.setInterval(() => {
      void syncState();
    }, 20000);

    const stream = new EventSource(getTerminalStreamUrl());
    stream.onmessage = (event) => {
      const line = JSON.parse(event.data) as TerminalLine;
      startTransition(() => {
        setState((current) => ({
          ...current,
          terminal: mergeTerminal(current.terminal, line),
        }));
      });
    };
    stream.onerror = () => stream.close();

    return () => {
      mounted = false;
      window.clearInterval(timer);
      stream.close();
    };
  }, []);

  async function switchMode(mode: OperatingMode) {
    try {
      setIsSwitching(true);
      const nextState = normalizeState(await setOperatingMode(mode));
      startTransition(() => {
        setState((current) => ({
          ...nextState,
          alerts: mergeAlerts(current.alerts, nextState.alerts),
        }));
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Mod degistirilemedi.");
    } finally {
      setIsSwitching(false);
    }
  }

  const headline = useMemo(() => {
    if (state.activeAlert) {
      return state.activeAlert.title;
    }
    if (state.telemetry) {
      return state.telemetry.summaryHeadline;
    }
    return "Uzay havasi motoru baslatiliyor";
  }, [state.activeAlert, state.telemetry]);

  return {
    state,
    loading,
    error,
    isSwitching,
    headline,
    switchMode,
  };
}
